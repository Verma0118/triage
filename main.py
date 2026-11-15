"""Triage FastAPI app: one sim loop, WebSocket broadcast, MockUnit bridge."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

import config
from bridge import LiveUnit, MockUnit
from engine.world import World
from models import Event

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
CARDS_PATH = ROOT / "cards.json"

log = logging.getLogger("triage")

# Tests set this to 0 so the loop does not wall-clock sleep.
TICK_SLEEP = 1.0 / config.TICK_HZ

world = World()
bridge: MockUnit | LiveUnit = MockUnit()
sockets: set[WebSocket] = set()
_sim_task: asyncio.Task | None = None
_stop = False


def _hw_event(msg: str) -> None:
    world.events.append(Event(t=world.t, kind="hw", msg=msg))


def make_bridge(use_mock: bool | None = None):
    """Build MockUnit or LiveUnit. LiveUnit falls back to mock source on connect fail."""
    if use_mock is None:
        use_mock = config.USE_MOCK
    if use_mock:
        return MockUnit()
    return LiveUnit(on_event=_hw_event, autostart=True)


def run_effects(effects: list) -> None:
    for eff in effects:
        if not eff:
            continue
        kind = eff[0]
        if kind == "motor_test":
            bridge.motor_test()
        elif kind == "motors_off":
            bridge.motors_off()
        elif kind == "set_name" and len(eff) >= 3:
            bridge.set_name(str(eff[2]))


def apply_set_mock(value: bool) -> None:
    """Close current bridge cleanly, then switch mock/live."""
    global bridge
    try:
        bridge.motors_off()
    except Exception:
        pass
    try:
        bridge.close()
    except Exception:
        pass
    bridge = make_bridge(use_mock=bool(value))


def public_state() -> dict:
    """World public snapshot plus bridge safety flags for the UI."""
    payload = world.to_public()
    # Motors never look armed unless a human set TRIAGE_MOTORS=1 (default off).
    payload["motors_enabled"] = bool(config.MOTORS_ENABLED)
    u1 = next((u for u in world.units if u.id == "U1"), None)
    payload["bridge_source"] = (u1.source if u1 else "mock")
    return payload


async def broadcast_state() -> None:
    text = json.dumps(public_state())
    dead: list[WebSocket] = []
    for ws in list(sockets):
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        sockets.discard(ws)


async def sim_loop() -> None:
    """One loop for the process. Opening more tabs must not speed up the sim."""
    global _stop
    while not _stop:
        try:
            world.apply_u1_snapshot(bridge.read())
            if world.phase == "live":
                world.step(config.DT)
            await broadcast_state()
        except Exception:
            log.exception("sim_loop tick failed")
        sleep = TICK_SLEEP
        if sleep > 0:
            await asyncio.sleep(sleep)
        else:
            # Yield to the event loop so WebSocket handlers can run in tests.
            await asyncio.sleep(0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _sim_task, _stop, bridge, world
    _stop = False
    world = World()
    bridge = make_bridge()
    sockets.clear()
    _sim_task = asyncio.create_task(sim_loop())
    yield
    _stop = True
    if _sim_task is not None:
        _sim_task.cancel()
        try:
            await _sim_task
        except asyncio.CancelledError:
            pass
        _sim_task = None
    try:
        bridge.motors_off()
    except Exception:
        pass
    try:
        bridge.close()
    except Exception:
        pass


app = FastAPI(title="Triage", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/cards.json")
def cards():
    return FileResponse(CARDS_PATH, media_type="application/json")


def gap_brief_text(w: World | None = None) -> str:
    """Velocity brief from run data. Empty string if no gap logged."""
    w = w if w is not None else world
    if not w.gaps:
        return ""
    # Prefer the fast_threat gap track (night1 C / night2 T1).
    gap = next((g for g in w.gaps if g.get("gap_type") == "fast_threat"), w.gaps[0])
    tid = gap.get("track_id")
    track = next((t for t in w.tracks if t.id == tid), None)
    if track is None:
        # Fall back to any track that matches gap story (speed 40).
        track = next((t for t in w.tracks if t.speed >= 40), None)
    if track is None:
        return ""

    contact_t = None
    for e in w.events:
        if e.kind == "contact" and tid and tid in e.msg:
            contact_t = e.t
            break
    impact_t = None
    for e in w.events:
        if e.kind == "impact" and tid and tid in e.msg:
            impact_t = e.t
            break
    # Impact may only be reflected in track status (no dedicated event).
    if impact_t is None and track.status == "impact":
        impact_t = w.t

    required = track.speed * config.CAPABLE_SPEED_MARGIN
    lines = [
        "TRIAGE VELOCITY BRIEF",
        f"Threat speed: {track.speed:g}",
        f"Target asset: {track.target_asset or 'unknown'}",
    ]
    if contact_t is not None and impact_t is not None:
        lines.append(
            f"Time from first contact to impact: {impact_t - contact_t:.1f} s"
        )
    lines.append(f"Required speed to be capable: {required:g} (threat x {config.CAPABLE_SPEED_MARGIN})")
    lines.append(f"Shortfall vs Variant A (30): {required - 30:g}")
    lines.append("Rack units:")
    for u in w.units:
        needed = track.speed * config.CAPABLE_SPEED_MARGIN
        why = (
            f"{u.speed:g} < {track.speed:g} x {config.CAPABLE_SPEED_MARGIN} = {needed:g}"
            if u.speed <= needed
            else "capable"
        )
        lines.append(f"  {u.id}: variant {u.variant}, speed {u.speed:g} — {why}")
    lines.append(
        "Keep the shared core (flight controller, ESCs, radio, software). "
        "Propose module swaps only."
    )
    return "\n".join(lines) + "\n"


@app.get("/gap_brief")
def gap_brief():
    return PlainTextResponse(gap_brief_text(world))


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    sockets.add(ws)
    # Immediate snapshot so clients do not wait a full tick.
    try:
        await ws.send_text(json.dumps(public_state()))
    except Exception:
        sockets.discard(ws)
        return
    try:
        while True:
            raw = await ws.receive_text()
            try:
                cmd = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("malformed ws message (not json)")
                continue
            if not isinstance(cmd, dict):
                log.warning("malformed ws message (not object)")
                continue
            try:
                if cmd.get("type") == "set_mock":
                    apply_set_mock(bool(cmd.get("value", True)))
                effects = world.handle_command(cmd)
                run_effects(effects)
            except Exception:
                log.exception("handle_command failed for %r", cmd)
    except WebSocketDisconnect:
        pass
    finally:
        sockets.discard(ws)
