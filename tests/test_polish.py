"""Polish: reset mid-flight, swap back to A, mock toggle mid-run."""

from __future__ import annotations

import config
import main
from bridge import MockUnit
from engine.world import World
from fastapi.testclient import TestClient
from main import app, apply_set_mock
from tests.test_gap_swap import _approve_delay_run, _night1_to_ended


def test_reset_mid_flight_clears_outbound_units():
    world = World()
    world.load_scenario("juniper_night1")
    mock = MockUnit()
    world.handle_command({"type": "start"})
    first: dict[str, float] = {}
    launched = False
    for _ in range(2000):
        world.apply_u1_snapshot(mock.read())
        world.step(config.DT)
        for line in world.plan:
            if line.approved:
                continue
            if line.id not in first:
                first[line.id] = world.t
            if world.t - first[line.id] >= 0.5:
                world.handle_command({"type": "approve", "line_ids": [line.id]})
        if any(u.state not in ("rack", "expended") for u in world.units):
            launched = True
            break
    assert launched
    effects = world.handle_command({"type": "reset"})
    assert ("motors_off",) in effects
    assert world.phase == "idle"
    assert world.tracks == []
    assert world.plan == []
    assert all(u.state == "rack" for u in world.units)


def test_swap_u1_back_to_a():
    world = _night1_to_ended()
    world.handle_command({"type": "swap_variant", "unit_id": "U1", "variant": "B"})
    assert next(u for u in world.units if u.id == "U1").variant == "B"
    effects = world.handle_command(
        {"type": "swap_variant", "unit_id": "U1", "variant": "A"}
    )
    assert ("set_name", "U1", "TRIAGE-A-001") in effects
    u1 = next(u for u in world.units if u.id == "U1")
    assert u1.variant == "A"
    assert u1.speed == config.VARIANTS["A"]["speed"]


def test_mock_toggle_mid_run_keeps_sim_state():
    main.TICK_SLEEP = 0.0
    world = World()
    world.load_scenario("juniper_night1")
    mock = MockUnit()
    world.handle_command({"type": "start"})
    for _ in range(30):
        world.apply_u1_snapshot(mock.read())
        world.step(config.DT)
    assert world.phase == "live"
    t_before = world.t
    tracks_before = len(world.tracks)
    main.world = world
    main.bridge = mock
    # Toggle mock off then on via apply_set_mock (closes/reopens MockUnit).
    apply_set_mock(True)
    assert isinstance(main.bridge, MockUnit)
    snap = main.bridge.read()
    assert snap["source"] == "mock"
    # Sim state intact.
    assert main.world.phase == "live"
    assert main.world.t == t_before
    assert len(main.world.tracks) == tracks_before
    main.world.apply_u1_snapshot(main.bridge.read())
    main.world.step(config.DT)
    assert main.world.phase == "live"
    assert main.world.t > t_before


def test_app_reset_via_ws_from_live():
    main.TICK_SLEEP = 0.0
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()
            ws.send_json({"type": "load_scenario", "name": "juniper_night1"})
            ws.send_json({"type": "start"})
            msg = None
            for _ in range(50):
                msg = ws.receive_json()
                if msg.get("phase") == "live":
                    break
            assert msg is not None and msg["phase"] == "live"
            ws.send_json({"type": "reset"})
            for _ in range(50):
                msg = ws.receive_json()
                if msg.get("phase") == "idle":
                    break
            assert msg["phase"] == "idle"
            assert msg["tracks"] == []
