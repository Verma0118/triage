"""Scenario definitions: assets, rack units, timed track spawns."""

from __future__ import annotations

import math

import config
from models import Asset, Unit


def _unit(uid: str, x: float, y: float, source: str) -> Unit:
    v = config.VARIANTS["A"]
    battery_pct = 1.0
    return Unit(
        id=uid,
        variant="A",
        speed=v["speed"],
        max_range=v["max_range"],
        range=v["max_range"] * battery_pct,
        cost=v["cost"],
        battery_v=15.8,
        battery_pct=battery_pct,
        ready=True,
        source=source,
        x=x,
        y=y,
        home_x=x,
        home_y=y,
        state="rack",
        assigned_track=None,
    )


def _juniper_assets() -> list[Asset]:
    # Spread enough that map labels do not collide (housing/comms were stacking).
    return [
        Asset("housing", 720.0, 360.0, "housing"),
        Asset("generator", 780.0, 280.0, "generator"),
        Asset("comms", 640.0, 260.0, "comms"),
        Asset("fuel", 800.0, 400.0, "fuel"),
        Asset("parking", 880.0, 540.0, "parking"),
    ]


def _juniper_units() -> list[Unit]:
    # Docked in the interceptor rack bay (map pad ~488–620 x, pads at y≈405).
    # Keep unit-to-track proposal distances under 600 for Variant A at 50% battery.
    return [
        _unit("U1", 500.0, 405.0, "mock"),
        _unit("U2", 536.0, 405.0, "sim"),
        _unit("U3", 572.0, 405.0, "sim"),
        _unit("U4", 608.0, 405.0, "sim"),
    ]


def _decoy_waypoints() -> list[tuple[float, float]]:
    """Straight first leg ~12 s at speed 9, then 2–3 s loiter legs with ≥90° turns.

    First leg is not aimed inside 20° of housing/generator/comms/fuel.
    Keeps loitering until at least t=58 (spawn t=5 + 12 s straight + loiter),
    then ends gone on a short final leg (≤3 s). No long straight exit.
    """
    speed = 9.0
    spawn_t = 5.0
    straight_s = 12.0
    # Close enough to the rack that every unit-to-track distance is < 600.
    start = (210.0, 50.0)
    # Fly due east (~12 s).
    leg1_end = (start[0] + speed * straight_s, start[1])  # (308, 50)

    # Verify cone constraint at definition time (guards against accidental edits).
    heading = 0.0  # east
    assets = {a.name: a for a in _juniper_assets()}
    for name in ("housing", "generator", "comms", "fuel"):
        a = assets[name]
        to_a = math.atan2(a.y - start[1], a.x - start[0])
        diff = abs((to_a - heading + math.pi) % (2 * math.pi) - math.pi)
        assert math.degrees(diff) > 20.0, f"decoy first leg aims at {name}"

    # Loiter box: N/W/S/E legs of 2–3 s with 90° turns until past t=58, then short end.
    wps: list[tuple[float, float]] = [start, leg1_end]
    x, y = leg1_end
    loiter_dirs = [
        (0.0, 1.0),
        (-1.0, 0.0),
        (0.0, -1.0),
        (1.0, 0.0),
    ]
    t_end = spawn_t + straight_s  # ~17
    i = 0
    while t_end < 58.0:
        dx, dy = loiter_dirs[i % 4]
        secs = 2.5 if (i % 5) != 4 else 3.0
        x = x + dx * speed * secs
        y = y + dy * speed * secs
        wps.append((x, y))
        t_end += secs
        i += 1
    # Short final leg (≤3 s) then gone — no long straight exit.
    dx, dy = loiter_dirs[i % 4]
    secs = 2.5
    x = x + dx * speed * secs
    y = y + dy * speed * secs
    wps.append((x, y))
    return wps


def _friendly_waypoints() -> list[tuple[float, float]]:
    """Registered friendly returning to rack/base inside the map; gone on arrival."""
    # From north of the outpost, approach the rack/base and end there (not off-map).
    return [
        (500.0, 80.0),
        (560.0, 300.0),
        (600.0, 400.0),  # rack/base — inside map
    ]


