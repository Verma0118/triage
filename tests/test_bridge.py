"""H3-code: LiveUnit with fake board — no real serial port."""

from __future__ import annotations

import threading
import time

import config
import main
from bridge import LiveUnit, MockUnit, _variant_from_name
from fastapi.testclient import TestClient
from main import app


SENSOR_GYRO = 1 << 5


class FakeConn:
    def __init__(self, is_open: bool = True):
        self.is_open = is_open

    def open(self):
        self.is_open = True

    def close(self):
        self.is_open = False


class FakeBoard:
    """Minimal board matching the MSP calls LiveUnit uses."""

    MSP_ANALOG = object()
    MSP_BATTERY_STATE = object()

    def __init__(self):
        self.CONFIG = {
            "name": "TRIAGE-A-001",
            "activeSensors": SENSOR_GYRO,
            "mode": 0,
            "armingDisableFlags": 0,
            "apiVersion": "1.48",
            "flightControllerIdentifier": "BTFL",
            "flightControllerVersion": "26.6.2",
        }
        self.SENSOR_DATA = {"kinematics": [1.0, -2.0, 90.0]}
        self.ANALOG = {"voltage": 15.8}
        self.AUX_CONFIG = ["ARM"]
        self.INAV = False
        self.conn = FakeConn(True)
        self.motor_frames: list[list[int]] = []
        self.msp_names: list[str] = []
        self.raise_on_motor: Exception | None = None
        self._armed = False
        self.name_written: str | None = None

    def send_RAW_msg(self, code, data=None):
        # Record by reverse-looking name is done by LiveUnit via code_name arg path.
        return True

    def receive_msg(self):
        return b"ok"

    def process_recv_data(self, handler):
        return None

    def send_RAW_MOTORS(self, values):
        if self.raise_on_motor is not None:
            raise self.raise_on_motor
        self.motor_frames.append([int(v) for v in values])

    def process_mode(self, mode):
        return ["ARM"] if self._armed else []

    def process_armingDisableFlags(self, flags):
        return []


