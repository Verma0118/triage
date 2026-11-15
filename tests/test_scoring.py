"""S2: threat scoring — unit factors + night1 label assertions."""

from __future__ import annotations

import math

import config
from engine.scoring import (
    ScoreState,
    circular_std_deg,
    heading_points,
    score_track,
    speed_points,
    steady_points,
)
from engine.world import World
from models import Asset, Track


def _asset(name: str, x: float, y: float) -> Asset:
    return Asset(name=name, x=x, y=y, kind=name)


def _track(**kwargs) -> Track:
    defaults = dict(
        id="T",
        x=0.0,
        y=0.0,
        speed=18.0,
        heading=0.0,
        history=[(0.0, 0.0)],
        registered_friendly=False,
        truth="real",
        waypoints=[],
        wp_index=0,
        status="active",
    )
    defaults.update(kwargs)
    return Track(**defaults)


# --- per-factor unit tests -------------------------------------------------


def test_registered_friendly_score_zero_label_friendly():
    track = _track(registered_friendly=True, speed=18.0, heading=0.0)
    assets = [_asset("housing", 100.0, 0.0)]
    state = ScoreState()
    score_track(track, assets, config.DT, state)
    assert track.threat_score == 0
    assert track.raw_score == 0.0
    assert track.label == "friendly"
    assert track.factors == []


def test_unregistered_adds_twenty():
    track = _track(speed=0.0, heading=0.0, history=[(0.0, 0.0)])
    # Far from assets, no heading cone, no steady (<3 samples), speed 0 → only +20.
    assets = [_asset("housing", 500.0, 500.0)]
    state = ScoreState()
    # Age past new-contact so label can settle; raw still just unregistered.
    state.age = config.NEW_CONTACT_SECONDS
    score_track(track, assets, config.DT, state)
    assert any("+20 unregistered" in f for f in track.factors)
    assert track.raw_score == 20.0


def test_speed_points_band_and_ramps():
    assert speed_points(0.0) == 0.0
    assert math.isclose(speed_points(config.ATTACK_SPEED_MIN / 2), 10.0)
    assert speed_points(config.ATTACK_SPEED_MIN) == 20.0
    assert speed_points(
        (config.ATTACK_SPEED_MIN + config.ATTACK_SPEED_MAX) / 2
    ) == 20.0
    assert speed_points(config.ATTACK_SPEED_MAX) == 20.0
    assert speed_points(config.ATTACK_SPEED_MAX + 10) == 20.0


def test_heading_points_picks_best_asset_in_cone():
    # Track at origin heading east; housing due east (value 1.0), parking NE.
    track = _track(x=0.0, y=0.0, heading=0.0)
    assets = [
        _asset("housing", 100.0, 0.0),
        _asset("parking", 100.0, 40.0),
    ]
    pts, name, factors = heading_points(track, assets, locked=None)
    assert name == "housing"
    assert math.isclose(pts, 35.0 * config.ASSET_VALUE["housing"])
    assert factors == ["+35 heading to housing"]


def test_heading_points_outside_cone_is_zero():
    track = _track(x=0.0, y=0.0, heading=0.0)  # east
    assets = [_asset("housing", 0.0, 100.0)]  # due north = 90°
    pts, name, factors = heading_points(track, assets, locked=None)
    assert pts == 0.0
    assert name is None
    assert factors == []


def test_heading_sticky_target_until_30_deg():
    track = _track(x=0.0, y=0.0, heading=0.0)
    # housing slightly off-axis but still best in-cone; parking farther off.
    assets = [
        _asset("housing", 100.0, 10.0),  # ~6° off east
        _asset("parking", 100.0, 30.0),  # ~17° off east
    ]
    _pts, name, _ = heading_points(track, assets, locked=None)
    assert name == "housing"

    # Keep lock while angle under 30° even if another asset is better.
    pts2, name2, _ = heading_points(track, assets, locked="housing")
    assert name2 == "housing"
    assert pts2 > 0.0

    # Break lock when angle >= 30°; housing is no longer sticky.
    track.heading = math.radians(50.0)
    to_housing = math.atan2(assets[0].y - track.y, assets[0].x - track.x)
    ang = math.degrees(abs((track.heading - to_housing + math.pi) % (2 * math.pi) - math.pi))
    assert ang >= 30.0
    _pts3, name3, _ = heading_points(track, assets, locked="housing")
    assert name3 != "housing"