def juniper_night1() -> dict:
    housing = (720.0, 360.0)
    parking = (880.0, 540.0)
    # B: straight at housing from ~620 west.
    b_start = (housing[0] - 620.0, housing[1])
    # C: straight at parking from the west.
    c_start = (parking[0] - 600.0, parking[1])

    return {
        "name": "juniper_night1",
        "replay": False,
        "assets": _juniper_assets(),
        "units": _juniper_units(),
        "spawns": [
            {
                "t": 2.0,
                "id": "F1",
                "speed": 15.0,
                "truth": "friendly",
                "registered_friendly": True,
                "target_asset": None,
                "waypoints": _friendly_waypoints(),
            },
            {
                "t": 5.0,
                "id": "A",
                "speed": 9.0,
                "truth": "decoy",
                "registered_friendly": False,
                "target_asset": None,
                "waypoints": _decoy_waypoints(),
            },
            {
                "t": 8.0,
                "id": "B",
                "speed": 18.0,
                "truth": "real",
                "registered_friendly": False,
                "target_asset": "housing",
                "waypoints": [b_start, housing],
            },
            {
                "t": 50.0,
                "id": "C",
                "speed": 40.0,
                "truth": "real",
                "registered_friendly": False,
                "target_asset": "parking",
                "waypoints": [c_start, parking],
            },
        ],
    }


def juniper_night2() -> dict:
    comms = (640.0, 260.0)
    # Fast threat at comms. ETA >= 20 s (dist >= 800 at speed 40).
    # Approach along rack latitude so unit-to-track at proposal stays under 600.
    c_start = (comms[0] - 800.0, 413.0)  # (-160, 413); ETA = 20.0 s
    units = [
        _unit("U1", 500.0, 405.0, "mock"),
        _unit("U2", 536.0, 405.0, "sim"),
        _unit("U3", 572.0, 405.0, "sim"),
        _unit("U4", 608.0, 405.0, "sim"),
    ]
    return {
        "name": "juniper_night2",
        "replay": False,
        "assets": _juniper_assets(),
        "units": units,
        "spawns": [
            {
                "t": 3.0,
                "id": "T1",
                "speed": 40.0,
                "truth": "real",
                "registered_friendly": False,
                "target_asset": "comms",
                "waypoints": [c_start, comms],
            },
        ],
    }


def tower22() -> dict:
    housing = (720.0, 360.0)
    return {
        "name": "tower22",
        "replay": True,
        "assets": _juniper_assets(),
        "units": _juniper_units(),
        "spawns": [
            {
                "t": 2.0,
                "id": "F1",
                "speed": 15.0,
                "truth": "friendly",
                "registered_friendly": True,
                "target_asset": None,
                "waypoints": [
                    (720.0, 40.0),
                    (720.0, 200.0),
                    (660.0, 360.0),
                    (500.0, 360.0),
                    (-20.0, 360.0),
                ],
            },
            {
                "t": 2.0,
                "id": "T1",
                "speed": 12.0,
                "truth": "real",
                "registered_friendly": False,
                "target_asset": "housing",
                "waypoints": [
                    (720.0, 680.0),
                    housing,
                ],
            },
        ],
    }


SCENARIOS: dict[str, dict] = {
    "juniper_night1": juniper_night1(),
    "juniper_night2": juniper_night2(),
    "tower22": tower22(),
}


def get_scenario(name: str) -> dict:
    if name not in SCENARIOS:
        raise KeyError(f"unknown scenario: {name}")
    # Return a fresh copy so load/reset do not mutate the template.
    return _clone_scenario(SCENARIOS[name])


def _clone_scenario(src: dict) -> dict:
    return {
        "name": src["name"],
        "replay": src["replay"],
        "assets": [
            Asset(a.name, a.x, a.y, a.kind) for a in src["assets"]
        ],
        "units": [
            Unit(
                id=u.id,
                variant=u.variant,
                speed=u.speed,
                max_range=u.max_range,
                range=u.range,
                cost=u.cost,
                battery_v=u.battery_v,
                battery_pct=u.battery_pct,
                ready=u.ready,
                source=u.source,
                roll=u.roll,
                pitch=u.pitch,
                yaw=u.yaw,
                x=u.x,
                y=u.y,
                home_x=u.home_x,
                home_y=u.home_y,
                state=u.state,
                assigned_track=u.assigned_track,
            )
            for u in src["units"]
        ],
        "spawns": [
            {
                **spawn,
                "waypoints": list(spawn["waypoints"]),
            }
            for spawn in src["spawns"]
        ],
    }
