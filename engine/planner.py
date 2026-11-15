"""Sticky plan lines. Pure engine — no FastAPI, serial, or bridge."""

from __future__ import annotations

import math

import config
from models import Event, PlanLine, Track, Unit


def _dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def _line_id(unit_id: str, track_id: str, action: str) -> str:
    return f"{unit_id}:{track_id}:{action}"


def _unit_has_line(plan: list[PlanLine], unit_id: str) -> bool:
    """A unit with any current plan line is busy (one track at a time)."""
    return any(ln.unit_id == unit_id for ln in plan)


def _capable(unit: Unit, track: Track, plan: list[PlanLine]) -> bool:
    if unit.state != "rack" or not unit.ready:
        return False
    if _unit_has_line(plan, unit.id):
        return False
    if unit.speed <= track.speed * config.CAPABLE_SPEED_MARGIN:
        return False
    if unit.range < _dist(unit.x, unit.y, track.x, track.y):
        return False
    return True


def _cheapest_capable(units: list[Unit], track: Track, plan: list[PlanLine]) -> Unit | None:
    capable = [u for u in units if _capable(u, track, plan)]
    if not capable:
        return None
    capable.sort(key=lambda u: (u.cost, u.id))
    return capable[0]


def _active_line_for_track(plan: list[PlanLine], track_id: str) -> PlanLine | None:
    """Any current line (proposed or approved) that assigns this track."""
    for line in plan:
        if line.track_id == track_id:
            return line
    return None


def _last_approved_for_unit(plan: list[PlanLine], unit_id: str) -> PlanLine | None:
    approved = [ln for ln in plan if ln.unit_id == unit_id and ln.approved]
    if not approved:
        return None
    # Prefer the most recently added approved line (list order).
    return approved[-1]


def _has_pending_transition(plan: list[PlanLine], unit_id: str, track_id: str, action: str) -> bool:
    return any(
        ln.unit_id == unit_id
        and ln.track_id == track_id
        and ln.action == action
        and not ln.approved
        for ln in plan
    )


def plan_tick(world) -> None:
    """Update plan lines for this tick. No-op for replay scenarios."""
    if world.replay:
        return

    # 7. Track ended: remove lines; units out on it auto-return.
    _handle_ended_tracks(world)

    # 4. Sticky exception: proposed line's unit on rack became not ready.
    _reassign_not_ready(world)

    # 5. Transitions for units already launched.
    _propose_transitions(world)

    # 1–3. New candidates.
    _propose_new_assignments(world)


def _handle_ended_tracks(world) -> None:
    ended_ids = {
        t.id for t in world.tracks if t.status in ("neutralized", "impact", "gone")
    }
    if not ended_ids:
        return
    world.plan = [ln for ln in world.plan if ln.track_id not in ended_ids]
    for unit in world.units:
        if unit.assigned_track in ended_ids and unit.state not in ("rack", "expended"):
            unit.state = "returning"
            unit.assigned_track = None
            # Auto-return home; sim will finish the flight.
            world.events.append(
                Event(t=world.t, kind="recall", msg="track gone, returning")
            )


def _reassign_not_ready(world) -> None:
    to_drop: list[PlanLine] = []
    for line in list(world.plan):
        if line.approved:
            continue
        unit = next((u for u in world.units if u.id == line.unit_id), None)
        if unit is None:
            continue
        if unit.state == "rack" and not unit.ready:
            to_drop.append(line)

    for line in to_drop:
        world.plan.remove(line)
        track = next((t for t in world.tracks if t.id == line.track_id), None)
        if track is None or track.status != "active":
            continue
        if track.label not in ("threat", "unknown"):
            continue
        # Line already removed from plan, so the dropped unit is free; others busy stay busy.
        replacement = _cheapest_capable(world.units, track, world.plan)
        if replacement is None:
            continue
        action = "engage" if track.label == "threat" else "launch_early"
        new_id = _line_id(replacement.id, track.id, action)
        if new_id in world._ever_proposed:
            continue
        reason = f"{line.unit_id} not ready, reassigned"
        _add_line(world, replacement.id, track.id, action, reason)


def _propose_transitions(world) -> None:
    for unit in world.units:
        last = _last_approved_for_unit(world.plan, unit.id)
        if last is None or last.action != "launch_early":
            continue
        if unit.state not in ("outbound", "shadowing"):
            continue
        track = next((t for t in world.tracks if t.id == last.track_id), None)
        if track is None or track.status != "active":
            continue

        # launch_early -> engage
        if track.label == "threat":
            if not _has_pending_transition(world.plan, unit.id, track.id, "engage"):
                _add_line(
                    world, unit.id, track.id, "engage", "confirmed threat"
                )
            continue

        if (
            track.label == "unknown"
            and track.eta is not None
            and track.eta < config.FORCE_COMMIT_ETA
        ):
            if not _has_pending_transition(world.plan, unit.id, track.id, "engage"):
                _add_line(
                    world,
                    unit.id,
                    track.id,
                    "engage",
                    "out of time, defaulting to threat",
                )
            continue

        # launch_early -> return: score below THREAT_LOW for DECOY_RECALL_HOLD
        key = track.id
        if track.threat_score < config.THREAT_LOW:
            world._decoy_hold[key] = world._decoy_hold.get(key, 0.0) + config.DT
        else:
            world._decoy_hold[key] = 0.0

        if world._decoy_hold.get(key, 0.0) >= config.DECOY_RECALL_HOLD:
            if not _has_pending_transition(world.plan, unit.id, track.id, "return"):
                # Also skip if return already approved.
                if not any(
                    ln.unit_id == unit.id
                    and ln.track_id == track.id
                    and ln.action == "return"
                    and ln.approved
                    for ln in world.plan
                ):
                    _add_line(
                        world, unit.id, track.id, "return", "now likely decoy"
                    )


def _track_age(world, track_id: str) -> float:
    st = world._score_state.get(track_id)
    return st.age if st is not None else 0.0


def _propose_new_assignments(world) -> None:
    candidates = [
        t
        for t in world.tracks
        if t.status == "active"
        and t.label in ("threat", "unknown")
        and _track_age(world, t.id) >= config.NEW_CONTACT_SECONDS
    ]
    # Tracks that already have a line are sticky — skip.
    candidates = [
        t for t in candidates if _active_line_for_track(world.plan, t.id) is None
    ]
    candidates.sort(key=lambda t: (-t.priority, t.id))

    for track in candidates:
        # S3: skip full gap/best_effort (S6). If nobody is capable, leave unassigned.
        unit = _cheapest_capable(world.units, track, world.plan)
        if unit is None:
            continue
        action = "engage" if track.label == "threat" else "launch_early"
        reason = (
            f"{'threat' if action == 'engage' else 'unknown'} "
            f"priority={track.priority}"
        )
        _add_line(world, unit.id, track.id, action, reason)


def _add_line(world, unit_id: str, track_id: str, action: str, reason: str) -> None:
    lid = _line_id(unit_id, track_id, action)
    if lid in world._ever_proposed:
        return
    # Do not add a second line for same unit+track+action if already present.
    if any(
        ln.unit_id == unit_id and ln.track_id == track_id and ln.action == action
        for ln in world.plan
    ):
        return
    world._ever_proposed.add(lid)
    line = PlanLine(
        id=lid,
        unit_id=unit_id,
        track_id=track_id,
        action=action,
        reason=reason,
        approved=False,
    )
    world.plan.append(line)
    world.events.append(
        Event(t=world.t, kind="plan", msg=f"{lid} {reason}")
    )
