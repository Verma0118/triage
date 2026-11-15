"""Scenario definitions: assets, rack units, timed track spawns."""

from __future__ import annotations

import math

import config
from models import Asset, Unit


def _unit(uid: str, x: float, y: float, source: str, variant: str = "A") -> Unit:
    v = config.VARIANTS[variant]
    battery_pct = 1.0
    return Unit(
        id=uid,
        variant=variant,
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
    # Compound around the hub. High-value kinds: housing, generator, clinic.
    return [
        Asset("housing", 500.0, 350.0, "housing"),      # hub HV
        Asset("generator", 585.0, 270.0, "generator"),  # NE HV
        Asset("clinic", 620.0, 380.0, "clinic"),        # E of hub HV — on-screen with slice
        Asset("comms", 400.0, 255.0, "comms"),          # NW
        Asset("fuel", 605.0, 425.0, "fuel"),            # SE
        Asset("radar", 640.0, 250.0, "radar"),          # NE — on-screen with slice
        Asset("parking", 655.0, 520.0, "parking"),      # further SE apron
    ]


def _juniper_units() -> list[Unit]:
    # Docked in compact rack building (slot centers match static map).
    # Keep unit-to-track proposal distances under 600 for Variant A at 50% battery.
    return [
        _unit("U1", 261.0, 421.0, "mock"),
        _unit("U2", 297.0, 421.0, "sim"),
        # The rack's single Variant B: the only unit fast enough for track B.
        # It is expended there, so the later fast threat finds no B left and the
        # gap reads "only Variant B unit already expended".
        _unit("U3", 333.0, 421.0, "sim", variant="B"),
        _unit("U4", 369.0, 421.0, "sim"),
    ]



def _decoy_waypoints() -> list[tuple[float, float]]:
    """Straight first leg ~5 s at speed 9, then 2–3 s loiter legs with ≥90° turns.

    First leg is not aimed inside 20° of high-value or primary sites, so the
    track reads UNKNOWN while it is flying straight. Once it starts loitering
    the heading variance climbs and it resolves to DECOY.

    Timings are tight on purpose: the whole demo has to fit a 60 second film.
    """
    speed = 9.0
    spawn_t = 1.0
    straight_s = 5.0
    # ~230 from the rack, so the interceptor reaches standoff before the track
    # resolves to DECOY: the operator sees it arrive, hold, then be recalled.
    start = (120.0, 240.0)
    # Fly due west (~5 s) — clears every asset by >150 degrees.
    leg1_end = (start[0] - speed * straight_s, start[1])  # (75, 240)

    # Verify cone constraint at definition time (guards against accidental edits).
    heading = math.pi  # west
    assets = {a.name: a for a in _juniper_assets()}
    for name in ("housing", "generator", "clinic", "comms", "fuel", "radar"):
        a = assets[name]
        to_a = math.atan2(a.y - start[1], a.x - start[0])
        diff = abs((to_a - heading + math.pi) % (2 * math.pi) - math.pi)
        assert math.degrees(diff) > 20.0, f"decoy first leg aims at {name}"


    # Loiter box: N/W/S/E legs of 2–3 s with 90° turns until past t=58, then short end.
    wps: list[tuple[float, float]] = [start, leg1_end]
    x, y = leg1_end
    # Every loiter leg must point away from the outpost. An eastward leg aims
    # back at the site and scores heading points, which would flip the track out
    # of DECOY mid-loiter. N / W / S / W drifts the decoy off the west edge and
    # still turns >=90 degrees between legs.
    loiter_dirs = [
        (0.0, 1.0),    # north
        (-1.0, 0.0),   # west
        (0.0, -1.0),   # south
        (-1.0, 0.0),   # west
    ]
    for dx, dy in loiter_dirs:
        h = math.atan2(dy, dx)
        for name in ("housing", "generator", "clinic", "comms", "fuel", "radar", "parking"):
            a = assets[name]
            to_a = math.atan2(a.y - leg1_end[1], a.x - leg1_end[0])
            d = abs((to_a - h + math.pi) % (2 * math.pi) - math.pi)
            assert math.degrees(d) > 20.0, f"decoy loiter leg aims at {name}"
    t_end = spawn_t + straight_s  # ~6
    i = 0
    while t_end < 20.0:
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
        (500.0, 60.0),
        (420.0, 280.0),
        (300.0, 421.0),  # rack/base — inside map
    ]


