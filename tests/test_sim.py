"""S1: sim, world, scenarios — tracks only, no scoring/planner."""

import ast
import importlib
import inspect
import math
from pathlib import Path

import config
from engine.world import World
from scenarios import SCENARIOS


REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = REPO_ROOT / "engine"
FORBIDDEN_ENGINE_IMPORTS = {"fastapi", "serial", "yamspy", "bridge"}
WALL_CLOCK_NAMES = {
    "time",
    "sleep",
    "monotonic",
    "perf_counter",
    "process_time",
    "datetime",
    "now",
    "utcnow",
}


def _run_night1_until_ended(max_ticks: int = 2000) -> list[dict]:
    """Advance juniper_night1 with no approvals; return a timeline of snapshots."""
    world = World()
    world.load_scenario("juniper_night1")
    world.handle_command({"type": "start"})
    timeline: list[dict] = []
    for _ in range(max_ticks):
        world.step(config.DT)
        timeline.append(_snapshot(world))
        if world.phase == "ended":
            break
    assert world.phase == "ended", "night1 did not end within tick budget"
    return timeline


def _snapshot(world: World) -> dict:
    tracks = tuple(
        (
            t.id,
            round(t.x, 6),
            round(t.y, 6),
            round(t.speed, 6),
            round(t.heading, 6),
            t.status,
            t.truth,
        )
        for t in sorted(world.tracks, key=lambda tr: tr.id)
    )
    events = tuple((e.t, e.kind, e.msg) for e in world.events)
    units = tuple((u.id, u.state, round(u.x, 6), round(u.y, 6)) for u in world.units)
    return {
        "t": round(world.t, 6),
        "phase": world.phase,
        "tracks": tracks,
        "events": events,
        "units": units,
    }


def _final_status_by_id(timeline: list[dict]) -> dict[str, str]:
    last = timeline[-1]
    return {tid: status for tid, _x, _y, _sp, _hd, status, _truth in last["tracks"]}


def _spawn_times(timeline: list[dict]) -> dict[str, float]:
    first_seen: dict[str, float] = {}
    for snap in timeline:
        for tid, *_rest in snap["tracks"]:
            if tid not in first_seen:
                first_seen[tid] = snap["t"]
    return first_seen


def test_night1_twice_identical_timelines():
    a = _run_night1_until_ended()
    b = _run_night1_until_ended()
    assert a == b


def test_tracks_spawn_at_scenario_times():
    timeline = _run_night1_until_ended()
    spawns = _spawn_times(timeline)
    # Spawns happen on the tick that crosses scenario time (t after step).
    assert spawns["F1"] == pytest_approx_tick(2.0)
    assert spawns["A"] == pytest_approx_tick(5.0)
    assert spawns["B"] == pytest_approx_tick(8.0)
    assert spawns["C"] == pytest_approx_tick(50.0)


def pytest_approx_tick(spawn_t: float) -> float:
    """First tick at or after spawn_t when stepping by DT from 0."""
    ticks = math.ceil(spawn_t / config.DT - 1e-12)
    return round(ticks * config.DT, 6)


def test_no_approvals_b_impacts_housing_c_impacts_parking():
    timeline = _run_night1_until_ended()
    statuses = _final_status_by_id(timeline)
    assert statuses["B"] == "impact"
    assert statuses["C"] == "impact"

    world = World()
    world.load_scenario("juniper_night1")
    housing = next(a for a in world.assets if a.kind == "housing")
    parking = next(a for a in world.assets if a.kind == "parking")

    b_impact = next(
        snap
        for snap in timeline
        if any(tid == "B" and status == "impact" for tid, *_r, status, _t in snap["tracks"])
    )
    c_impact = next(
        snap
        for snap in timeline
        if any(tid == "C" and status == "impact" for tid, *_r, status, _t in snap["tracks"])
    )
    b_pos = next((x, y) for tid, x, y, *_r in b_impact["tracks"] if tid == "B")
    c_pos = next((x, y) for tid, x, y, *_r in c_impact["tracks"] if tid == "C")
    assert math.hypot(b_pos[0] - housing.x, b_pos[1] - housing.y) < config.INTERCEPT_RADIUS
    assert math.hypot(c_pos[0] - parking.x, c_pos[1] - parking.y) < config.INTERCEPT_RADIUS


def test_friendly_and_decoy_end_gone():
    timeline = _run_night1_until_ended()
    statuses = _final_status_by_id(timeline)
    assert statuses["F1"] == "gone"
    assert statuses["A"] == "gone"


def test_world_step_has_no_wall_clock_calls():
    source = inspect.getsource(World.step)
    # Parse as a class body so method indentation is valid.
    tree = ast.parse("class _W:\n" + source)
    hits: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_Attribute(self, node: ast.Attribute) -> None:
            if isinstance(node.attr, str) and node.attr in WALL_CLOCK_NAMES:
                hits.append(node.attr)
            self.generic_visit(node)

        def visit_Name(self, node: ast.Name) -> None:
            if node.id in {"time", "datetime"}:
                hits.append(node.id)
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in WALL_CLOCK_NAMES:
                hits.append(func.attr)
            elif isinstance(func, ast.Name) and func.id in WALL_CLOCK_NAMES:
                hits.append(func.id)
            self.generic_visit(node)

    Visitor().visit(tree)
    assert hits == [], f"World.step uses wall-clock APIs: {hits}"


