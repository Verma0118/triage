"""Track (and later unit) motion. Pure functions over model state."""

from __future__ import annotations

import math

from models import Track


def _heading(dx: float, dy: float) -> float:
    return math.atan2(dy, dx)


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
