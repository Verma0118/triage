"""S7: tower22 replay — scoring only, no planner lines."""

from __future__ import annotations

import config
from bridge import MockUnit
from engine.world import World


def _run_tower22() -> World:
    world = World()
    world.load_scenario("tower22")
    assert world.replay is True
    world.handle_command({"type": "start"})
    mock = MockUnit()
    for _ in range(4000):
        world.apply_u1_snapshot(mock.read())
        world.step(config.DT)
        if world.phase == "ended":
            break
    return world


def test_tower22_planner_produces_zero_lines():
    world = World()
    world.load_scenario("tower22")
    world.handle_command({"type": "start"})
    mock = MockUnit()
    saw_active = False
    for _ in range(4000):
        world.apply_u1_snapshot(mock.read())
        world.step(config.DT)
        assert world.plan == []
        if any(t.status == "active" for t in world.tracks):
            saw_active = True
        if world.phase == "ended":
            break
    assert saw_active
    assert world.plan == []
    assert world.alerts == []
    assert all(u.state == "rack" for u in world.units)


def test_tower22_friendly_every_tick():
    world = World()
    world.load_scenario("tower22")
    world.handle_command({"type": "start"})
    mock = MockUnit()
    saw = False
    for _ in range(4000):
        world.apply_u1_snapshot(mock.read())
        world.step(config.DT)
        f1 = next((t for t in world.tracks if t.id == "F1"), None)
        if f1 is not None and f1.status == "active":
            saw = True
            assert f1.label == "friendly"
            assert f1.threat_score == 0
        if world.phase == "ended":
            break
    assert saw


def test_tower22_unregistered_threat_heading_housing_eta():
    world = World()
    world.load_scenario("tower22")
    world.handle_command({"type": "start"})
    mock = MockUnit()
    saw_threat = False
    for _ in range(4000):
        world.apply_u1_snapshot(mock.read())
        world.step(config.DT)
        t1 = next((t for t in world.tracks if t.id == "T1"), None)
        if t1 is None or t1.status != "active":
            if world.phase == "ended":
                break
            continue
        st = world._score_state.get("T1")
        if st is not None and st.age >= config.NEW_CONTACT_SECONDS:
            assert t1.label == "threat", f"t={world.t} label={t1.label}"
            assert any("heading to housing" in f for f in t1.factors), t1.factors
            assert t1.eta is not None and t1.eta > 0
            saw_threat = True
        if world.phase == "ended":
            break
    assert saw_threat