def test_circular_std_wraps_at_plus_minus_180():
    """Headings near +/-180° are close on the circle; stddev must be small."""
    nearly_opp = [
        math.radians(179.0),
        math.radians(-179.0),
        math.radians(178.0),
        math.radians(-178.0),
    ]
    std = circular_std_deg(nearly_opp)
    assert std < 5.0, f"wrap stddev should be small, got {std}"

    spread = [math.radians(0.0), math.radians(90.0), math.radians(180.0), math.radians(-90.0)]
    std_spread = circular_std_deg(spread)
    assert std_spread > 40.0


def test_steady_points_thresholds():
    assert steady_points([]) == 0.0
    assert steady_points([(0.0, 0.0), (1.0, 0.0)]) == 0.0  # <3 samples

    # Perfectly east: 3+ colinear samples → full 25.
    hist = [(float(i), 0.0) for i in range(6)]
    assert math.isclose(steady_points(hist), 25.0)

    # Large turns → 0.
    zig = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 2.0), (1.0, 2.0)]
    assert steady_points(zig) == 0.0


def test_new_contact_forces_unknown():
    track = _track(
        speed=18.0,
        heading=0.0,
        x=0.0,
        y=0.0,
        history=[(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0)],
    )
    assets = [_asset("housing", 200.0, 0.0)]
    state = ScoreState(age=0.0, ema=0.0)
    score_track(track, assets, config.DT, state)
    assert state.age == config.DT
    assert track.label == "unknown"
    assert "new contact, classifying" in track.factors


def test_hysteresis_blocks_flip_at_threshold():
    """Unknown stays unknown at score 70; needs 70+hysteresis to become threat."""
    from engine.scoring import apply_label

    assert apply_label("unknown", 70.0, age=10.0, registered=False) == "unknown"
    assert apply_label("unknown", 70.0 + config.LABEL_HYSTERESIS, age=10.0, registered=False) == "threat"
    assert apply_label("threat", 70.0, age=10.0, registered=False) == "threat"
    assert apply_label("threat", 70.0 - config.LABEL_HYSTERESIS, age=10.0, registered=False) == "unknown"
    assert apply_label("unknown", 40.0, age=10.0, registered=False) == "unknown"
    assert apply_label("unknown", 40.0 - config.LABEL_HYSTERESIS, age=10.0, registered=False) == "decoy"
    assert apply_label("decoy", 40.0, age=10.0, registered=False) == "decoy"
    assert apply_label("decoy", 40.0 + config.LABEL_HYSTERESIS, age=10.0, registered=False) == "unknown"


def test_to_public_has_no_truth_or_waypoints():
    track = _track(
        truth="decoy",
        waypoints=[(0.0, 0.0), (1.0, 0.0)],
        wp_index=1,
        threat_score=12,
        label="decoy",
    )
    pub = track.to_public()
    assert "truth" not in pub
    assert "waypoints" not in pub
    assert "wp_index" not in pub
    world = World()
    world.load_scenario("juniper_night1")
    world.handle_command({"type": "start"})
    for _ in range(100):
        world.step(config.DT)
    payload = world.to_public()
    blob = repr(payload)
    assert "truth" not in blob
    assert "waypoints" not in blob
    for tr in payload["tracks"]:
        assert "truth" not in tr
        assert "waypoints" not in tr


# --- night1 full-run label assertions -------------------------------------


def _run_night1():
    world = World()
    world.load_scenario("juniper_night1")
    world.handle_command({"type": "start"})
    # Per-tick records: t, id -> (score, label, status)
    series: list[tuple[float, dict[str, tuple[int, str, str]]]] = []
    for _ in range(2000):
        world.step(config.DT)
        snap = {
            t.id: (t.threat_score, t.label, t.status)
            for t in world.tracks
        }
        series.append((world.t, snap))
        if world.phase == "ended":
            break
    assert world.phase == "ended"
    return world, series


def _spawn_t(series, tid: str) -> float:
    for t, snap in series:
        if tid in snap:
            return t
    raise AssertionError(f"{tid} never spawned")


def _loiter_start_t_for_a(world: World) -> float:
    """Wall-clock sim time when A finishes its straight first leg (reaches wp[1])."""
    from scenarios import get_scenario

    data = get_scenario("juniper_night1")
    spawn = next(s for s in data["spawns"] if s["id"] == "A")
    wps = spawn["waypoints"]
    leg_len = math.hypot(wps[1][0] - wps[0][0], wps[1][1] - wps[0][1])
    straight_s = leg_len / spawn["speed"]
    return spawn["t"] + straight_s


