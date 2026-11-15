# TRIAGE MVP Build Plan (v2, reviewed)

Hackathon MVP. Kearney x PERLab Hackathon, Startup Track A&D. **Submission due Sunday 8:30 AM.**
Project background: `docs/PROJECT_CONTEXT.md`. Original plan: `docs/BUILD_PLAN_v1_original.md`.
This file supersedes v1. Where they disagree, this file wins.

## 0. What changed from v1 and why

| # | v1 problem | Fix in v2 |
|---|---|---|
| 1 | Planner re-ran every tick with no memory. Assignments would flip between units and un-approve themselves as priorities moved. | Sticky lines. A unit stays on its track. Only defined action transitions create a new line (section 7.3). |
| 2 | Raw score recomputed per tick drives labels directly, so labels flap around 70 / 40. | Smoothed score plus hysteresis plus a "new contact" window (7.2). |
| 3 | "Steady path" used the last ~20 positions at 10 Hz (2 s). A decoy built from straight waypoint legs looks perfectly steady inside every leg. The decoy would never classify as a decoy. | History sampled at 2 Hz over 6 s, circular std dev, decoy legs shorter than the window (7.2, 9). |
| 4 | A wandering decoy scores as decoy from the first tick, so "launch early then recall" never fires. | Decoy flies a straight first leg (reads unknown), then loiters (9). |
| 5 | Nothing said what a `launch_early` unit does when it reaches the track. | It shadows at a standoff distance until engage or return is approved (7.3). |
| 6 | Pursuit math lets a slow unit catch a fast threat head-on, so "best effort" would succeed and the gap story breaks. | A unit that is not capable always misses. Deterministic (7.4). |
| 7 | Fast threat aimed at parking scores 72, two points above the threat line. One tuning change and the gap never fires. | Gap detection does not depend on the label being threat (7.3 rule 6). |
| 8 | Unit 1 engages, becomes `expended`, then the script unplugs its battery and swaps its variant. | Scenario routes Unit 1 to the decoy (returns unused) and Unit 2 to the real threat (9). Tie-break by unit id makes this deterministic. |
| 9 | Unit 1 range = max_range x battery_pct. A sagging pack silently changes who the planner picks. | Scenario distances sized for 50% battery, tested at 50%, plus a pre-demo battery check (9, 13). |
| 10 | Motor test in a background thread while a 5 Hz poll thread uses the same serial port. Overlapping tests on repeated approvals. No stop on crash. | One serial owner thread, single-flight motor test, hard clamp in code, zero on exit, motors off by default (8). |
| 11 | Silent auto-fallback to mock while the card still says LIVE. | Every unit carries `source: live / mock`. UI shows it. Auto-retry live (8). |
| 12 | "Approve all" can approve a line that appeared as the operator clicked. | Approve sends the line ids that were on screen (6). |
| 13 | `truth` leak relied on remembering not to serialize it. | Explicit `to_public()` plus a test (5, gate S5). |
| 14 | Sim loop placement unspecified. A loop per WebSocket connection runs the sim at 2x with two tabs open. | One loop, started in app lifespan. Fixed dt, not wall clock (7.1). |
| 15 | `load_scenario` / `reset` vs. swapped variant undefined. Night 2 could reset Unit 1 back to A. | Variants survive load and reset (7.5). |
| 16 | Tower 22 would run the planner and pop launch proposals on the real-event replay. | `replay: True` scenarios run scoring only (9). |
| 17 | Re-rendering the UI at 10 Hz destroys the APPROVE button between mouse-down and mouse-up. Clicks get lost. | Re-render lists only when content changes (10). |
| 18 | Hardware was a blocking step for all software. Checks were manual eyeballing. | Two tracks. Software gates are automated tests against the mock. Hardware gates are human-run, in parallel (11). |
| 19 | `--reload`, hardcoded port, online installs, no early backup recording. | See 2, 4, 11. |
| 20 | Threat with long ETA got `launch_early`, then a second approval to engage. Four approvals in 20 seconds. | Threat -> `engage` directly. `launch_early` is for unknowns only (7.3). |
| 21 | `veto` had no defined behavior and is not in the demo. | Cut. Not approving is the veto. |

## 1. What we're building

