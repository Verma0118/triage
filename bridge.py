"""Unit sources: MockUnit always; LiveUnit imports serial/yamspy only on live paths."""

from __future__ import annotations

import atexit
import logging
import math
import os
import queue
import re
import signal
import threading
import time
from typing import Callable

import config

log = logging.getLogger("triage.bridge")

SENSOR_GYRO = 1 << 5
_NAME_OK = re.compile(r"^TRIAGE-[AB]-001$")

# Process-wide live unit for atexit / signal motors_off (set by LiveUnit).
_live_for_safety: "LiveUnit | None" = None
_safety_registered = False


def _variant_from_name(name: str) -> str:
    parts = name.split("-")
    if len(parts) >= 2 and len(parts[1]) == 1 and parts[1].isalpha():
        return parts[1].upper()
    return "A"


def _battery_pct(voltage: float) -> float:
    span = config.BATTERY_V_MAX - config.BATTERY_V_MIN
    if span <= 0:
        return 0.0
    return max(0.0, min(1.0, (voltage - config.BATTERY_V_MIN) / span))


class MockUnit:
    """Simulated Unit 1. Tests can set battery_v / battery_pct / ready."""

    def __init__(self) -> None:
        self.name = "TRIAGE-A-001"
        self.battery_v = 15.8
        self.battery_pct = 1.0
        self.ready = True
        self.armed = False
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        self._tick = 0
        self.motor_tests = 0
        self._closed = False

    def read(self) -> dict:
        self._tick += 1
        phase = self._tick * 0.05
        self.roll = 8.0 * math.sin(phase)
        self.pitch = 5.0 * math.cos(phase * 0.7)
        self.yaw = (self.yaw + 0.2) % 360.0
        return {
            "source": "mock",
            "name": self.name,
            "variant": _variant_from_name(self.name),
            "battery_v": self.battery_v,
            "battery_pct": self.battery_pct,
            "ready": self.ready,
            "armed": self.armed,
            "roll": self.roll,
            "pitch": self.pitch,
            "yaw": self.yaw,
            "age": 0.0,
        }

    def motor_test(self) -> bool:
        self.motor_tests += 1
        return True

    def set_name(self, name: str) -> bool:
        self.name = name
        return True

    def motors_off(self) -> None:
        return None

    def close(self) -> None:
        self._closed = True


