"""S6 / S6.1: capability gap, best_effort, shelter, swap, gap_brief, cards."""

from __future__ import annotations

import math

import config
import main
from bridge import MockUnit
from engine.world import World
from fastapi.testclient import TestClient
from main import app, gap_brief_text


def _approve_delay_run(
    world: World, delay: float = 2.0, mock: MockUnit | None = None
) -> World:
    if world.phase != "live":
        world.handle_command({"type": "start"})
    first_seen: dict[str, float] = {}
    for _ in range(4000):
        if mock is not None:
            world.apply_u1_snapshot(mock.read())
        world.step(config.DT)
        for line in world.plan:
            if line.approved:
                continue
            if line.id not in first_seen:
                first_seen[line.id] = world.t
            if world.t - first_seen[line.id] + 1e-12 >= delay:
                world.handle_command({"type": "approve", "line_ids": [line.id]})
        if world.phase == "ended":
            break
    return world


def _night1_to_ended(mock: MockUnit | None = None) -> World:
    world = World()
    world.load_scenario("juniper_night1")
    return _approve_delay_run(world, 2.0, mock=mock or MockUnit())


def test_night1_c_gap_best_effort_shelter_miss_impact():
    world = _night1_to_ended()
    c = next(t for t in world.tracks if t.id == "C")
    assert c.status == "impact"
    assert all(t.status != "neutralized" or t.id != "C" for t in world.tracks)

    gap_events = [e for e in world.events if e.kind == "gap"]
    assert len(gap_events) == 1
    fast = [g for g in world.gaps if g.get("gap_type") == "fast_threat"]
    assert len(fast) == 1
    assert fast[0].get("track_id") == "C"

    assert any(e.kind == "plan" and "best_effort" in e.msg for e in world.events)
    assert any("parking" in a.lower() and "shelter" in a.lower() for a in world.alerts)
    assert any(e.kind == "miss" for e in world.events)


def test_swap_refused_live_works_ended():
    world = World()
    world.load_scenario("juniper_night1")
    world.handle_command({"type": "start"})
    world.step(config.DT)
    assert world.phase == "live"
    effects = world.handle_command(
        {"type": "swap_variant", "unit_id": "U1", "variant": "B"}
    )
    assert effects == []
    assert next(u for u in world.units if u.id == "U1").variant == "A"

    world = _night1_to_ended()
    assert world.phase == "ended"
    effects = world.handle_command(
        {"type": "swap_variant", "unit_id": "U1", "variant": "B"}
    )
    assert ("set_name", "U1", "TRIAGE-B-001") in effects
    u1 = next(u for u in world.units if u.id == "U1")
    spec = config.VARIANTS["B"]
    assert u1.variant == "B"
    assert u1.speed == spec["speed"]
    assert u1.max_range == spec["max_range"]
    assert u1.cost == spec["cost"]
    assert any(e.kind == "swap" for e in world.events)


def test_night2_after_swap_u1_engages():
    world = _night1_to_ended()
    world.handle_command({"type": "swap_variant", "unit_id": "U1", "variant": "B"})
    world.load_scenario("juniper_night2")
    assert next(u for u in world.units if u.id == "U1").variant == "B"
    _approve_delay_run(world, 2.0, mock=MockUnit())
    assert world.phase == "ended"
    assert world.tracks[0].status == "neutralized"
    assert any(e.kind == "plan" and "U1:" in e.msg and "engage" in e.msg for e in world.events)
    assert next(u for u in world.units if u.id == "U1").state == "expended"


