"""Triage FastAPI app: one sim loop, WebSocket broadcast, MockUnit bridge."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
from bridge import MockUnit
from engine.world import World

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
CARDS_PATH = ROOT / "cards.json"

log = logging.getLogger("triage")

# Tests set this to 0 so the loop does not wall-clock sleep.
TICK_SLEEP = 1.0 / config.TICK_HZ

world = World()
bridge = MockUnit()
sockets: set[WebSocket] = set()
_sim_task: asyncio.Task | None = None
_stop = False


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


async def broadcast_state() -> None:
    payload = world.to_public()
    text = json.dumps(payload)
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
    bridge = MockUnit()
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
    bridge.motors_off()
    bridge.close()


app = FastAPI(title="Triage", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/cards.json")
def cards():
    return FileResponse(CARDS_PATH, media_type="application/json")


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    sockets.add(ws)
    # Immediate snapshot so clients do not wait a full tick.
    try:
        await ws.send_text(json.dumps(world.to_public()))
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
                effects = world.handle_command(cmd)
                run_effects(effects)
            except Exception:
                log.exception("handle_command failed for %r", cmd)
    except WebSocketDisconnect:
        pass
    finally:
        sockets.discard(ws)
