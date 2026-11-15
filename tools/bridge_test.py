#!/usr/bin/env python3
"""Standalone Betaflight FC test over USB. Human-run only. Do not invoke from agents."""

from __future__ import annotations

import argparse
import atexit
import os
import signal
import sys
import time
from pathlib import Path

import serial
from serial.tools import list_ports
from yamspy import MSPy

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402

# Betaflight MSP_STATUS(_EX) activeSensors bits: 0 acc, 1 baro, 2 mag, 3 gps, 4 rangefinder, 5 gyro.
SENSOR_GYRO = 1 << 5

_board: MSPy | None = None


def resolve_port(cli_port: str | None) -> str:
    if cli_port:
        return cli_port
    env_port = os.environ.get("TRIAGE_PORT") or config.SERIAL_PORT
    if env_port:
        return env_port
    for info in list_ports.comports():
        if info.device.startswith("/dev/cu.usbmodem"):
            return info.device
    sys.exit(
        "No flight controller found. Expected a /dev/cu.usbmodem* port.\n"
        "Plug in the FC over USB, close Betaflight Configurator, or pass --port / TRIAGE_PORT."
    )


def open_board(port: str) -> MSPy:
    board = MSPy(device=port, logfilename=os.devnull, loglevel="ERROR", trials=1)
    try:
        board.conn.open()
    except serial.SerialException as err:
        err_l = str(err).lower()
        busy = (
            "busy" in err_l
            or "resource temporarily unavailable" in err_l
            or getattr(err, "errno", None) in (16, 35)
        )
        if busy:
            sys.exit(
                f"Port {port} is busy. Close Betaflight Configurator (it holds the serial port) "
                f"and try again.\n({err})"
            )
        sys.exit(f"Could not open serial port {port}: {err}")
    except FileNotFoundError as err:
        sys.exit(f"Port {port} not found: {err}")
    board.INAV = False
    return board


def close_board(board: MSPy | None) -> None:
    if board is None:
        return
    try:
        if board.conn and board.conn.is_open:
            board.conn.close()
    except Exception:
        pass


def msp_transact(board: MSPy, code_name: str, data: list | bytearray | None = None) -> bool:
    """Send one MSP request and process the reply into board state."""
    payload = [] if data is None else data
    code = MSPy.MSPCodes[code_name]
    if not board.send_RAW_msg(code, data=payload):
        return False
    handler = board.receive_msg()
    if not handler:
        return False
    board.process_recv_data(handler)
    return True


def identify_fc(board: MSPy) -> None:
    msp_transact(board, "MSP_API_VERSION")
    msp_transact(board, "MSP_FC_VARIANT")
    ident = board.CONFIG.get("flightControllerIdentifier", "")
    board.INAV = "INAV" in ident
    msp_transact(board, "MSP_FC_VERSION")


def read_name(board: MSPy) -> str:
    msp_transact(board, "MSP_NAME")
    return (board.CONFIG.get("name") or "").rstrip("\x00")


def write_name(board: MSPy, name: str) -> None:
    # MSP_SET_NAME only — never MSP_EEPROM_WRITE / save2eprom.
    payload = list(name.encode("utf-8"))
    msp_transact(board, "MSP_SET_NAME", payload)


def read_attitude(board: MSPy) -> tuple[float, float, float]:
    msp_transact(board, "MSP_ATTITUDE")
    roll, pitch, yaw = board.SENSOR_DATA["kinematics"]
    return float(roll), float(pitch), float(yaw)


def read_battery_v(board: MSPy) -> float:
    # Use MSP_ANALOG only. YAMSPy 0.3.3 mis-parses MSP_BATTERY_STATE on current
    # Betaflight (it skips the legacy u8 voltage byte, so every later field is
    # shifted by one and voltage reads like 606.72). Verified on hardware at H1.
    if not msp_transact(board, "MSP_ANALOG"):
        return 0.0
    return float(board.ANALOG.get("voltage") or 0.0)


def read_status(board: MSPy) -> None:
    msp_transact(board, "MSP_STATUS_EX")
    if not board.AUX_CONFIG:
        msp_transact(board, "MSP_BOXNAMES")


def battery_pct(voltage: float) -> float:
    span = config.BATTERY_V_MAX - config.BATTERY_V_MIN
    if span <= 0:
        return 0.0
    return max(0.0, min(1.0, (voltage - config.BATTERY_V_MIN) / span))


def gyro_present(board: MSPy) -> bool:
    return bool(board.CONFIG.get("activeSensors", 0) & SENSOR_GYRO)


def is_armed(board: MSPy) -> bool:
    modes = board.process_mode(board.CONFIG.get("mode", 0))
    return "ARM" in modes


def arming_disable_flags(board: MSPy) -> list[str]:
    flags = board.CONFIG.get("armingDisableFlags", 0) or 0
    return [name for name in board.process_armingDisableFlags(flags) if name]


def compute_ready(board: MSPy, voltage: float) -> bool:
    # Bench arming-disable flags (RXLOSS, MSP, THROTTLE, …) are ignored on purpose.
    return voltage > config.BATTERY_V_MIN and gyro_present(board)


def send_motors(board: MSPy, value: int) -> None:
    board.send_RAW_MOTORS([int(value)] * 8)
    # Drain ACK if present so the next command is not confused.
    try:
        handler = board.receive_msg()
        if handler:
            board.process_recv_data(handler)
    except Exception:
        pass


