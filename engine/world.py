"""World: holds state, step(dt), handle_command. No wall clock. No hardware."""

from __future__ import annotations

import math

from models import Event, Track
from scenarios import get_scenario

from engine.sim import move_track


class World:
    def __init__(self) -> None:
        self.t: float = 0.0
        self.scenario: str | None = None
        self.phase: str = "idle"  # idle | live | paused | ended
        self.replay: bool = False
        self.assets: list = []
        self.tracks: list[Track] = []
        self.units: list = []
        self.plan: list = []
        self.events: list[Event] = []
        self.gaps: list = []
        self.alerts: list[str] = []
        self._spawns: list[dict] = []
        self._spawned_ids: set[str] = set()
        self._kept_variants: dict[str, str] = {}

    def load_scenario(self, name: str) -> None:
        data = get_scenario(name)
        # Preserve variants across load (7.5).
        kept = dict(self._kept_variants)
        for u in self.units:
            kept[u.id] = u.variant
        self._kept_variants = kept

        self.t = 0.0
        self.scenario = data["name"]
        self.phase = "idle"
        self.replay = bool(data["replay"])
        self.assets = data["assets"]
        self.tracks = []
        self.plan = []
        self.events = []
        self.gaps = []
        self.alerts = []
        self._spawns = sorted(data["spawns"], key=lambda s: (s["t"], s["id"]))
        self._spawned_ids = set()
        self.units = data["units"]
        self._apply_kept_variants()

    def _apply_kept_variants(self) -> None:
        import config

        for u in self.units:
            variant = self._kept_variants.get(u.id, u.variant)
            if variant not in config.VARIANTS:
                continue
            spec = config.VARIANTS[variant]
            u.variant = variant
            u.speed = spec["speed"]
            u.max_range = spec["max_range"]
            u.cost = spec["cost"]
            u.range = u.max_range * u.battery_pct

    def reset(self) -> list:
        """Reload current scenario. Variants kept. Returns hardware effects."""
        name = self.scenario
        if name is None:
            return [("motors_off",)]
        self.load_scenario(name)
        return [("motors_off",)]

    def handle_command(self, cmd: dict) -> list:
        """Apply a command. Returns hardware effects for main.py to run."""
        if not isinstance(cmd, dict):
            return []
        ctype = cmd.get("type")
        if ctype == "load_scenario":
            name = cmd.get("name")
            if isinstance(name, str) and name:
                self.load_scenario(name)
            return []
        if ctype == "start":
            if self.phase in ("idle", "paused", "ended"):
                if self.phase == "ended":
                    # Starting from ended requires a reset/load first; ignore.
                    if self.scenario is None:
                        return []
                if self.phase == "idle" or self.phase == "paused":
                    self.phase = "live"
            return []
        if ctype == "pause":
            if self.phase == "live":
                self.phase = "paused"
            return []
        if ctype == "reset":
            return self.reset()
        if ctype == "approve":
            # S1: no planner; approvals are no-ops.
            return []
        if ctype == "swap_variant":
            # Implemented in a later gate; refuse during live here for safety.
            return []
        if ctype == "set_mock":
            return []
        return []

    def step(self, dt: float) -> None:
        """Advance exactly dt seconds of sim time. Never reads the wall clock."""
        if self.phase != "live":
            return

        self.t = self.t + dt
        self._spawn_due_tracks()
        for track in self.tracks:
            if track.status == "active":
                move_track(track, dt)

        if self._scenario_complete():
            self.phase = "ended"

    def _spawn_due_tracks(self) -> None:
        for spawn in self._spawns:
            sid = spawn["id"]
            if sid in self._spawned_ids:
                continue
            if self.t + 1e-12 < spawn["t"]:
                continue
            self._spawned_ids.add(sid)
            wps = [tuple(p) for p in spawn["waypoints"]]
            x0, y0 = wps[0]
            heading = 0.0
            if len(wps) >= 2:
                heading = math.atan2(wps[1][1] - y0, wps[1][0] - x0)
            track = Track(
                id=sid,
                x=x0,
                y=y0,
                speed=float(spawn["speed"]),
                heading=heading,
                history=[(x0, y0)],
                registered_friendly=bool(spawn.get("registered_friendly", False)),
                truth=spawn["truth"],
                waypoints=wps,
                wp_index=1 if len(wps) > 1 else 0,
                target_asset=spawn.get("target_asset"),
                status="active",
            )
            # If only one waypoint and we already sit on it, index points past start.
            if len(wps) == 1:
                track.wp_index = 0
            self.tracks.append(track)
            self.events.append(
                Event(t=self.t, kind="contact", msg=f"contact {sid}")
            )

    def _scenario_complete(self) -> bool:
        if len(self._spawned_ids) < len(self._spawns):
            return False
        if any(tr.status == "active" for tr in self.tracks):
            return False
        if any(u.state != "rack" for u in self.units):
            return False
        return True

    def to_public(self) -> dict:
        return {
            "t": self.t,
            "scenario": self.scenario,
            "phase": self.phase,
            "replay": self.replay,
            "assets": [a.to_public() for a in self.assets],
            "tracks": [t.to_public() for t in self.tracks],
            "units": [u.to_public() for u in self.units],
            "plan": [p.to_public() for p in self.plan],
            "events": [e.to_public() for e in self.events[-50:]],
            "gaps": list(self.gaps),
            "alerts": list(self.alerts),
        }