**Triage** is an AI battle manager for the watch officer at a small outpost. It:
- classifies incoming drones as **threat / decoy / unknown / friendly** using a transparent **threat score**
- ranks them by **priority** (threat score x asset value x urgency)
- recommends which interceptor to send (cheapest capable unit first)
- sends an interceptor out early on unknowns, holds it at standoff, and **recalls it if the track turns out to be a decoy**
- requires the operator to **approve every plan line**
- flags a **capability gap** when no unit on the rack can catch a threat, then shows a **Velocity reconfiguration card** and lets us **swap Unit 1 to Variant B**

**Unit 1 is a real drone** (Betaflight flight controller over USB). Units 2-4 are simulated.

### Hard rules
- **Keep math simple.** Straight lines, distance / speed, simple angles.
- **Everything runs offline** on one laptop. No CDN, no web fonts, no network calls.
- **Props OFF** and drone strapped down for any motor command.
- **Close Betaflight Configurator** before running the bridge (it holds the serial port).
- **The engine is pure Python.** `engine/` imports nothing from FastAPI, the bridge, or serial. It must run headless.
- Story first. If a feature doesn't serve the demo, skip it.

## 2. Tech stack
- **Backend:** Python 3.12 (`/opt/homebrew/bin/python3.12`, the system `python3` is 3.9 and too old), FastAPI, uvicorn, WebSocket
- **Hardware:** YAMSPy 0.3.3 (MSP over USB serial). Fallback if YAMSPy costs more than 20 minutes: raw MSP v1 frames with pyserial (`$M<`, length, command, payload, XOR checksum).
- **Frontend:** single `static/index.html`, vanilla JS + inline SVG. No React, no build step.
- **State:** in memory. No database.
- **Tests:** pytest.
- Pin versions in `requirements.txt`. Install while online. Do **not** run uvicorn with `--reload` when the live bridge is on (the reloader restarts the process and can leave the serial port or a motor command hanging).

## 3. File tree
```
triage/
  AGENTS.md                 # rules for the coding agent
  README.md
  requirements.txt          # fastapi, uvicorn[standard], yamspy, pyserial, pytest, httpx
  .gitignore
  config.py
  main.py                   # FastAPI app, WebSocket, the one sim loop, command handling
  models.py                 # dataclasses + to_public()
  bridge.py                 # LiveUnit + MockUnit, same interface
  engine/
    __init__.py
    world.py                # World: holds state, step(dt), handle_command(cmd) -> effects
    scoring.py
    planner.py
    sim.py
  scenarios.py              # juniper_night1, juniper_night2, tower22
  cards.json
  tools/
    bridge_test.py          # standalone FC test, human-run only
    headless_run.py         # runs a scenario with a scripted operator, prints the timeline
  tests/
    test_sim.py  test_scoring.py  test_planner.py  test_gap_swap.py  test_server.py
  static/
    index.html
  docs/
```
Assets are drawn by the UI from the `assets` array in the WebSocket state, so map coordinates cannot drift from the engine. No hand-drawn SVG files with their own coordinates.

