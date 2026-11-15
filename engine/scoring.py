"""Threat score and label. Pure functions over track + assets. No wall clock."""

from __future__ import annotations

import math
from dataclasses import dataclass

import config
from models import Asset, Track


@dataclass
class ScoreState:
    ema: float = 0.0
    hist_acc: float = 0.0
    age: float = 0.0


def angle_diff_rad(a: float, b: float) -> float:
    """Smallest absolute angle from a to b, radians in [0, pi]."""
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def circular_std_deg(headings_rad: list[float]) -> float:
    """Circular standard deviation in degrees. Handles wrap at +/-180."""
    if len(headings_rad) < 2:
        return 0.0
    n = len(headings_rad)
    c = sum(math.cos(h) for h in headings_rad) / n
    s = sum(math.sin(h) for h in headings_rad) / n
    r = math.hypot(c, s)
    if r >= 1.0:
        return 0.0
    if r < 1e-12:
        return 180.0
    return math.degrees(math.sqrt(-2.0 * math.log(r)))


def _headings_from_history(history: list[tuple[float, float]]) -> list[float]:
    out: list[float] = []
    for i in range(1, len(history)):
        x0, y0 = history[i - 1]
        x1, y1 = history[i]
        dx, dy = x1 - x0, y1 - y0
        if math.hypot(dx, dy) <= 1e-9:
            continue
        out.append(math.atan2(dy, dx))
    return out


def steady_points(history: list[tuple[float, float]]) -> float:
    if len(history) < 3:
        return 0.0
    headings = _headings_from_history(history)
    if len(headings) < 2:
        return 0.0
    std = circular_std_deg(headings)
    if std <= config.STEADY_FULL_DEG:
        return 25.0
    if std >= config.STEADY_ZERO_DEG:
        return 0.0
    span = config.STEADY_ZERO_DEG - config.STEADY_FULL_DEG
    return 25.0 * (1.0 - (std - config.STEADY_FULL_DEG) / span)


def speed_points(speed: float) -> float:
    if speed <= 0:
        return 0.0
    if speed < config.ATTACK_SPEED_MIN:
        return 20.0 * speed / config.ATTACK_SPEED_MIN
    # At or above min: full 20 (including above max per plan: "Above: 20").
    return 20.0


def heading_points(
    track: Track, assets: list[Asset], locked: str | None
) -> tuple[float, str | None, list[str]]:
    """Return (points, target_name, factor_strings)."""
    if locked:
        asset = next((a for a in assets if a.name == locked), None)
        if asset is not None:
            to_a = math.atan2(asset.y - track.y, asset.x - track.x)
            ang = math.degrees(angle_diff_rad(track.heading, to_a))
            if ang < 30.0:
                value = config.ASSET_VALUE.get(asset.kind, 0.2)
                pts = 35.0 * value
                return pts, locked, [f"+{int(round(pts))} heading to {locked}"]
            # Lock broken; fall through to re-pick.

    best_name: str | None = None
    best_ang = None
    for asset in assets:
        to_a = math.atan2(asset.y - track.y, asset.x - track.x)
        ang = math.degrees(angle_diff_rad(track.heading, to_a))
        if ang < config.HEADING_CONE_DEG:
            if best_ang is None or ang < best_ang:
                best_ang = ang
                best_name = asset.name

    if best_name is None:
        return 0.0, None, []

    asset = next(a for a in assets if a.name == best_name)
    value = config.ASSET_VALUE.get(asset.kind, 0.2)
    pts = 35.0 * value
    return pts, best_name, [f"+{int(round(pts))} heading to {best_name}"]


def apply_label(
    current: str, score: float, *, age: float, registered: bool
) -> str:
    if registered:
        return "friendly"
    if age < config.NEW_CONTACT_SECONDS:
        return "unknown"

    hyst = config.LABEL_HYSTERESIS
    high = config.THREAT_HIGH
    low = config.THREAT_LOW

    if current == "friendly":
        current = "unknown"

    desired = (
        "threat"
        if score >= high
        else "unknown"
        if score >= low
        else "decoy"
    )
    if desired == current:
        return current

    # threat <-> unknown around HIGH
    if current == "unknown" and desired == "threat":
        return "threat" if score >= high + hyst else current
    if current == "threat" and desired == "unknown":
        return "unknown" if score <= high - hyst else current
    if current == "threat" and desired == "decoy":
        return "decoy" if score <= low - hyst else (
            "unknown" if score <= high - hyst else current
        )

    # unknown <-> decoy around LOW
    if current == "unknown" and desired == "decoy":
        return "decoy" if score <= low - hyst else current
    if current == "decoy" and desired == "unknown":
        return "unknown" if score >= low + hyst else current
    if current == "decoy" and desired == "threat":
        return "threat" if score >= high + hyst else (
            "unknown" if score >= low + hyst else current
        )

    return current


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def score_track(
    track: Track, assets: list[Asset], dt: float, state: ScoreState
) -> None:
    """Update history sampling, raw/smoothed score, label, eta, priority."""
    if track.status != "active":
        return

    state.age += dt
    state.hist_acc += dt
    while state.hist_acc >= config.HISTORY_DT - 1e-12:
        state.hist_acc -= config.HISTORY_DT
        track.history.append((track.x, track.y))
        if len(track.history) > config.HISTORY_LEN:
            track.history = track.history[-config.HISTORY_LEN :]

    if track.registered_friendly:
        track.raw_score = 0.0
        state.ema = 0.0
        track.threat_score = 0
        track.factors = []
        track.label = "friendly"
        track.target_asset = None
        track.eta = None
        track.priority = 0
        return

    h_pts, target, h_factors = heading_points(track, assets, track.target_asset)
    track.target_asset = target

    s_pts = steady_points(track.history)
    sp_pts = speed_points(track.speed)
    u_pts = 20.0

    factors: list[str] = []
    factors.extend(h_factors)
    if s_pts > 0:
        factors.append(f"+{int(round(s_pts))} steady path")
    if sp_pts > 0:
        factors.append(f"+{int(round(sp_pts))} speed match")
    factors.append("+20 unregistered")

    raw = h_pts + s_pts + sp_pts + u_pts
    track.raw_score = raw

    # Exponential smoothing toward raw with time constant SCORE_TAU.
    alpha = 1.0 - math.exp(-dt / config.SCORE_TAU) if config.SCORE_TAU > 0 else 1.0
    state.ema = state.ema + (raw - state.ema) * alpha
    track.threat_score = int(round(state.ema))

    if state.age < config.NEW_CONTACT_SECONDS:
        factors = ["new contact, classifying"] + factors

    track.factors = factors
    track.label = apply_label(
        track.label, float(track.threat_score), age=state.age, registered=False
    )

    if track.target_asset:
        asset = next((a for a in assets if a.name == track.target_asset), None)
        if asset is not None and track.speed > 0:
            dist = math.hypot(asset.x - track.x, asset.y - track.y)
            track.eta = dist / track.speed
            value = config.ASSET_VALUE.get(asset.kind, 0.2)
        else:
            track.eta = None
            value = 0.2
    else:
        track.eta = None
        value = 0.2

    if track.eta is None:
        urgency = 0.0
    else:
        urgency = _clamp01(1.0 - track.eta / 60.0)
    track.priority = int(
        round(track.threat_score * value * (0.5 + 0.5 * urgency))
    )


def update_scores(
    tracks: list[Track],
    assets: list[Asset],
    dt: float,
    states: dict[str, ScoreState],
) -> None:
    for track in tracks:
        if track.id not in states:
            states[track.id] = ScoreState()
        score_track(track, assets, dt, states[track.id])
