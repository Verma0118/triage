"""S3: planner, approve, unit movement, MockUnit, scripted operator."""

from __future__ import annotations

import math

import config
from bridge import MockUnit
from engine.world import World
from models import PlanLine, Track, Unit


def _run(
    world: World,
    *,
    max_ticks: int = 3000,
    approve_delay: float | None = None,
    mock: MockUnit | None = None,
    approve_filter=None,
    until=None,
) -> World:
    """Advance live world. approve_delay: auto-approve proposed lines after N seconds."""
    if world.phase != "live":
        world.handle_command({"type": "start"})
    first_seen: dict[str, float] = {}
    for _ in range(max_ticks):
        if mock is not None:
            world.apply_u1_snapshot(mock.read())
        world.step(config.DT)
        if approve_delay is not None:
            for line in world.plan:
                if line.approved:
                    continue
                if approve_filter is not None and not approve_filter(line):
                    continue
                if line.id not in first_seen:
                    first_seen[line.id] = world.t
                if world.t - first_seen[line.id] + 1e-12 >= approve_delay:
                    world.handle_command({"type": "approve", "line_ids": [line.id]})
        if until is not None and until(world):
            break
        if world.phase == "ended":
            break
    return world


def _night1_world() -> World:
    world = World()
    world.load_scenario("juniper_night1")
    return world


def _unit_by_id(world: World, uid: str) -> Unit:
    return next(u for u in world.units if u.id == uid)


def _track_by_id(world: World, tid: str) -> Track:
    return next(t for t in world.tracks if t.id == tid)


def _lines_for(world: World, *, track_id=None, unit_id=None, action=None):
    out = []
    for line in world.plan:
        if track_id is not None and line.track_id != track_id:
            continue
        if unit_id is not None and line.unit_id != unit_id:
            continue
        if action is not None and line.action != action:
            continue
        out.append(line)
    return out


# --- S3 bullets -------------------------------------------------------------


def test_no_approvals_all_units_stay_rack():
    world = _night1_world()
    _run(world, approve_delay=None)
    assert world.phase == "ended"
    for u in world.units:
        assert u.state == "rack", f"{u.id} state={u.state}"


def test_scripted_operator_u1_launch_early_shadow_return():
    world = _night1_world()
    mock = MockUnit()
    saw_shadowing = False
    saw_return_line = False
    saw_launch = False

    world.handle_command({"type": "start"})
    first_seen: dict[str, float] = {}
    for _ in range(3000):
        world.apply_u1_snapshot(mock.read())
        world.step(config.DT)
        if _lines_for(world, unit_id="U1", track_id="A", action="launch_early"):
            saw_launch = True
        if _unit_by_id(world, "U1").state == "shadowing":
            saw_shadowing = True
        if _lines_for(world, unit_id="U1", track_id="A", action="return"):
            saw_return_line = True
        for line in world.plan:
            if line.approved:
                continue
            if line.id not in first_seen:
                first_seen[line.id] = world.t
            if world.t - first_seen[line.id] + 1e-12 >= 2.0:
                world.handle_command({"type": "approve", "line_ids": [line.id]})
        if world.phase == "ended":
            break

    assert saw_launch, "U1 never got launch_early on A"
    assert saw_shadowing, "U1 never reached shadowing"
    assert saw_return_line, "return line for A never appeared"

    u1 = _unit_by_id(world, "U1")
    assert u1.state == "rack"
    assert u1.ready is True
    assert any(e.kind == "returned" for e in world.events), "missing returned event"


def test_scripted_operator_u2_engage_b_neutralized():
    world = _night1_world()
    saw_engage = False
    world.handle_command({"type": "start"})
    first_seen: dict[str, float] = {}
    for _ in range(3000):
        world.step(config.DT)
        if _lines_for(world, unit_id="U2", track_id="B", action="engage"):
            saw_engage = True
        for line in world.plan:
            if line.approved:
                continue
            if line.id not in first_seen:
                first_seen[line.id] = world.t
            if world.t - first_seen[line.id] + 1e-12 >= 2.0:
                world.handle_command({"type": "approve", "line_ids": [line.id]})
        if world.phase == "ended":
            break
    assert saw_engage, "U2 never got engage on B"
    assert _track_by_id(world, "B").status == "neutralized"
    assert _unit_by_id(world, "U2").state == "expended"
    assert any(e.kind == "neutralized" for e in world.events)


def test_stickiness_delayed_approval_a_u1_b_u2():
    """If first approval waits until after B spawns, A still U1 and B still U2."""
    world = _night1_world()
    world.handle_command({"type": "start"})
    first_seen: dict[str, float] = {}
    a_unit = None
    b_unit = None
    for _ in range(3000):
        world.step(config.DT)
        for ln in world.plan:
            if ln.track_id == "A" and ln.action == "launch_early":
                a_unit = ln.unit_id
            if ln.track_id == "B" and ln.action == "engage":
                b_unit = ln.unit_id
        b_spawned = any(t.id == "B" for t in world.tracks)
        for line in world.plan:
            if line.approved:
                continue
            if line.id not in first_seen:
                first_seen[line.id] = world.t
            gate = max(first_seen[line.id] + 2.0, 8.0)
            if b_spawned and world.t + 1e-12 >= gate:
                world.handle_command({"type": "approve", "line_ids": [line.id]})
        if world.phase == "ended":
            break

    assert a_unit == "U1", f"A assigned to {a_unit}"
    assert b_unit == "U2", f"B assigned to {b_unit}"