## 4. Config (`config.py`)
```python
import os
SERIAL_PORT    = os.environ.get("TRIAGE_PORT")           # None = autodetect first /dev/cu.usbmodem* (Windows: set COM3)
USE_MOCK       = os.environ.get("TRIAGE_MOCK", "1") == "1"    # default MOCK. Live needs TRIAGE_MOCK=0
MOTORS_ENABLED = os.environ.get("TRIAGE_MOTORS", "0") == "1"  # default OFF. Only a human sets this.

MAP_W, MAP_H = 1000, 700               # map units, shown as meters
TICK_HZ = 10
DT = 0.1                               # fixed sim step, seconds

VARIANTS = {                           # speeds are map units per second, tuned for demo pacing
  "A": {"speed": 30, "max_range": 1500, "cost": 2000},
  "B": {"speed": 60, "max_range": 1400, "cost": 5000},
}
ASSET_VALUE = {"housing": 1.0, "generator": 0.8, "comms": 0.7, "fuel": 0.7, "parking": 0.2}

BATTERY_V_MIN, BATTERY_V_MAX = 13.2, 16.8   # 4S. CONFIRM the pack at gate H1.
MOTOR_TEST_VALUE = 1080
MOTOR_HARD_CAP = 1100                       # enforced in bridge code, not just here
MOTOR_TEST_SECONDS = 1.0

THREAT_HIGH, THREAT_LOW = 70, 40
LABEL_HYSTERESIS = 3                 # must cross a threshold by this much to change label
SCORE_TAU = 1.0                      # seconds, smoothing time constant
NEW_CONTACT_SECONDS = 2.0            # label is "unknown" until this much track history exists
HISTORY_DT, HISTORY_LEN = 0.5, 12    # 6 s heading window
HEADING_CONE_DEG = 20
STEADY_FULL_DEG, STEADY_ZERO_DEG = 5, 40
ATTACK_SPEED_MIN, ATTACK_SPEED_MAX = 15, 45

CAPABLE_SPEED_MARGIN = 1.2
FORCE_COMMIT_ETA = 8
DECOY_RECALL_HOLD = 3
STANDOFF_RADIUS = 60
INTERCEPT_RADIUS = 15
```
Scenario speeds: normal real threat 18, fast threat 40, decoy 9, friendly 15.
Check: fast threat 40 x 1.2 = 48. Variant A (30) is not capable, Variant B (60) is.

## 5. Data model (`models.py`)
```python
Asset:    name, x, y, kind

Track:    id, x, y, speed, heading,
          history: list[(x, y)],
          registered_friendly: bool,
          truth: "real" | "decoy" | "friendly",   # BACKEND ONLY
          waypoints, wp_index,                     # BACKEND ONLY
          target_asset: str | None,
          raw_score: float, threat_score: int, factors: list[str],
          label: "threat" | "decoy" | "unknown" | "friendly",
          eta: float | None, priority: int,
          status: "active" | "neutralized" | "impact" | "gone"

Unit:     id, variant, speed, max_range, range, cost,
          battery_v, battery_pct, ready: bool,
          source: "live" | "mock" | "sim",        # U1 is live or mock. U2-4 are sim.
          roll, pitch, yaw,
          x, y, home_x, home_y,
          state: "rack" | "outbound" | "shadowing" | "returning" | "expended",
          assigned_track: str | None

PlanLine: id ("U1:T2:launch_early"), unit_id, track_id,
          action: "launch_early" | "engage" | "best_effort" | "return",
          reason: str, approved: bool

Event:    t, kind ("contact","plan","approve","recall","returned","neutralized","miss",
                   "gap","impact","shelter","swap","hw"), msg
```
Every model that goes to the UI has `to_public() -> dict` with an explicit field list. `truth`, `waypoints`, `wp_index` are never in it. Do not use `dataclasses.asdict` for the wire.

## 6. WebSocket protocol (`/ws`)
**Server -> client, every tick:**
```json
{"t": 12.3, "scenario": "juniper_night1", "phase": "idle|live|paused|ended", "replay": false,
 "assets": [...], "tracks": [...], "units": [...],
 "plan": [...], "events": [... last 50 ...], "gaps": [...], "alerts": ["Shelter: parking"]}
```
**Client -> server:**
```json
{"type": "load_scenario", "name": "juniper_night1"}
{"type": "start"} {"type": "pause"} {"type": "reset"}
{"type": "approve", "line_ids": ["U1:T2:launch_early"]}
{"type": "swap_variant", "unit_id": "U1", "variant": "B"}
{"type": "set_mock", "value": true}
```
- `approve` only approves ids that are currently proposed. Unknown ids are ignored.
- Unknown or malformed messages are ignored and logged. They never crash the loop.
- After-action is a client-side overlay built from `events`, `gaps`, and `/cards.json`. No server message.

## 7. Engine logic

### 7.1 Loop
- `World.step(DT)` advances exactly 0.1 s of sim time. It never reads the wall clock. Same inputs give the same timeline.
- `main.py` starts **one** asyncio task in the FastAPI lifespan. Each tick: read the bridge snapshot into Unit 1, call `world.step(DT)` if phase is `live`, broadcast to all sockets, run returned hardware effects, sleep to hold 10 Hz. Opening more tabs must not speed up the sim.
- `World.handle_command(cmd)` returns a list of effects, for example `("motor_test", "U1")` or `("set_name", "U1", "TRIAGE-B-001")`. `main.py` executes them against the bridge. The engine never touches hardware.

