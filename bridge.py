"""Unit sources. S3: MockUnit only. LiveUnit comes later (no serial/yamspy yet)."""

from __future__ import annotations

import math


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
        # Slow fake tilt — advances on each read, not wall clock.
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


def _variant_from_name(name: str) -> str:
    # TRIAGE-A-001 -> A
    parts = name.split("-")
    if len(parts) >= 2 and len(parts[1]) == 1 and parts[1].isalpha():
        return parts[1].upper()
    return "A"