def test_night1_friendly_always_friendly_score_zero():
    _world, series = _run_night1()
    for t, snap in series:
        if "F1" not in snap:
            continue
        score, label, status = snap["F1"]
        if status != "active":
            # After gone, label may remain friendly; score must stay 0 while active.
            continue
        assert label == "friendly", f"t={t}: F1 label={label}"
        assert score == 0, f"t={t}: F1 score={score}"


def test_night1_b_threat_within_4s_and_never_leaves():
    _world, series = _run_night1()
    spawn = _spawn_t(series, "B")
    first_threat_t = None
    for t, snap in series:
        if "B" not in snap:
            continue
        _score, label, status = snap["B"]
        if status != "active":
            continue
        if label == "threat" and first_threat_t is None:
            first_threat_t = t
            assert t <= spawn + 4.0 + 1e-9, f"B became threat at t={t}, spawn={spawn}"
        if first_threat_t is not None:
            assert label == "threat", f"t={t}: B left threat -> {label}"
    assert first_threat_t is not None, "B never became threat"


def test_night1_a_unknown_then_decoy_never_threat():
    world, series = _run_night1()
    spawn = _spawn_t(series, "A")
    loiter_t = _loiter_start_t_for_a(world)
    decoy_deadline = loiter_t + 10.0

    became_decoy_at = None
    for t, snap in series:
        if "A" not in snap:
            continue
        _score, label, status = snap["A"]
        if status != "active":
            continue
        assert label != "threat", f"t={t}: A read threat"
        # During straight leg (before loiter): must be unknown (after new-contact window).
        if spawn + config.NEW_CONTACT_SECONDS <= t < loiter_t - 1e-9:
            assert label == "unknown", f"t={t}: A should be unknown on straight leg, got {label}"
        if label == "decoy" and became_decoy_at is None:
            became_decoy_at = t

    assert became_decoy_at is not None, "A never became decoy"
    assert became_decoy_at <= decoy_deadline + 1e-9, (
        f"A became decoy at t={became_decoy_at}, loiter_start={loiter_t}, "
        f"deadline={decoy_deadline}"
    )


def test_night1_no_track_changes_label_more_than_3_times():
    _world, series = _run_night1()
    last: dict[str, str] = {}
    changes: dict[str, int] = {}
    for _t, snap in series:
        for tid, (_score, label, _status) in snap.items():
            prev = last.get(tid)
            if prev is not None and prev != label:
                changes[tid] = changes.get(tid, 0) + 1
            last[tid] = label
    for tid, n in changes.items():
        assert n <= 3, f"{tid} changed label {n} times (>3)"


def test_night1_c_is_threat_or_unknown():
    _world, series = _run_night1()
    saw = False
    for t, snap in series:
        if "C" not in snap:
            continue
        _score, label, status = snap["C"]
        if status != "active":
            continue
        saw = True
        assert label in ("threat", "unknown"), f"t={t}: C label={label}"
    assert saw


def test_night1_a_stays_decoy_after_first_decoy():
    """Once A becomes decoy it never returns to unknown or threat."""
    _world, series = _run_night1()
    seen_decoy = False
    for t, snap in series:
        if "A" not in snap:
            continue
        _score, label, status = snap["A"]
        if status != "active":
            continue
        if label == "decoy":
            seen_decoy = True
        if seen_decoy:
            assert label == "decoy", f"t={t}: A left decoy -> {label}"
    assert seen_decoy, "A never became decoy"


def test_night1_c_threat_within_5s_and_stays_until_impact():
    _world, series = _run_night1()
    spawn = _spawn_t(series, "C")
    first_threat_t = None
    for t, snap in series:
        if "C" not in snap:
            continue
        _score, label, status = snap["C"]
        if label == "threat" and first_threat_t is None:
            first_threat_t = t
            assert t <= spawn + 5.0 + 1e-9, f"C became threat at t={t}, spawn={spawn}"
        if first_threat_t is not None and status == "active":
            assert label == "threat", f"t={t}: C left threat -> {label}"
        if status == "impact":
            assert first_threat_t is not None, "C impacted before becoming threat"
    assert first_threat_t is not None, "C never became threat"
    assert any(
        "C" in snap and snap["C"][2] == "impact" for _t, snap in series
    ), "C never reached impact"