### 7.2 Threat score (`scoring.py`), 0-100
| Factor | Points | How |
|---|---|---|
| Heading to asset | up to +35 | Angle between track heading and the vector to each asset. Take the asset with the smallest angle under HEADING_CONE_DEG. Points = 35 x ASSET_VALUE. Once a target is picked, keep it while its angle stays under 30 deg. |
| Steady, direct path | up to +25 | **Circular** std dev of heading across `history` (sampled every HISTORY_DT, last HISTORY_LEN samples). 25 at <= STEADY_FULL_DEG, 0 at >= STEADY_ZERO_DEG, linear between. Fewer than 3 samples = 0 points. |
| Speed matches attack drone | up to +20 | 20 inside [ATTACK_SPEED_MIN, ATTACK_SPEED_MAX]. Below: 20 x speed / MIN. Above: 20. |
| Unregistered | +20 | If `registered_friendly`: score 0, label friendly, stop. |

- `raw_score` = sum. `threat_score` = round of the exponentially smoothed raw score (time constant SCORE_TAU).
- `factors` are strings, for example `"+35 heading to housing"`, `"+22 steady path"`.
- **Label:** friendly if registered. `unknown` with factor `"new contact, classifying"` while track age < NEW_CONTACT_SECONDS. After that: threat at >= 70, unknown at 40-69, decoy below 40, but a label only changes when the smoothed score is past the threshold by LABEL_HYSTERESIS.
- **ETA** = distance to target asset / speed. None if no target.
- **Urgency** = clamp(1 - ETA / 60, 0, 1). **Priority** = round(threat_score x ASSET_VALUE[target] x (0.5 + 0.5 x urgency)). No target: use 0.2 as the asset value.

### 7.3 Planner (`planner.py`)
The planner keeps its lines between ticks. Rules:

1. **Candidates:** active tracks labeled threat or unknown that have no line yet, sorted by priority descending.
2. **Capable** unit: state `rack`, `ready`, `unit.speed > track.speed x CAPABLE_SPEED_MARGIN`, and `unit.range >= distance(unit, track)`.
3. **Pick** the cheapest capable unit. Tie-break: lowest unit id. Label threat -> `engage`. Label unknown -> `launch_early`.
4. **Sticky:** once a line exists for a (unit, track) pair, proposed or approved, the planner does not move that track to another unit. Exception: the unit is still on the rack and becomes not ready. Then drop the line and re-plan the track, with the reason naming the dropped unit ("U1 not ready, reassigned").
5. **Transitions** for a unit already launched on a track. Each creates a new proposed line that needs approval. Until it is approved the unit keeps doing what was last approved.
   - `launch_early` -> `engage`: label became threat ("confirmed threat"), or label unknown and ETA < FORCE_COMMIT_ETA ("out of time, defaulting to threat").
   - `launch_early` -> `return`: smoothed score below THREAT_LOW for DECOY_RECALL_HOLD seconds ("now likely decoy").
6. **Capability gap:** the track is threat or unknown and **no unit in the whole roster**, in any state, has a variant fast enough. Log one `gap` event per track with `gap_type: "fast_threat"`. This is separate from "capable units exist but are busy", which is not a gap.
   - If the label is threat: propose `best_effort` with the fastest ready rack unit (tie: lowest id) and raise a shelter alert for the target asset.
7. **Track ended** (neutralized, impact, gone): remove its lines. Any unit still out on it returns home automatically with event "track gone, returning". No approval needed to come home from nothing.
8. **Nothing launches, commits, or recalls without an approved line.**
9. Replay scenarios (`replay: True`): the planner does not run.

### 7.4 Sim (`sim.py`)
- Tracks move along scenario waypoints at constant speed. Real tracks end at an asset: reaching it -> `impact`. Decoy and friendly tracks end off-map or at base -> `gone`. Impact is decided by scenario truth, not by the computed `target_asset`.
- Unit behavior by last approved line:
  - `launch_early`: fly straight at the track's current position. Inside STANDOFF_RADIUS: state `shadowing`, hold that distance.
  - `engage`: close to INTERCEPT_RADIUS -> track `neutralized`, unit `expended`, event.
  - `best_effort`: close to INTERCEPT_RADIUS -> event `miss` ("could not match speed"), unit returns home. The track continues. A non-capable unit never neutralizes.
  - `return`: fly home -> state `rack`, event `returned` ("returned, not expended").