def juniper_night1() -> dict:
    housing = (500.0, 350.0)
    parking = (655.0, 520.0)
    # B: straight at housing from 400 west (14.3 s at speed 28).
    b_start = (housing[0] - 400.0, housing[1])
    # C: straight at parking from 560 west (14 s at speed 40) — long enough for
    # the best-effort interceptor to visibly chase and fall behind.
    c_start = (parking[0] - 560.0, parking[1])

    return {
        "name": "juniper_night1",
        "replay": False,
        "assets": _juniper_assets(),
        "units": _juniper_units(),
        "spawns": [
            {
                "t": 1.0,
                "id": "A",
                "speed": 9.0,
                "truth": "decoy",
                "registered_friendly": False,
                "target_asset": None,
                "waypoints": _decoy_waypoints(),
            },
            {
                "t": 2.0,
                "id": "B",
                # 28 needs a unit above 33.6: Variant A (30) cannot take this,
                # only the rack's single Variant B (60) can.
                "speed": 28.0,
                "truth": "real",
                "registered_friendly": False,
                "target_asset": "housing",
                "waypoints": [b_start, housing],
            },
            {
                "t": 22.0,
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
    comms = (400.0, 255.0)
    # Fast threat at comms, 480 west at speed 40: ETA 12 s, which still leaves
    # a comfortable margin between the proposal and impact.
    # Approach along rack latitude so unit-to-track at proposal stays under 600.
    c_start = (comms[0] - 480.0, 421.0)  # west approach along rack lat; ETA = 12.0 s
    units = [
        _unit("U1", 261.0, 421.0, "mock"),
        _unit("U2", 297.0, 421.0, "sim"),
        _unit("U3", 333.0, 421.0, "sim"),
        _unit("U4", 369.0, 421.0, "sim"),
    ]
    return {
        "name": "juniper_night2",
        "replay": False,
        "assets": _juniper_assets(),
        "units": units,
        "spawns": [
            {
                "t": 1.0,
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
    housing = (500.0, 350.0)
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
                    (500.0, 40.0),
                    (500.0, 200.0),
                    (440.0, 350.0),
                    (300.0, 350.0),
                    (-20.0, 350.0),
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
                    (500.0, 680.0),
                    housing,
                ],
            },
        ],
    }


def _short_decoy_waypoints() -> list[tuple[float, float]]:
    """Faster decoy for live demos: short straight, brief loiter, gone ~t=28."""
    speed = 11.0
    spawn_t = 2.0
    straight_s = 7.0
    # On-map; east leg must stay outside 20° of site bearings.
    start = (200.0, 70.0)
    leg1_end = (start[0] + speed * straight_s, start[1])
    heading = 0.0
    assets = {a.name: a for a in _juniper_assets()}
    for name in ("housing", "generator", "clinic", "comms", "fuel", "radar"):
        a = assets[name]
        to_a = math.atan2(a.y - start[1], a.x - start[0])
        diff = abs((to_a - heading + math.pi) % (2 * math.pi) - math.pi)
        assert math.degrees(diff) > 20.0, f"short decoy aims at {name}"
    wps: list[tuple[float, float]] = [start, leg1_end]
    x, y = leg1_end
    dirs = [(0.0, 1.0), (-1.0, 0.0), (0.0, -1.0), (1.0, 0.0)]
    t_end = spawn_t + straight_s
    i = 0
    while t_end < 26.0:
        dx, dy = dirs[i % 4]
        secs = 2.0
        x = x + dx * speed * secs
        y = y + dy * speed * secs
        wps.append((x, y))
        t_end += secs
        i += 1
    dx, dy = dirs[i % 4]
    wps.append((x + dx * speed * 2.0, y + dy * speed * 2.0))
    return wps


def hot_inbound() -> dict:
    """~20 s: friendly in, then a real threat at housing — starts on-map."""
    housing = (500.0, 350.0)
    # Visible immediately (inside viewBox), ~12 s to impact at speed 22.
    b_start = (220.0, housing[1])
    return {
        "name": "hot_inbound",
        "replay": False,
        "assets": _juniper_assets(),
        "units": _juniper_units(),
        "spawns": [
            {
                "t": 0.5,
                "id": "F1",
                "speed": 18.0,
                "truth": "friendly",
                "registered_friendly": True,
                "target_asset": None,
                "waypoints": _friendly_waypoints(),
            },
            {
                "t": 1.5,
                "id": "B",
                "speed": 22.0,
                "truth": "real",
                "registered_friendly": False,
                "target_asset": "housing",
                "waypoints": [b_start, housing],
            },
        ],
    }


def two_front() -> dict:
    """~30 s: decoy + real threat overlapping; both start on-map."""
    housing = (500.0, 350.0)
    b_start = (200.0, housing[1] + 15.0)
    return {
        "name": "two_front",
        "replay": False,
        "assets": _juniper_assets(),
        "units": _juniper_units(),
        "spawns": [
            {
                "t": 1.0,
                "id": "A",
                "speed": 11.0,
                "truth": "decoy",
                "registered_friendly": False,
                "target_asset": None,
                "waypoints": _short_decoy_waypoints(),
            },
            {
                "t": 2.5,
                "id": "B",
                "speed": 20.0,
                "truth": "real",
                "registered_friendly": False,
                "target_asset": "housing",
                "waypoints": [b_start, housing],
            },
        ],
    }


def gap_rush() -> dict:
    """~15 s: fast threat at parking — gap story, starts on the visible map."""
    parking = (655.0, 520.0)
    # On-map west approach (not off-screen). Still too fast for Variant A.
    c_start = (180.0, 500.0)
    return {
        "name": "gap_rush",
        "replay": False,
        "assets": _juniper_assets(),
        "units": _juniper_units(),
        "spawns": [
            {
                "t": 0.8,
                "id": "C",
                "speed": 40.0,
                "truth": "real",
                "registered_friendly": False,
                "target_asset": "parking",
                "waypoints": [c_start, parking],
            },
        ],
    }


def clinic_raid() -> dict:
    """~15 s: real threat at high-value clinic — starts on-map from the south."""
    clinic = (620.0, 380.0)
    start = (600.0, 620.0)
    return {
        "name": "clinic_raid",
        "replay": False,
        "assets": _juniper_assets(),
        "units": _juniper_units(),
        "spawns": [
            {
                "t": 0.8,
                "id": "T1",
                "speed": 22.0,
                "truth": "real",
                "registered_friendly": False,
                "target_asset": "clinic",
                "waypoints": [start, clinic],
            },
        ],
    }


def comms_push() -> dict:
    """~15 s: threat at comms — on-map west spawn (demo stand-in for night2)."""
    comms = (400.0, 255.0)
    # Visible left side; unit-to-track stays under 600 for rack units.
    c_start = (120.0, 300.0)
    return {
        "name": "comms_push",
        "replay": False,
        "assets": _juniper_assets(),
        "units": _juniper_units(),
        "spawns": [
            {
                "t": 0.8,
                "id": "T1",
                "speed": 28.0,
                "truth": "real",
                "registered_friendly": False,
                "target_asset": "comms",
                "waypoints": [c_start, comms],
            },
        ],
    }


SCENARIOS: dict[str, dict] = {
    "juniper_night1": juniper_night1(),
    "juniper_night2": juniper_night2(),
    "tower22": tower22(),
    "hot_inbound": hot_inbound(),
    "two_front": two_front(),
    "gap_rush": gap_rush(),
    "clinic_raid": clinic_raid(),
    "comms_push": comms_push(),
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
