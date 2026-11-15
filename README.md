# Triage

AI battle manager for the watch officer at a small outpost. Kearney x PERLab Hackathon, Startup Track A&D.

See `docs/PROJECT_CONTEXT.md` and `docs/BUILD_PLAN.md`.

## Setup

```bash
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Python **3.12** only (`.venv`). System `python3` on macOS is often 3.9 and will not work.

## Run commands

Never use `--reload`. Close Betaflight Configurator before any live/USB run.

### Mock (default)

```bash
cd ~/Desktop/triage
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/

### Live telemetry (no motors)

Props off. Battery in. Configurator closed. Hand ready on the battery lead if you later enable motors.

```bash
TRIAGE_MOCK=0 .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Optional port: `TRIAGE_PORT=/dev/cu.usbmodem…`

### Live + motors

Props **OFF**. Drone strapped. Hand on the battery lead. Physical stop = pull the battery.

```bash
TRIAGE_MOCK=0 TRIAGE_MOTORS=1 .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Standalone motor blip (human only):

```bash
TRIAGE_MOTORS=1 .venv/bin/python tools/bridge_test.py --motor
```

## Tests

```bash
.venv/bin/python -m pytest -q
```

## Pre-demo checklist

- Battery charged, Unit 1 shows ≥ 60%
- Props off, drone strapped, Configurator closed
- `TRIAGE_MOCK=0 TRIAGE_MOTORS=1`, no `--reload`
- Wi-Fi off, page still loads (proves offline)
- U1 card says LIVE and Variant A (use **Swap U1 to A** if the last run left it on B)
- One browser tab
- Backup video on the desktop
- **Zero tilt** once the board is mounted so the horizon reads level

## Scenarios

1. **Tower 22** — replay only (no plan bar)
2. **Night 1** — decoy / engage / fast-threat gap
3. After-action → **SWAP** to Variant B
4. **Night 2** — U1 engages
5. **Swap U1 to A** before re-running the full demo