def motors_off() -> None:
    board = _board
    if board is None:
        return
    try:
        if not (board.conn and board.conn.is_open):
            return
        for _ in range(3):
            send_motors(board, 1000)
    except Exception as err:
        print(f"motors_off failed: {err}", file=sys.stderr)


def _signal_stop(signum, _frame) -> None:
    print(f"\nSignal {signum}: sending motors to 1000…", file=sys.stderr)
    motors_off()
    sys.exit(128 + signum)


def register_motor_safety() -> None:
    atexit.register(motors_off)
    signal.signal(signal.SIGINT, _signal_stop)
    signal.signal(signal.SIGTERM, _signal_stop)


def print_version_once(board: MSPy) -> None:
    api = board.CONFIG.get("apiVersion", "?")
    fc = board.CONFIG.get("flightControllerVersion", "?")
    ident = board.CONFIG.get("flightControllerIdentifier", "?")
    print(f"Betaflight / FC: {ident} firmware {fc}  MSP API {api}")


def cmd_read(board: MSPy) -> None:
    identify_fc(board)
    print_version_once(board)
    msp_transact(board, "MSP_BOXNAMES")
    print("Reading telemetry (Ctrl-C to stop)…")
    try:
        while True:
            roll, pitch, yaw = read_attitude(board)
            voltage = read_battery_v(board)
            pct = battery_pct(voltage)
            read_status(board)
            armed = is_armed(board)
            flags = arming_disable_flags(board)
            ready = compute_ready(board, voltage)
            name = read_name(board)
            print(
                f"roll={roll:7.1f}  pitch={pitch:7.1f}  yaw={yaw:7.1f}  "
                f"V={voltage:5.2f}  pct={pct:5.1%}  "
                f"armed={armed}  ready={ready}  name={name!r}  "
                f"arming_disable={flags or '-'}"
            )
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nStopped.")


def cmd_name(board: MSPy, new_name: str) -> None:
    identify_fc(board)
    print_version_once(board)
    before = read_name(board)
    print(f"Current name: {before!r}")
    print(f"Writing name:  {new_name!r} (no EEPROM save)")
    write_name(board, new_name)
    after = read_name(board)
    print(f"Re-read name:  {after!r}")
    if after == new_name:
        print("MATCH")
    else:
        print("MISMATCH")


def cmd_motor(board: MSPy) -> None:
    if os.environ.get("TRIAGE_MOTORS", "0") != "1":
        sys.exit(
            "Refusing motor test: set TRIAGE_MOTORS=1 in the environment "
            "(props off, drone strapped, hand on the battery lead)."
        )

    identify_fc(board)
    print_version_once(board)
    msp_transact(board, "MSP_BOXNAMES")
    read_status(board)
    voltage = read_battery_v(board)
    armed = is_armed(board)

    if armed:
        sys.exit("Refusing motor test: flight controller reports ARMED.")
    if voltage <= config.BATTERY_V_MIN:
        sys.exit(
            f"Refusing motor test: battery {voltage:.2f} V <= BATTERY_V_MIN "
            f"{config.BATTERY_V_MIN}."
        )

    print("=" * 60)
    print("WARNING: PROPS OFF. DRONE STRAPPED. Hand on the battery lead.")
    print("Physical stop is pulling the battery.")
    print("=" * 60)
    confirm = input("Type YES to run the motor blip: ").strip()
    if confirm != "YES":
        sys.exit("Aborted (confirmation was not YES).")

    register_motor_safety()
    value = min(config.MOTOR_TEST_VALUE, config.MOTOR_HARD_CAP)
    duration = float(config.MOTOR_TEST_SECONDS)
    interval = 0.1
    print(f"Motor blip: value={value} for {duration}s (re-send every {interval}s)…")

    try:
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            send_motors(board, value)
            time.sleep(interval)
    finally:
        print("Stopping motors (1000 x 3)…")
        for _ in range(3):
            send_motors(board, 1000)
        print("Done.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Betaflight USB bridge test (human-run only). Default mode: --read."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--read",
        action="store_true",
        help="Loop-print attitude, battery, armed, arming-disable flags, ready, craft name (default).",
    )
    mode.add_argument(
        "--name",
        metavar="NEWNAME",
        help="Write craft name via MSP_SET_NAME, re-read, print MATCH or MISMATCH (no EEPROM save).",
    )
    mode.add_argument(
        "--motor",
        action="store_true",
        help="Short motor blip (requires TRIAGE_MOTORS=1 and typed YES).",
    )
    parser.add_argument(
        "--port",
        default=None,
        help="Serial port (else TRIAGE_PORT / config.SERIAL_PORT, else first /dev/cu.usbmodem*).",
    )
    return parser


def main() -> None:
    global _board
    parser = build_parser()
    args = parser.parse_args()

    port = resolve_port(args.port)
    print(f"Using port: {port}")
    board = open_board(port)
    _board = board

    try:
        if args.name is not None:
            cmd_name(board, args.name)
        elif args.motor:
            cmd_motor(board)
        else:
            # --read or default
            cmd_read(board)
    finally:
        close_board(board)
        _board = None


if __name__ == "__main__":
    main()