def _wait_motors(board: FakeBoard, min_frames: int, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if len(board.motor_frames) >= min_frames:
            return
        time.sleep(0.01)
    raise AssertionError(
        f"expected >= {min_frames} motor frames, got {len(board.motor_frames)}"
    )


def test_motor_test_refused_when_motors_disabled(monkeypatch):
    monkeypatch.setattr(config, "MOTORS_ENABLED", False)
    board = FakeBoard()
    events: list[str] = []
    unit = LiveUnit(board=board, on_event=lambda m: events.append(m), autostart=True)
    try:
        assert unit.motor_test() is False
        assert board.motor_frames == []
        assert any("motor" in e.lower() or "refused" in e.lower() for e in events)
    finally:
        unit.close()


def test_motor_test_refused_when_armed(monkeypatch):
    monkeypatch.setattr(config, "MOTORS_ENABLED", True)
    board = FakeBoard()
    board._armed = True
    unit = LiveUnit(board=board, autostart=True)
    try:
        time.sleep(0.15)  # let poll see armed
        assert unit.read()["armed"] is True
        assert unit.motor_test() is False
        assert board.motor_frames == []
    finally:
        unit.close()


def test_motor_test_refused_when_voltage_low(monkeypatch):
    monkeypatch.setattr(config, "MOTORS_ENABLED", True)
    board = FakeBoard()
    board.ANALOG["voltage"] = config.BATTERY_V_MIN
    unit = LiveUnit(board=board, autostart=True)
    try:
        time.sleep(0.15)
        assert unit.read()["battery_v"] <= config.BATTERY_V_MIN
        assert unit.motor_test() is False
        assert board.motor_frames == []
    finally:
        unit.close()


def test_motor_value_never_exceeds_hard_cap(monkeypatch):
    monkeypatch.setattr(config, "MOTORS_ENABLED", True)
    monkeypatch.setattr(config, "MOTOR_TEST_VALUE", 1500)
    monkeypatch.setattr(config, "MOTOR_TEST_SECONDS", 0.15)
    board = FakeBoard()
    unit = LiveUnit(board=board, autostart=True)
    try:
        time.sleep(0.1)
        assert unit.motor_test() is True
        _wait_motors(board, 4)
        time.sleep(0.05)
        above = [f for f in board.motor_frames if any(v > 1000 for v in f)]
        assert above, "expected at least one spin frame"
        for frame in board.motor_frames:
            assert all(v <= config.MOTOR_HARD_CAP for v in frame)
            assert all(v != 1500 for v in frame)
    finally:
        unit.close()


def test_two_motor_tests_only_one_run(monkeypatch):
    monkeypatch.setattr(config, "MOTORS_ENABLED", True)
    monkeypatch.setattr(config, "MOTOR_TEST_SECONDS", 0.25)
    board = FakeBoard()
    unit = LiveUnit(board=board, autostart=True)
    try:
        time.sleep(0.1)
        assert unit.motor_test() is True
        assert unit.motor_test() is False
        _wait_motors(board, 4)
        # Wait for completion
        deadline = time.monotonic() + 1.0
        while unit._motor_running and time.monotonic() < deadline:
            time.sleep(0.02)
        spin = [f for f in board.motor_frames if f[0] > 1000]
        # One contiguous run only — all spin frames share the capped value.
        assert spin
        assert all(f[0] == spin[0][0] for f in spin)
    finally:
        unit.close()


def test_motor_run_ends_with_three_all_1000(monkeypatch):
    monkeypatch.setattr(config, "MOTORS_ENABLED", True)
    monkeypatch.setattr(config, "MOTOR_TEST_SECONDS", 0.12)
    board = FakeBoard()
    unit = LiveUnit(board=board, autostart=True)
    try:
        time.sleep(0.1)
        assert unit.motor_test() is True
        deadline = time.monotonic() + 1.5
        while unit._motor_running and time.monotonic() < deadline:
            time.sleep(0.02)
        time.sleep(0.05)
        assert len(board.motor_frames) >= 4
        assert board.motor_frames[-3:] == [[1000] * 8] * 3
    finally:
        unit.close()


def test_motor_run_all_1000_if_board_raises(monkeypatch):
    monkeypatch.setattr(config, "MOTORS_ENABLED", True)
    monkeypatch.setattr(config, "MOTOR_TEST_SECONDS", 0.3)
    board = FakeBoard()
    calls = {"n": 0}

    def flaky(values):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        board.motor_frames.append([int(v) for v in values])

    board.send_RAW_MOTORS = flaky  # type: ignore[method-assign]
    unit = LiveUnit(board=board, autostart=True)
    try:
        time.sleep(0.1)
        unit.motor_test()
        deadline = time.monotonic() + 1.5
        while unit._motor_running and time.monotonic() < deadline:
            time.sleep(0.02)
        time.sleep(0.05)
        assert board.motor_frames[-3:] == [[1000] * 8] * 3
    finally:
        unit.close()


def test_voltage_via_msp_analog_never_battery_state():
    board = FakeBoard()
    unit = LiveUnit(board=board, autostart=True)
    try:
        time.sleep(0.2)
        snap = unit.read()
        assert snap["battery_v"] == 15.8
        assert "MSP_ANALOG" in unit._msp_log
        assert "MSP_BATTERY_STATE" not in unit._msp_log
    finally:
        unit.close()


def test_connect_failure_source_mock_app_starts(monkeypatch):
    monkeypatch.setattr(config, "USE_MOCK", False)

    def boom():
        raise OSError("no port")

    monkeypatch.setattr(main, "TICK_SLEEP", 0.0)
    # Force LiveUnit connect to fail when main builds bridge.
    import bridge as bridge_mod

    real_live = bridge_mod.LiveUnit

    def failing_live(**kwargs):
        return real_live(connect=boom, on_event=kwargs.get("on_event"), autostart=True)

    monkeypatch.setattr(bridge_mod, "LiveUnit", failing_live)
    monkeypatch.setattr(main, "LiveUnit", failing_live)

    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        # Bridge should be presenting mock source.
        snap = main.bridge.read()
        assert snap["source"] == "mock"


def test_stale_snapshot_ready_false(monkeypatch):
    board = FakeBoard()
    unit = LiveUnit(board=board, autostart=True)
    try:
        time.sleep(0.15)
        assert unit.read()["ready"] is True
        # Freeze poll by stopping thread updates: age the snapshot manually.
        with unit._lock:
            unit._snap["polled_at"] = time.monotonic() - 2.0
        snap = unit.read()
        assert snap["age"] > 1.0
        assert snap["ready"] is False
    finally:
        unit.close()


def test_variant_from_name():
    assert _variant_from_name("TRIAGE-A-001") == "A"
    assert _variant_from_name("TRIAGE-B-001") == "B"
    assert _variant_from_name("OTHER") == "A"