def test_engine_imports_no_fastapi_serial_bridge():
    offenders: list[str] = []
    for path in sorted(ENGINE_DIR.rglob("*.py")):
        mod_name = ".".join(path.relative_to(REPO_ROOT).with_suffix("").parts)
        mod = importlib.import_module(mod_name)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name in FORBIDDEN_ENGINE_IMPORTS:
                    offenders.append(f"{path.name}: import {name}")
        # also ensure loaded module does not pull them in transitively at top level
        for name in FORBIDDEN_ENGINE_IMPORTS:
            if name in getattr(mod, "__dict__", {}):
                offenders.append(f"{mod_name}: binds {name}")
    assert offenders == [], f"Forbidden engine imports: {offenders}"


def test_night1_scenario_speeds_and_geometry():
    """Section 9 constraints: speeds, B distance ~620, decoy first-leg cone, unit range."""
    scenario = SCENARIOS["juniper_night1"]
    assets = {a.name: a for a in scenario["assets"]}
    spawns = {s["id"]: s for s in scenario["spawns"]}

    assert spawns["A"]["speed"] == 9
    assert spawns["B"]["speed"] == 18
    assert spawns["C"]["speed"] == 40
    assert spawns["F1"]["speed"] == 15
    assert spawns["A"]["truth"] == "decoy"
    assert spawns["B"]["truth"] == "real"
    assert spawns["C"]["truth"] == "real"
    assert spawns["F1"]["truth"] == "friendly"
    assert spawns["F1"]["registered_friendly"] is True

    housing = assets["housing"]
    parking = assets["parking"]
    b0 = spawns["B"]["waypoints"][0]
    b_dist = math.hypot(b0[0] - housing.x, b0[1] - housing.y)
    assert 600 <= b_dist <= 640, f"B should start ~620 from housing, got {b_dist}"

    # C aims at parking (last waypoint near parking).
    c_last = spawns["C"]["waypoints"][-1]
    assert math.hypot(c_last[0] - parking.x, c_last[1] - parking.y) < 1.0

    # Decoy first leg ~12 s, not aimed inside 20 deg of HVA assets.
    a_wps = spawns["A"]["waypoints"]
    assert len(a_wps) >= 2
    leg_len = math.hypot(a_wps[1][0] - a_wps[0][0], a_wps[1][1] - a_wps[0][1])
    assert 9 * 11.5 <= leg_len <= 9 * 12.5
    heading = math.atan2(a_wps[1][1] - a_wps[0][1], a_wps[1][0] - a_wps[0][0])
    hva = ("housing", "generator", "comms", "fuel")
    for name in hva:
        asset = assets[name]
        to_asset = math.atan2(asset.y - a_wps[0][1], asset.x - a_wps[0][0])
        diff = abs((to_asset - heading + math.pi) % (2 * math.pi) - math.pi)
        assert math.degrees(diff) > 20, f"decoy first leg aims within 20° of {name}"

    # Unit-to-track distance at spawn under 600 for every spawn.
    for spawn in scenario["spawns"]:
        sx, sy = spawn["waypoints"][0]
        for unit in scenario["units"]:
            d = math.hypot(unit.x - sx, unit.y - sy)
            assert d < 600, f"{unit.id} to {spawn['id']} is {d} (>= 600)"


def test_all_three_scenarios_load():
    world = World()
    for name in ("juniper_night1", "juniper_night2", "tower22"):
        world.load_scenario(name)
        assert world.scenario == name
        assert world.phase == "idle"
        assert len(world.units) == 4
        assert world.tracks == []
    assert SCENARIOS["tower22"]["replay"] is True
    assert SCENARIOS["juniper_night1"]["replay"] is False
    assert SCENARIOS["juniper_night2"]["replay"] is False


def test_units_stay_on_rack_without_approvals():
    timeline = _run_night1_until_ended()
    for snap in timeline:
        for _uid, state, _x, _y in snap["units"]:
            assert state == "rack"


def test_to_public_omits_truth_and_waypoints():
    from models import Track

    track = Track(
        id="A",
        x=1.0,
        y=2.0,
        speed=9.0,
        heading=0.0,
        history=[(1.0, 2.0)],
        registered_friendly=False,
        truth="decoy",
        waypoints=[(1.0, 2.0), (10.0, 2.0)],
        wp_index=0,
        target_asset=None,
        raw_score=0.0,
        threat_score=0,
        factors=[],
        label="unknown",
        eta=None,
        priority=0,
        status="active",
    )
    pub = track.to_public()
    assert "truth" not in pub
    assert "waypoints" not in pub
    assert "wp_index" not in pub
    assert pub["id"] == "A"
    assert pub["x"] == 1.0