- Unit 1: position is simulated. Battery, ready, attitude, and source come from the bridge snapshot. `range = max_range x battery_pct`. Live readiness only gates Unit 1 while it is on the rack. Once outbound in the sim, unplugging the real battery does not teleport it.
- Phase goes to `ended` when all spawns are done, no track is active, and no unit is away from the rack.

### 7.5 State rules
- `load_scenario`: clears tracks, plan, events, alerts, gaps, sim time. Units go back to rack and are un-expended. **Variants are kept.**
- `reset`: same as loading the current scenario again. Also sends motors-off through the bridge.
- `swap_variant`: only allowed when phase is `idle` or `ended` (swaps happen between attacks). Updates speed / max_range / cost from VARIANTS, logs `swap`. For Unit 1 it also emits the `set_name` effect.
- `set_mock`: allowed any time. Closes the serial port cleanly before switching.

### 7.6 Approve -> hardware
- Approving a **launch** line (`launch_early`, `engage`, `best_effort`) for a unit with `source: live` that is on the rack emits one `motor_test` effect. `return` lines never spin motors.

## 8. Hardware bridge (`bridge.py`)
```python
class UnitSource:
    def read(self) -> dict      # {source, name, variant, battery_v, battery_pct, ready, armed, roll, pitch, yaw, age}
    def motor_test(self) -> bool    # returns immediately. False if refused.
    def set_name(self, name: str) -> bool
    def motors_off(self) -> None
    def close(self) -> None
```
**LiveUnit**
- One background thread owns the serial port. Nothing else reads or writes it. Polling (about 5 Hz), motor tests, and name writes all go through that thread's command queue. `read()` returns the cached snapshot and never blocks.
- Port: `TRIAGE_PORT` or autodetect. On macOS use `/dev/cu.usbmodem*`.
- MSP: `MSP_NAME`, `MSP_SET_NAME`, `MSP_ATTITUDE`, `MSP_ANALOG` or `MSP_BATTERY_STATE`, `MSP_STATUS_EX`, `MSP_SET_MOTOR`. Check method names against the installed YAMSPy.
- **ready** = snapshot age < 1 s and battery_v > BATTERY_V_MIN and gyro present. Ignore arming-disable flags that are always set on a USB bench (RX loss, MSP, throttle, and similar). Do not require "no arming flags" or Unit 1 will never be ready.
- **Motor test, all of these or refuse:** `MOTORS_ENABLED` is true, FC reports disarmed, battery_v > BATTERY_V_MIN, no motor test already running (single-flight: a second request while one runs is dropped). Value = `min(MOTOR_TEST_VALUE, MOTOR_HARD_CAP)`. Re-send the value every 100 ms for MOTOR_TEST_SECONDS, then send all-1000 three times in a `finally` block.
- **Motors off on every exit path:** `atexit`, SIGINT / SIGTERM handler, serial exception handler, `reset`, `close()`.
- Known limit: if the process is killed hard mid-test, the FC may hold the last motor value. **Physical stop is pulling the battery.** Someone has a hand on the battery lead whenever `TRIAGE_MOTORS=1`.
- **Name write:** `MSP_SET_NAME` then re-read. Do **not** send an EEPROM save, so a power cycle restores the original name. If the re-read does not match (newer Betaflight may want `MSP2_SET_TEXT`, find out at H2), keep the variant in app state and log an `hw` event "name write unverified". The swap must still work on screen.
- Variant parsed from name: `TRIAGE-A-001` -> A. Unknown name -> A.
- Battery pct = clamp((v - V_MIN) / (V_MAX - V_MIN), 0, 1).
- If attitude reads stuck at zero, the accelerometer is disabled in Betaflight. Enable it in Configurator.

**MockUnit:** slow fake tilt, battery 15.8 V, ready, `source: "mock"`, motor test logs and returns true, name stored in memory. Tests can set its battery and ready values.