class LiveUnit:
    """One background thread owns the serial port. read() never blocks on I/O."""

    def __init__(
        self,
        *,
        board=None,
        connect: Callable | None = None,
        on_event: Callable[[str], None] | None = None,
        autostart: bool = True,
        port: str | None = None,
    ) -> None:
        self.on_event = on_event
        self._connect_fn = connect
        self._port = port
        self._board = board
        self._injected = board is not None
        self._mock = MockUnit()
        self._lock = threading.Lock()
        self._q: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._motor_running = False
        self._live = False
        self._msp_log: list[str] = []
        self._last_retry = 0.0
        self._thread: threading.Thread | None = None
        now = time.monotonic()
        self._snap: dict = {
            "source": "mock",
            "name": "TRIAGE-A-001",
            "variant": "A",
            "battery_v": 15.8,
            "battery_pct": 1.0,
            "ready": False,
            "armed": False,
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": 0.0,
            "age": 0.0,
            "polled_at": now,
        }
        if autostart:
            self.start()

    def _emit(self, msg: str) -> None:
        log.info("hw: %s", msg)
        if self.on_event is not None:
            try:
                self.on_event(msg)
            except Exception:
                log.exception("on_event failed")

    def start(self) -> None:
        global _live_for_safety
        _register_safety()
        _live_for_safety = self
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._worker, name="triage-liveunit", daemon=True
        )
        self._thread.start()

    def read(self) -> dict:
        with self._lock:
            snap = dict(self._snap)
            polled_at = float(snap.pop("polled_at", time.monotonic()))
        age = time.monotonic() - polled_at
        snap["age"] = age
        if snap["source"] == "live":
            ready = (
                age < 1.0
                and float(snap["battery_v"]) > config.BATTERY_V_MIN
                and bool(snap.get("_gyro", True))
            )
            snap["ready"] = ready
        snap.pop("_gyro", None)
        return snap

    def motor_test(self) -> bool:
        if not config.MOTORS_ENABLED:
            self._emit("motor test refused: MOTORS_ENABLED false")
            return False
        with self._lock:
            armed = bool(self._snap.get("armed"))
            voltage = float(self._snap.get("battery_v") or 0.0)
            live = self._live
            running = self._motor_running
        if not live and not self._injected:
            self._emit("motor test refused: not live")
            return False
        if armed:
            self._emit("motor test refused: armed")
            return False
        if voltage <= config.BATTERY_V_MIN:
            self._emit("motor test refused: low voltage")
            return False
        if running:
            self._emit("motor test refused: already running")
            return False
        self._motor_running = True
        self._q.put(("motor_test",))
        return True

    def set_name(self, name: str) -> bool:
        self._q.put(("set_name", name))
        return True

    def motors_off(self) -> None:
        # Prefer synchronous off on the worker; also try direct if injected/idle.
        self._q.put(("motors_off",))
        if self._board is not None and not self._motor_running:
            try:
                self._send_motors_all(1000, times=3)
            except Exception:
                pass

    def close(self) -> None:
        global _live_for_safety
        self._stop.set()
        self._q.put(("stop",))
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        try:
            self._send_motors_all(1000, times=3)
        except Exception:
            pass
        self._close_board()
        self._live = False
        with self._lock:
            self._snap["source"] = "mock"
        if _live_for_safety is self:
            _live_for_safety = None

    # --- worker -----------------------------------------------------------------

    def _worker(self) -> None:
        try:
            if self._injected:
                self._live = True
                self._ensure_craft_name()
                self._poll_once()
            else:
                self._try_connect()
            while not self._stop.is_set():
                try:
                    item = self._q.get(timeout=0.05)
                except queue.Empty:
                    item = None
                if item is not None:
                    self._handle_cmd(item)
                    if item[0] == "stop":
                        break
                if self._live:
                    try:
                        self._poll_once()
                    except Exception as err:
                        self._on_serial_lost(err)
                else:
                    self._apply_mock_snap()
                    now = time.monotonic()
                    if now - self._last_retry >= 3.0:
                        self._last_retry = now
                        self._try_connect()
        finally:
            try:
                self._send_motors_all(1000, times=3)
            except Exception:
                pass
            self._close_board()

    def _handle_cmd(self, item: tuple) -> None:
        kind = item[0]
        if kind == "stop":
            return
        if kind == "motors_off":
            try:
                self._send_motors_all(1000, times=3)
            except Exception as err:
                self._emit(f"motors_off failed: {err}")
            return
        if kind == "set_name":
            self._do_set_name(str(item[1]))
            return
        if kind == "motor_test":
            self._do_motor_test()
            return

    def _try_connect(self) -> None:
        if self._injected:
            return
        try:
            if self._connect_fn is not None:
                self._board = self._connect_fn()
            else:
                self._board = self._open_real_board()
            self._live = True
            self._emit("live connected")
            self._ensure_craft_name()
            self._poll_once()
        except Exception as err:
            self._board = None
            self._live = False
            self._apply_mock_snap()
            self._emit(f"live connect failed, using mock: {err}")

    def _open_real_board(self):
        import serial
        from serial.tools import list_ports
        from yamspy import MSPy

        port = self._port or config.SERIAL_PORT or os.environ.get("TRIAGE_PORT")
        if not port:
            for info in list_ports.comports():
                if info.device.startswith("/dev/cu.usbmodem"):
                    port = info.device
                    break
        if not port:
            raise RuntimeError("no flight controller port found")
        board = MSPy(device=port, logfilename=os.devnull, loglevel="ERROR", trials=1)
        board.conn.open()
        board.INAV = False
        self._msp_transact(board, "MSP_API_VERSION")
        self._msp_transact(board, "MSP_FC_VARIANT")
        ident = board.CONFIG.get("flightControllerIdentifier", "")
        board.INAV = "INAV" in str(ident)
        self._msp_transact(board, "MSP_FC_VERSION")
        return board

    def _close_board(self) -> None:
        board = self._board
        if board is None or self._injected:
            return
        try:
            if getattr(board, "conn", None) and board.conn.is_open:
                board.conn.close()
        except Exception:
            pass
        self._board = None

    def _on_serial_lost(self, err: Exception) -> None:
        self._emit(f"serial lost, falling back to mock: {err}")
        try:
            self._send_motors_all(1000, times=3)
        except Exception:
            pass
        self._close_board()
        self._live = False
        self._apply_mock_snap()

    def _apply_mock_snap(self) -> None:
        snap = self._mock.read()
        snap["polled_at"] = time.monotonic()
        snap["_gyro"] = True
        with self._lock:
            self._snap = snap

    def _msp_transact(self, board, code_name: str, data=None) -> bool:
        from yamspy import MSPy

        self._msp_log.append(code_name)
        payload = [] if data is None else data
        code = MSPy.MSPCodes[code_name]
        if not board.send_RAW_msg(code, data=payload):
            return False
        handler = board.receive_msg()
        if not handler:
            return False
        board.process_recv_data(handler)
        return True

    def _msp_transact_current(self, code_name: str, data=None) -> bool:
        board = self._board
        if board is None:
            return False
        if self._injected:
            # Fake board: no real MSP codes; just record and apply side effects.
            self._msp_log.append(code_name)
            if code_name == "MSP_SET_NAME" and data is not None:
                name = bytes(data).decode("utf-8", errors="replace")
                board.CONFIG["name"] = name
                board.name_written = name
            return True
        return self._msp_transact(board, code_name, data)

    def _poll_once(self) -> None:
        board = self._board
        if board is None:
            return
        if self._injected:
            self._msp_log.append("MSP_ATTITUDE")
            self._msp_log.append("MSP_ANALOG")
            self._msp_log.append("MSP_STATUS_EX")
            self._msp_log.append("MSP_NAME")
            roll, pitch, yaw = (float(x) for x in board.SENSOR_DATA["kinematics"])
            voltage = float(board.ANALOG.get("voltage") or 0.0)
            armed = bool(getattr(board, "_armed", False))
            name = (board.CONFIG.get("name") or "").rstrip("\x00")
            gyro = bool(board.CONFIG.get("activeSensors", 0) & SENSOR_GYRO)
        else:
            import serial

            try:
                self._msp_transact_current("MSP_ATTITUDE")
                roll, pitch, yaw = (
                    float(x) for x in board.SENSOR_DATA["kinematics"]
                )
                self._msp_transact_current("MSP_ANALOG")
                voltage = float(board.ANALOG.get("voltage") or 0.0)
                self._msp_transact_current("MSP_STATUS_EX")
                if not board.AUX_CONFIG:
                    self._msp_transact_current("MSP_BOXNAMES")
                modes = board.process_mode(board.CONFIG.get("mode", 0))
                armed = "ARM" in modes
                self._msp_transact_current("MSP_NAME")
                name = (board.CONFIG.get("name") or "").rstrip("\x00")
                gyro = bool(board.CONFIG.get("activeSensors", 0) & SENSOR_GYRO)
            except serial.SerialException as err:
                raise err

        now = time.monotonic()
        age = 0.0
        ready = (
            age < 1.0
            and voltage > config.BATTERY_V_MIN
            and gyro
        )
        with self._lock:
            self._snap = {
                "source": "live",
                "name": name,
                "variant": _variant_from_name(name),
                "battery_v": voltage,
                "battery_pct": _battery_pct(voltage),
                "ready": ready,
                "armed": armed,
                "roll": roll,
                "pitch": pitch,
                "yaw": yaw,
                "age": age,
                "polled_at": now,
                "_gyro": gyro,
            }
        self._live = True

    def _ensure_craft_name(self) -> None:
        board = self._board
        if board is None:
            return
        if self._injected:
            name = (board.CONFIG.get("name") or "").rstrip("\x00")
        else:
            self._msp_transact_current("MSP_NAME")
            name = (board.CONFIG.get("name") or "").rstrip("\x00")
        if not _NAME_OK.match(name):
            self._do_set_name("TRIAGE-A-001")

    def _do_set_name(self, name: str) -> None:
        board = self._board
        if board is None:
            self._mock.set_name(name)
            with self._lock:
                self._snap["name"] = name
                self._snap["variant"] = _variant_from_name(name)
            return
        self._msp_transact_current("MSP_SET_NAME", list(name.encode("utf-8")))
        # NEVER EEPROM save.
        if self._injected:
            after = (board.CONFIG.get("name") or "").rstrip("\x00")
        else:
            self._msp_transact_current("MSP_NAME")
            after = (board.CONFIG.get("name") or "").rstrip("\x00")
        with self._lock:
            self._snap["name"] = name
            self._snap["variant"] = _variant_from_name(name)
        if after != name:
            self._emit("name write unverified")

    def _send_motors_all(self, value: int, times: int = 1) -> None:
        board = self._board
        if board is None:
            return
        for _ in range(times):
            board.send_RAW_MOTORS([int(value)] * 8)
            if not self._injected:
                try:
                    handler = board.receive_msg()
                    if handler:
                        board.process_recv_data(handler)
                except Exception:
                    pass

    def _do_motor_test(self) -> None:
        # Sole path that may send a motor value above 1000.
        value = min(config.MOTOR_TEST_VALUE, config.MOTOR_HARD_CAP)
        duration = float(config.MOTOR_TEST_SECONDS)
        interval = 0.1
        try:
            deadline = time.monotonic() + duration
            while time.monotonic() < deadline and not self._stop.is_set():
                self._send_motors_all(value, times=1)
                time.sleep(interval)
        except Exception as err:
            self._emit(f"motor test error: {err}")
        finally:
            try:
                self._send_motors_all(1000, times=3)
            except Exception as err:
                self._emit(f"motor stop failed: {err}")
            self._motor_running = False


def _safety_motors_off() -> None:
    unit = _live_for_safety
    if unit is None:
        return
    try:
        unit.motors_off()
    except Exception:
        pass
    try:
        unit._send_motors_all(1000, times=3)
    except Exception:
        pass


def _signal_stop(signum, _frame) -> None:
    _safety_motors_off()
    raise SystemExit(128 + signum)


def _register_safety() -> None:
    global _safety_registered
    if _safety_registered:
        return
    atexit.register(_safety_motors_off)
    try:
        signal.signal(signal.SIGINT, _signal_stop)
        signal.signal(signal.SIGTERM, _signal_stop)
    except Exception:
        pass
    _safety_registered = True