def test_night2_single_engage_never_launch_early_time_to_impact():
    """S6.1: after swap, T1's only launch line is U1 engage; >=6 s to impact."""
    world = _night1_to_ended()
    world.handle_command({"type": "swap_variant", "unit_id": "U1", "variant": "B"})
    world.load_scenario("juniper_night2")
    mock = MockUnit()
    world.handle_command({"type": "start"})

    # At spawn, ETA to asset must be >= 20 s.
    while world.t + 1e-12 < 3.0:
        world.apply_u1_snapshot(mock.read())
        world.step(config.DT)
    world.apply_u1_snapshot(mock.read())
    world.step(config.DT)
    t1 = next(t for t in world.tracks if t.id == "T1")
    assert t1.eta is not None and t1.eta + 1e-9 >= 20.0, f"spawn ETA={t1.eta}"

    propose_t = None
    seen_ids: set[str] = set()
    launch_lines: list[tuple[str, str]] = []
    for _ in range(4000):
        world.apply_u1_snapshot(mock.read())
        world.step(config.DT)
        for line in world.plan:
            if line.action not in ("launch_early", "engage", "best_effort"):
                continue
            if line.id in seen_ids:
                continue
            seen_ids.add(line.id)
            launch_lines.append((line.unit_id, line.action))
            if propose_t is None:
                propose_t = world.t
                u1 = next(u for u in world.units if u.id == "U1")
                tr = next(t for t in world.tracks if t.id == "T1")
                dist = math.hypot(u1.x - tr.x, u1.y - tr.y)
                assert dist < 600.0, f"unit-to-track {dist} at proposal"
                assert tr.eta is not None and tr.eta + 1e-9 >= 6.0
        if propose_t is not None:
            tr = next(t for t in world.tracks if t.id == "T1")
            if tr.status != "active":
                break

    assert propose_t is not None, "no launch line proposed"
    assert len(launch_lines) == 1, f"expected one launch line, got {launch_lines}"
    assert launch_lines[0] == ("U1", "engage")
    assert world.tracks[0].status == "impact"
    assert world.t - propose_t + 1e-9 >= 6.0


def test_night1_c_threat_within_3s_of_spawn():
    world = World()
    world.load_scenario("juniper_night1")
    world.handle_command({"type": "start"})
    mock = MockUnit()
    spawn = None
    first_threat = None
    for _ in range(4000):
        world.apply_u1_snapshot(mock.read())
        world.step(config.DT)
        c = next((t for t in world.tracks if t.id == "C"), None)
        if c is None:
            continue
        if spawn is None:
            spawn = world.t
        if c.label == "threat" and first_threat is None:
            first_threat = world.t
            break
        if world.phase == "ended":
            break
    assert spawn is not None and first_threat is not None
    assert first_threat <= spawn + 3.0 + 1e-9, (
        f"C threat at {first_threat}, spawn {spawn}"
    )


def test_night2_without_swap_gaps_again():
    world = World()
    world.load_scenario("juniper_night2")
    _approve_delay_run(world, 2.0, mock=MockUnit())
    assert any(e.kind == "gap" for e in world.events)
    assert any(g.get("gap_type") == "fast_threat" for g in world.gaps)
    assert world.tracks[0].status == "impact"


def test_reset_from_every_phase_keeps_variants():
    # idle
    world = World()
    world.load_scenario("juniper_night1")
    world.handle_command({"type": "swap_variant", "unit_id": "U1", "variant": "B"})
    world.handle_command({"type": "reset"})
    assert world.phase == "idle"
    assert next(u for u in world.units if u.id == "U1").variant == "B"
    assert world.tracks == []

    # live
    world.handle_command({"type": "start"})
    world.step(config.DT)
    assert world.phase == "live"
    world.handle_command({"type": "reset"})
    assert world.phase == "idle"
    assert next(u for u in world.units if u.id == "U1").variant == "B"

    # paused
    world.handle_command({"type": "start"})
    world.step(config.DT)
    world.handle_command({"type": "pause"})
    assert world.phase == "paused"
    world.handle_command({"type": "reset"})
    assert world.phase == "idle"
    assert next(u for u in world.units if u.id == "U1").variant == "B"

    # ended
    world = _night1_to_ended()
    world.handle_command({"type": "swap_variant", "unit_id": "U1", "variant": "B"})
    assert world.phase == "ended"
    effects = world.handle_command({"type": "reset"})
    assert ("motors_off",) in effects
    assert world.phase == "idle"
    assert next(u for u in world.units if u.id == "U1").variant == "B"


def test_gap_brief_empty_before_and_filled_after_night1():
    main.TICK_SLEEP = 0.0
    with TestClient(app) as client:
        r = client.get("/gap_brief")
        assert r.status_code == 200
        assert r.text.strip() == ""

    world = _night1_to_ended()
    text = gap_brief_text(world)
    assert "40" in text
    assert "48" in text
    for uid in ("U1", "U2", "U3", "U4"):
        assert uid in text
    assert "variant A" in text.lower() or "Variant A" in text or ": A" in text

    main.TICK_SLEEP = 0.0
    with TestClient(app) as client:
        main.world = world
        r = client.get("/gap_brief")
        assert r.status_code == 200
        assert "40" in r.text
        assert "48" in r.text


def test_cards_json_placeholder_flag():
    with TestClient(app) as client:
        data = client.get("/cards.json").json()
        assert "placeholder" in data[0]
        assert data[0]["placeholder"] is False
        assert "propulsion" in data[0].get("swap", [])