**Fallback:** if LiveUnit cannot connect or loses the port, switch to MockUnit, log an `hw` event, and retry live every 3 s. The UI shows MOCK the moment this happens. Never show LIVE on mock data.

## 9. Scenarios (`scenarios.py`)
Each scenario: `replay` flag, assets, units (rack positions), timed track spawns with waypoints, speed, truth, registered flag. All four units start as Variant A unless swapped. Rack sits near the asset cluster. Keep every unit-to-track distance at proposal time under 600 map units so Unit 1 stays capable at 50% battery.

**juniper_night1** (about 75 s)
- t=2: friendly, registered, returning to base. Stays green.
- t=5: track A, truth **decoy**, speed 9. First leg straight for about 12 s, not aimed inside 20 deg of housing, generator, comms, or fuel. Then a loiter pattern with legs of 2-3 s and turns of 90 deg or more. Expected: unknown -> **U1** `launch_early` -> U1 shadows -> score falls -> `return` -> U1 back on rack, not expended.
- t=8: track B, truth **real**, speed 18, straight at housing from about 620 away. Expected: threat -> **U2** `engage` -> neutralized, U2 expended.
- t=50: track C, truth **real**, speed 40, straight at **parking**. Expected: gap logged, `best_effort`, shelter alert for parking, miss, impact at parking.

**juniper_night2** (about 30 s, run after the swap)
- t=3: speed 40 real threat at comms. Expected: U1 (Variant B) is the only capable unit -> `engage` -> neutralized.

**tower22** (`replay: True`, about 45 s)
- Friendly registered drone returning from the north. At the same time an unregistered slow track from the south heading for housing.
- Scoring only. No planner, no units launched, no alerts. Friendly stays green. Second track reads threat with factors including "heading to housing" and an ETA.
- Tone: respectful and factual. No effects.

Scenario waypoints may be tuned to pass the gate tests. Thresholds in `config.py` and assertions in tests may not be loosened to make a scenario pass without sign-off.

## 10. UI (`static/index.html`)
```
+--------------------------------------+-------------------+
|            MAP (SVG)                 |   THREAT LIST     |
+--------------------------------------+-------------------+
| RACK: [U1 LIVE 15.8V 92% tilt READY A] [U2] [U3] [U4]    |
+----------------------------------------------------------+
| PLAN: U1 -> T2 launch early (reason)   ...   [APPROVE]   |
+----------------------------------------------------------+
| Scenario buttons | Start | Pause | Reset | Mock | After-action |
+----------------------------------------------------------+
```
- Map positions update every tick by setting attributes on existing SVG nodes.
- **Threat list, plan, rack, and events re-render only when their content changes** (compare a JSON string of the section to the last one). Never rebuild the APPROVE button on a timer.
- APPROVE sends the ids of the lines currently on screen. Keyboard: `A` approves, and the button works with Enter / Space.
- WebSocket reconnects automatically after a drop.
- Unit 1 card: **LIVE or MOCK badge from `unit.source`**, voltage + %, tilt indicator, variant, ready state.
- After-action overlay: event list, gap count, matching card from `cards.json`, **SWAP** button (enabled only in idle / ended).
- Replay scenarios hide the plan bar and rack actions.
- Everything local. No CDN scripts, no web fonts.

**Accessibility (WCAG AA, required):**
- Real `<button>` elements. Visible focus ring. Everything works by keyboard.
- One `<h1>`. Regions as landmarks with headings in order.
- Label is always shown as text ("THREAT", "DECOY") next to the color. Never color alone.
- Text contrast >= 4.5:1 on the dark theme, UI parts >= 3:1. Check the amber and gray.
- `aria-live="polite"` on alerts and on the plan region. Because those only re-render on change, they announce on change, not 10 times a second.
- Map SVG has `role="img"` and a text title. The threat list is the text equivalent.
- After-action overlay traps focus, closes on Escape, returns focus to the button that opened it.
- Respect `prefers-reduced-motion`.

`cards.json` example (replace numbers with real Velocity output + BOM):
```json
[{"gap_type": "fast_threat", "unit_id": "U1", "to_variant": "B",
  "swap": ["motors", "props", "battery"], "keep": ["flight controller", "ESCs", "radio", "software"],
  "reuse_pct": 80, "cost_delta": 3000, "swap_minutes": 15,
  "source": "Kearney Velocity AI"}]
```

