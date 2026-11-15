"""Triage data models. Wire payloads use to_public(); never dataclasses.asdict."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Asset:
    name: str
    x: float
    y: float
    kind: str

    def to_public(self) -> dict:
        return {"name": self.name, "x": self.x, "y": self.y, "kind": self.kind}


@dataclass
class Track:
    id: str
    x: float
    y: float
    speed: float
    heading: float
    history: list[tuple[float, float]] = field(default_factory=list)
    registered_friendly: bool = False
    truth: str = "real"  # real | decoy | friendly — BACKEND ONLY
    waypoints: list[tuple[float, float]] = field(default_factory=list)  # BACKEND ONLY
    wp_index: int = 0  # BACKEND ONLY
    target_asset: str | None = None
    raw_score: float = 0.0
    threat_score: int = 0
    factors: list[str] = field(default_factory=list)
    label: str = "unknown"  # threat | decoy | unknown | friendly
    eta: float | None = None
    priority: int = 0
    status: str = "active"  # active | neutralized | impact | gone

    def to_public(self) -> dict:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "speed": self.speed,
            "heading": self.heading,
            "history": list(self.history),
            "registered_friendly": self.registered_friendly,
            "target_asset": self.target_asset,
            "raw_score": self.raw_score,
            "threat_score": self.threat_score,
            "factors": list(self.factors),
            "label": self.label,
            "eta": self.eta,
            "priority": self.priority,
            "status": self.status,
        }


@dataclass
class Unit:
    id: str
    variant: str
    speed: float
    max_range: float
    range: float
    cost: int
    battery_v: float
    battery_pct: float
    ready: bool
    source: str  # live | mock | sim
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    x: float = 0.0
    y: float = 0.0
    home_x: float = 0.0
    home_y: float = 0.0
    state: str = "rack"  # rack | outbound | shadowing | returning | expended
    assigned_track: str | None = None

    def to_public(self) -> dict:
        return {
            "id": self.id,
            "variant": self.variant,
            "speed": self.speed,
            "max_range": self.max_range,
            "range": self.range,
            "cost": self.cost,
            "battery_v": self.battery_v,
            "battery_pct": self.battery_pct,
            "ready": self.ready,
            "source": self.source,
            "roll": self.roll,
            "pitch": self.pitch,
            "yaw": self.yaw,
            "x": self.x,
            "y": self.y,
            "home_x": self.home_x,
            "home_y": self.home_y,
            "state": self.state,
            "assigned_track": self.assigned_track,
        }


@dataclass
class PlanLine:
    id: str
    unit_id: str
    track_id: str
    action: str  # launch_early | engage | best_effort | return
    reason: str
    approved: bool = False

    def to_public(self) -> dict:
        return {
            "id": self.id,
            "unit_id": self.unit_id,
            "track_id": self.track_id,
            "action": self.action,
            "reason": self.reason,
            "approved": self.approved,
        }


@dataclass
class Event:
    t: float
    kind: str
    msg: str

    def to_public(self) -> dict:
        return {"t": self.t, "kind": self.kind, "msg": self.msg}
