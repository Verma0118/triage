"""Track and unit motion. Pure functions over model state."""

from __future__ import annotations

import math

import config
from models import Event, PlanLine, Track, Unit


def _heading(dx: float, dy: float) -> float:
    return math.atan2(dy, dx)


def _move_toward(x: float, y: float, tx: float, ty: float, speed: float, dt: float) -> tuple[float, float, bool]:
    """Move (x,y) toward (tx,ty) by speed*dt. Returns (nx, ny, arrived)."""
    dx, dy = tx - x, ty - y
    dist = math.hypot(dx, dy)
    step = speed * dt
    if dist <= 1e-9:
        return x, y, True
    if dist <= step:
        return tx, ty, True
    return x + (dx / dist) * step, y + (dy / dist) * step, False


def move_track(track: Track, dt: float) -> None:
    """Advance a track along its waypoints at constant speed.

    Real tracks that finish waypoints become impact.
    Decoy and friendly tracks that finish become gone.
    Impact/gone is decided by scenario truth, not target_asset.
    """
    if track.status != "active":
        return
    if not track.waypoints or track.wp_index >= len(track.waypoints):
        _finish_track(track)
        return

    remaining = track.speed * dt
    while remaining > 0 and track.wp_index < len(track.waypoints):
        tx, ty = track.waypoints[track.wp_index]
        dx = tx - track.x
        dy = ty - track.y
        dist = math.hypot(dx, dy)
        if dist <= 1e-9:
            track.wp_index += 1
            continue
        track.heading = _heading(dx, dy)
        if dist <= remaining:
            track.x = tx
            track.y = ty
            remaining -= dist
            track.wp_index += 1
        else:
            track.x += (dx / dist) * remaining
            track.y += (dy / dist) * remaining
            remaining = 0

    if track.wp_index >= len(track.waypoints):
        _finish_track(track)


def _finish_track(track: Track) -> None:
    if track.truth == "real":
        track.status = "impact"
    else:
        track.status = "gone"


def _last_approved(plan: list[PlanLine], unit_id: str) -> PlanLine | None:
    approved = [ln for ln in plan if ln.unit_id == unit_id and ln.approved]
    return approved[-1] if approved else None


def move_units(
    units: list[Unit],
    tracks: list[Track],
    plan: list[PlanLine],
    dt: float,
    events: list[Event],
    t: float,
) -> None:
    """Advance units per last approved line (or auto-return)."""
    tracks_by_id = {tr.id: tr for tr in tracks}
    for unit in units:
        if unit.state in ("rack", "expended"):
            continue

        # Auto-return home (track gone / return approved finishing).
        if unit.state == "returning":
            nx, ny, arrived = _move_toward(
                unit.x, unit.y, unit.home_x, unit.home_y, unit.speed, dt
            )
            unit.x, unit.y = nx, ny
            if arrived:
                unit.x, unit.y = unit.home_x, unit.home_y
                unit.state = "rack"
                unit.assigned_track = None
                events.append(
                    Event(t=t, kind="returned", msg="returned, not expended")
                )
            continue

        last = _last_approved(plan, unit.id)
        if last is None:
            continue

        track = tracks_by_id.get(last.track_id)
        if last.action == "return":
            unit.state = "returning"
            unit.assigned_track = last.track_id
            nx, ny, arrived = _move_toward(
                unit.x, unit.y, unit.home_x, unit.home_y, unit.speed, dt
            )
            unit.x, unit.y = nx, ny
            if arrived:
                unit.x, unit.y = unit.home_x, unit.home_y
                unit.state = "rack"
                unit.assigned_track = None
                events.append(
                    Event(t=t, kind="returned", msg="returned, not expended")
                )
            continue

        if track is None or track.status != "active":
            continue

        unit.assigned_track = track.id

        if last.action == "launch_early":
            _pursue_standoff(unit, track, dt)
        elif last.action == "engage":
            _pursue_engage(unit, track, dt, events, t)
        elif last.action == "best_effort":
            _pursue_best_effort(unit, track, dt, events, t, plan)


def _pursue_standoff(unit: Unit, track: Track, dt: float) -> None:
    dx = track.x - unit.x
    dy = track.y - unit.y
    dist = math.hypot(dx, dy)
    if dist <= config.STANDOFF_RADIUS:
        unit.state = "shadowing"
        # Hold standoff: move toward the point at STANDOFF_RADIUS from track
        # along the current unit-track ray (or away if too close).
        if dist < 1e-9:
            # Coincident — step west to create separation.
            target_x = track.x - config.STANDOFF_RADIUS
            target_y = track.y
        else:
            scale = config.STANDOFF_RADIUS / dist
            target_x = track.x - dx * scale
            target_y = track.y - dy * scale
        nx, ny, _ = _move_toward(unit.x, unit.y, target_x, target_y, unit.speed, dt)
        unit.x, unit.y = nx, ny
    else:
        unit.state = "outbound"
        nx, ny, _ = _move_toward(unit.x, unit.y, track.x, track.y, unit.speed, dt)
        unit.x, unit.y = nx, ny


def _pursue_engage(
    unit: Unit, track: Track, dt: float, events: list[Event], t: float
) -> None:
    unit.state = "outbound"
    nx, ny, _ = _move_toward(unit.x, unit.y, track.x, track.y, unit.speed, dt)
    unit.x, unit.y = nx, ny
    dist = math.hypot(track.x - unit.x, track.y - unit.y)
    if dist <= config.INTERCEPT_RADIUS:
        track.status = "neutralized"
        unit.state = "expended"
        unit.assigned_track = None
        events.append(
            Event(t=t, kind="neutralized", msg=f"{unit.id} neutralized {track.id}")
        )


def _pursue_best_effort(
    unit: Unit,
    track: Track,
    dt: float,
    events: list[Event],
    t: float,
    plan: list[PlanLine],
) -> None:
    """Close in, then miss. Non-capable never neutralizes (deterministic)."""
    unit.state = "outbound"
    nx, ny, _ = _move_toward(unit.x, unit.y, track.x, track.y, unit.speed, dt)
    unit.x, unit.y = nx, ny
    dist = math.hypot(track.x - unit.x, track.y - unit.y)
    capable = unit.speed > track.speed * config.CAPABLE_SPEED_MARGIN
    # Compare to last tick's distance (track moves before units each step).
    prev = getattr(unit, "_be_prev_dist", None)
    miss = False
    if capable:
        miss = dist <= config.INTERCEPT_RADIUS
    else:
        chase = max(config.STANDOFF_RADIUS, 50.0)
        if dist <= config.INTERCEPT_RADIUS:
            miss = True
        elif (
            prev is not None
            and dist <= chase
            and dist >= prev - 1e-9
        ):
            miss = True
    unit._be_prev_dist = dist
    if miss:
        events.append(
            Event(t=t, kind="miss", msg="could not match speed")
        )
        unit.state = "returning"
        unit.assigned_track = None
        if hasattr(unit, "_be_prev_dist"):
            delattr(unit, "_be_prev_dist")
        # Drop best_effort lines so the unit does not relaunch after returning.
        plan[:] = [
            ln
            for ln in plan
            if not (
                ln.unit_id == unit.id
                and ln.track_id == track.id
                and ln.action == "best_effort"
            )
        ]