## 11. Build order and gates

Two tracks. **S gates** are built by the coding agent in mock mode and proven by `pytest`. **H gates** need a person at the drone and run in parallel. Nothing in the S track waits on hardware.

Rules for every gate:
- One gate per agent session. Write the gate's tests first, then the code.
- Gate passes only when its tests and **all earlier tests** pass. Then commit and tag `gate-S3`, etc.
- Fails twice after real attempts: stop and report. Do not push on with a red gate.
- The reviewer (Claude) re-runs the tests and reads the diff before the next gate starts.

### S track (agent, mock only)

| Gate | Build | Must pass |
|---|---|---|
| **S0** | Repo, venv on Python 3.12, pinned requirements, FastAPI serving a placeholder `static/index.html`, pytest wired. | `pytest` runs. `GET /` returns 200. App starts with no drone attached. |
| **S1** | `models.py`, `engine/sim.py`, `engine/world.py`, `scenarios.py`, `tools/headless_run.py`. Tracks only, no scoring, no planner. | Running night1 twice gives identical timelines. Tracks spawn at their scenario times. With nobody approving anything, B impacts housing and C impacts parking. Friendly and decoy end as `gone`. `World.step` has no wall-clock calls. `engine/` imports no fastapi / serial / bridge. |
| **S2** | `engine/scoring.py`. | Unit tests per factor, including heading wrap-around at +/-180. On night1: friendly is always `friendly` with score 0. B is `threat` within 4 s of spawn and never leaves it. A is `unknown` during its straight leg, becomes `decoy` within 10 s of starting to loiter, and **never** reads `threat`. No track changes label more than 3 times in a run. C is `threat` or `unknown`. `to_public()` has no `truth` or `waypoints`. |
| **S3** | `engine/planner.py`, approve handling, unit movement, MockUnit. `headless_run.py` gets a scripted operator (approve everything N seconds after it appears). | See list below. |
| **S4** | `main.py` loop + WebSocket, wired to World and MockUnit. | Test client on `/ws` receives state. The string `truth` never appears in any message across a full night1 run. Two connected clients: sim time still advances 1.0 s per 10 ticks. Malformed message does not kill the loop. `approve` with a stale id changes nothing. |
| **S5** | UI: map, threat list, rack, plan bar, approve, controls. | **Human check, 5 min:** night1 in mock plays through by clicking APPROVE. Clicks never get lost. Tab reaches every control. MOCK badge shows. |
| **S6** | Gap, after-action overlay, cards, swap, night2. | See list below. Then human check of the overlay and SWAP. |
| **S7** | Tower 22 replay. | Planner produces zero lines for the whole run. Friendly label is `friendly` on every tick. Unregistered track is `threat` with a "heading to housing" factor and a non-null ETA. UI hides the plan bar. |

**S3 tests**
- No approvals at all: every unit stays in `rack` for the whole run.
- Scripted operator (2 s delay): U1 gets `launch_early` on A. U1 reaches `shadowing`. A `return` line appears. After approval U1 ends in `rack`, ready, not expended, with a `returned` event.
- Same run: U2 gets `engage` on B. B ends `neutralized`. U2 ends `expended`.
- **Stickiness:** if the operator delays the first approval until after B spawns, A still belongs to U1 and B to U2.
- An approved line never flips back to unapproved. The same line id is never proposed twice.
- U1 on rack with a proposed line, then MockUnit set not ready: line is replaced by one for another unit, reason names U1.
- U1 `shadowing`, `return` proposed but never approved: U1 keeps shadowing, does not come home, does not engage.
- Unknown track with ETA under FORCE_COMMIT_ETA gets an `engage` proposal with the "out of time" reason.
- Track ends while a unit is out on it: unit comes home, lines for that track are gone.
- Approving a launch line for a `source: live` unit yields exactly one `motor_test` effect. Approving the same id twice yields no second effect. Approving `return` yields none.
- Whole night1 flow still passes with MockUnit battery_pct forced to 0.5.