def test_approved_line_never_unapproved_and_id_not_reproposed():
    world = _night1_world()
    seen_ids: list[str] = []
    approved_flags: dict[str, list[bool]] = {}

    world.handle_command({"type": "start"})
    first_seen: dict[str, float] = {}
    for _ in range(3000):
        world.step(config.DT)
        for line in world.plan:
            if line.id not in seen_ids:
                seen_ids.append(line.id)
            approved_flags.setdefault(line.id, []).append(line.approved)
            if not line.approved:
                if line.id not in first_seen:
                    first_seen[line.id] = world.t
                if world.t - first_seen[line.id] >= 2.0:
                    world.handle_command({"type": "approve", "line_ids": [line.id]})
        if world.phase == "ended":
            break

    # No duplicate proposals of the same id (plan list may keep one copy).
    assert len(seen_ids) == len(set(seen_ids))
    for lid, flags in approved_flags.items():
        if any(flags):
            # Once True appeared, never goes back to False.
            first_true = flags.index(True)
            assert all(flags[first_true:]), f"{lid} flipped back to unapproved"


def test_u1_not_ready_line_reassigned():
    world = _night1_world()
    mock = MockUnit()
    world.handle_command({"type": "start"})
    # Run until U1 has a proposed (unapproved) line on rack.
    for _ in range(500):
        world.apply_u1_snapshot(mock.read())
        world.step(config.DT)
        lines = [ln for ln in world.plan if ln.unit_id == "U1" and not ln.approved]
        u1 = _unit_by_id(world, "U1")
        if lines and u1.state == "rack":
            break
    else:
        raise AssertionError("U1 never got a proposed rack line")

    old = lines[0]
    mock.ready = False
    world.apply_u1_snapshot(mock.read())
    # Step a few times for replan.
    for _ in range(5):
        world.apply_u1_snapshot(mock.read())
        world.step(config.DT)

    assert not any(
        ln.id == old.id and not ln.approved for ln in world.plan
    ), "old U1 proposed line should be dropped"
    replacements = [
        ln
        for ln in world.plan
        if ln.track_id == old.track_id and ln.unit_id != "U1" and not ln.approved
    ]
    assert replacements, "track was not reassigned"
    assert any("U1 not ready" in ln.reason for ln in replacements)


def test_return_proposed_but_not_approved_keeps_shadowing():
    world = _night1_world()
    mock = MockUnit()
    world.handle_command({"type": "start"})
    first_seen: dict[str, float] = {}
    return_seen_at = None
    for _ in range(3000):
        world.apply_u1_snapshot(mock.read())
        world.step(config.DT)
        # Approve everything except return lines.
        for line in world.plan:
            if line.approved:
                continue
            if line.action == "return":
                if return_seen_at is None:
                    return_seen_at = world.t
                continue
            if line.id not in first_seen:
                first_seen[line.id] = world.t
            if world.t - first_seen[line.id] >= 2.0:
                world.handle_command({"type": "approve", "line_ids": [line.id]})
        u1 = _unit_by_id(world, "U1")
        if return_seen_at is not None and world.t - return_seen_at >= 5.0:
            # After return has been proposed for 5 s without approval:
            assert u1.state == "shadowing", f"U1 state={u1.state}"
            assert math.hypot(u1.x - u1.home_x, u1.y - u1.home_y) > 1.0
            assert u1.state != "expended"
            return
        if world.phase == "ended":
            break
    raise AssertionError("return line never proposed or run ended too soon")


def test_force_commit_engage_when_eta_low():
    """Unknown track with ETA under FORCE_COMMIT_ETA gets engage 'out of time'."""
    world = World()
    world.load_scenario("juniper_night1")
    world.handle_command({"type": "start"})
    world._spawns = []
    world._spawned_ids = set()
    world.tracks = []
    world.plan = []
    world.events = []
    parking = next(a for a in world.assets if a.name == "parking")
    # Aim at parking (value 0.4): without full steady, score stays in unknown band,
    # but heading lock gives a real ETA. dist=50, speed=9 → ETA≈5.6 < 8.
    x0, y0 = parking.x - 50.0, parking.y
    track = Track(
        id="U",
        x=x0,
        y=y0,
        speed=9.0,
        heading=0.0,
        history=[(x0, y0)],
        registered_friendly=False,
        truth="decoy",
        waypoints=[(x0, y0), (parking.x, parking.y)],
        wp_index=1,
        target_asset="parking",
        label="unknown",
        status="active",
    )
    world.tracks.append(track)
    from engine.scoring import ScoreState

    world._score_state["U"] = ScoreState(age=5.0, ema=50.0)
    track.threat_score = 50
    track.eta = 50.0 / 9.0
    assert track.eta < config.FORCE_COMMIT_ETA

    u1 = _unit_by_id(world, "U1")
    line = PlanLine(
        id="U1:U:launch_early",
        unit_id="U1",
        track_id="U",
        action="launch_early",
        reason="test",
        approved=True,
    )
    world.plan.append(line)
    u1.state = "shadowing"
    u1.assigned_track = "U"
    u1.x = track.x - config.STANDOFF_RADIUS
    u1.y = track.y
    world._ever_proposed = {line.id}

    for _ in range(50):
        world.step(config.DT)
        eng = _lines_for(world, unit_id="U1", track_id="U", action="engage")
        if eng:
            assert any("out of time" in ln.reason for ln in eng)
            return
    raise AssertionError("engage with out-of-time reason never proposed")