**S6 tests**
- C produces exactly one `gap` event with `gap_type: "fast_threat"`, a `best_effort` line, a shelter alert naming parking, a `miss` event, and C ends `impact`. C is never `neutralized` in night1.
- `swap_variant` during `live` is refused. In `ended` it works: U1 speed / range / cost match Variant B, a `swap` event is logged, a `set_name` effect with `TRIAGE-B-001` is emitted.
- `load_scenario juniper_night2` after the swap: U1 is still B. U1 gets `engage`, track ends `neutralized`.
- night2 **without** the swap: gap again. This proves the swap is what fixed it.
- `reset` from every phase returns to a clean idle state with variants kept.

### H track (human at the drone, in parallel)

The agent may write this code. **Only a person runs it.** Read-only steps first.

| Gate | Do | Must pass |
|---|---|---|
| **H1** read-only, start right after S0 | `tools/bridge_test.py --read`. Battery in, props off, Configurator closed. | Port autodetects. Tilting changes roll and pitch with the right sign. Voltage matches a multimeter or the Configurator within 0.2 V. Confirm cell count and set BATTERY_V_MIN / MAX. Unplug battery: voltage near 0, ready false. Note the Betaflight version. |
| **H2** writes | `--name` then `--motor` with `TRIAGE_MOTORS=1`. Drone strapped, props off, hand on the battery lead. | Name write + re-read works, or the fallback is recorded. Motor blip runs about 1 s and stops by itself. Ctrl-C during the blip stops the motors. A second trigger during a blip is ignored. |
| **H3** integration, after S4 | Server with `TRIAGE_MOCK=0`. | U1 card shows LIVE and moves with the drone. Pull USB: card flips to MOCK within 2 s, no crash. Re-plug: back to LIVE. Pull battery: NOT READY. |
| **H4** full, after S6 | `TRIAGE_MOCK=0 TRIAGE_MOTORS=1`, full script. | Approving U1's launch spins the motors once. Recall does not. SWAP changes the craft name. Night 2 spins again. |

### Deadlines (Saturday evening -> Sunday morning)

| By | Done | If not |
|---|---|---|
| Sat 7:15 PM | S0. H1 started. | |
| Sat 8:30 PM | S1 + S2 | Stop and fix scoring before any planner work. |
| Sat 10:00 PM | S3. H2 done before the venue closes. | Planner is the core. Do not start UI polish until S3 is green. |
| Sat 11:30 PM | S4 + S5. **Record backup video #1 in mock.** | Cut unit movement animation, show status text. |
| Sun 1:00 AM | S6 + H3 | End the demo on the swap, cut night2. |
| Sun 2:00 AM | S7 + H4 | Tower 22 becomes a slide. |
| **Sun 3:00 AM** | **Feature freeze.** Fixes only. | |
| Sun 4:00 AM | Full live demo 3 times in a row clean. Final recording saved. | Submit backup video #1. |

### Never cut
- Unit 1 live data on screen
- Decoy flow (launch early -> recall)
- Approve -> Unit 1 motor spin

## 12. Demo script (about 3 min)
1. Tower 22 replay (friendly vs. unregistered)
2. Pick up the drone, tilt it, U1 moves on screen. Pull the battery: U1 NOT READY. Plug it back: READY.
3. juniper_night1: U1 launched early on the decoy (approve spins U1), real threat engaged by U2, U1 recalled and returns unused
4. Fast threat, gap, shelter alert, best effort misses, impact at parking
5. After-action, Velocity card, swap U1 to Variant B
6. juniper_night2, U1 engages (approve spins U1)
7. Close: "Triage handles the attack. Modularity makes sure the next one goes better."

The battery pull moved from mid-attack to step 2. Mid-attack it competes with live approvals and Unit 1 is usually in the air in the sim at that point. The replan behavior still exists and is tested in S3.

## 13. Pre-demo checklist
- Battery charged, Unit 1 shows >= 60%
- Props off, drone strapped, Configurator closed
- `TRIAGE_MOCK=0 TRIAGE_MOTORS=1`, no `--reload`
- Wi-Fi off, page still loads (proves offline)
- U1 card says LIVE and Variant A (swap back to A if the last run left it on B)
- One browser tab
- Backup video on the desktop