def test_track_ends_unit_comes_home_lines_removed():
    world = World()
    world.load_scenario("juniper_night1")
    world.handle_command({"type": "start"})
    world._spawns = []
    world._spawned_ids = set()
    world.tracks = []
    world.plan = []
    world.events = []

    track = Track(
        id="X",
        x=500.0,
        y=400.0,
        speed=9.0,
        heading=0.0,
        history=[(500.0, 400.0)],
        truth="decoy",
        waypoints=[(500.0, 400.0), (510.0, 400.0)],
        wp_index=1,
        label="unknown",
        status="active",
    )
    world.tracks.append(track)
    u1 = _unit_by_id(world, "U1")
    world.plan.append(
        PlanLine(
            id="U1:X:launch_early",
            unit_id="U1",
            track_id="X",
            action="launch_early",
            reason="test",
            approved=True,
        )
    )
    world._ever_proposed = {"U1:X:launch_early"}
    u1.state = "outbound"
    u1.assigned_track = "X"
    u1.x = 550.0
    u1.y = 400.0

    # End the track immediately.
    track.status = "gone"
    for _ in range(200):
        world.step(config.DT)
        if u1.state == "rack" and not any(ln.track_id == "X" for ln in world.plan):
            break
    assert u1.state == "rack"
    assert u1.assigned_track is None
    assert not any(ln.track_id == "X" for ln in world.plan)
    assert any("track gone" in e.msg for e in world.events)


def test_approve_live_launch_motor_test_once_return_none():
    world = _night1_world()
    u1 = _unit_by_id(world, "U1")
    u1.source = "live"
    world.handle_command({"type": "start"})
    # Wait for a launch_early proposal for U1.
    for _ in range(500):
        world.step(config.DT)
        lines = _lines_for(world, unit_id="U1", action="launch_early")
        if lines and not lines[0].approved:
            break
    else:
        raise AssertionError("no launch_early for U1")

    line = lines[0]
    effects1 = world.handle_command({"type": "approve", "line_ids": [line.id]})
    assert effects1.count(("motor_test", "U1")) == 1

    effects2 = world.handle_command({"type": "approve", "line_ids": [line.id]})
    assert effects2 == []

    # Get a return line: keep approving non-return, then find return.
    first_seen: dict[str, float] = {}
    for _ in range(2000):
        world.step(config.DT)
        for ln in world.plan:
            if ln.approved:
                continue
            if ln.action == "return":
                effects_r = world.handle_command({"type": "approve", "line_ids": [ln.id]})
                assert ("motor_test", "U1") not in effects_r
                return
            if ln.id not in first_seen:
                first_seen[ln.id] = world.t
            if world.t - first_seen[ln.id] >= 0.5:
                world.handle_command({"type": "approve", "line_ids": [ln.id]})
    raise AssertionError("return line never appeared")


def test_night1_flow_with_battery_pct_half():
    world = _night1_world()
    mock = MockUnit()
    mock.battery_pct = 0.5
    mock.battery_v = config.BATTERY_V_MIN + 0.5 * (
        config.BATTERY_V_MAX - config.BATTERY_V_MIN
    )
    saw_launch = False
    world.handle_command({"type": "start"})
    first_seen: dict[str, float] = {}
    for _ in range(3000):
        world.apply_u1_snapshot(mock.read())
        world.step(config.DT)
        if _lines_for(world, unit_id="U1", track_id="A", action="launch_early"):
            saw_launch = True
        for line in world.plan:
            if line.approved:
                continue
            if line.id not in first_seen:
                first_seen[line.id] = world.t
            if world.t - first_seen[line.id] + 1e-12 >= 2.0:
                world.handle_command({"type": "approve", "line_ids": [line.id]})
        if world.phase == "ended":
            break
    assert world.phase == "ended"
    assert saw_launch
    assert _track_by_id(world, "B").status == "neutralized"
    assert _unit_by_id(world, "U2").state == "expended"
    u1 = _unit_by_id(world, "U1")
    assert u1.state == "rack"
    assert any(e.kind == "returned" for e in world.events)
