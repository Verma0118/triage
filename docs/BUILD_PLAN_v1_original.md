# TRIAGE MVP Build Plan

Hackathon MVP. Kearney x PERLab Hackathon, Startup Track A&D. Submission due Sunday 8:30 AM.

## 1. What we're building

**Triage** is an AI battle manager for the watch officer at a small outpost. It:
- classifies incoming drones as **threat / decoy / unknown / friendly** using a transparent **threat score**
- ranks them by **priority** (threat score x asset value x urgency)
- recommends which interceptor to send (cheapest capable unit first)
- sends interceptors out early on unknowns, only commits at the last moment, and **recalls them if the track turns out to be a decoy**
- requires the operator to **approve every plan**
- flags a **capability gap** when no unit can catch a threat, then shows a **Velocity reconfiguration card** (swap modules on the shared core) and lets us **swap Unit 1 to Variant B**

**Unit 1 is a real drone** (Betaflight flight controller over USB). Units 2-4 are simulated.

### Hard rules
- **Keep math simple.** No trajectory physics. Straight lines, distance / speed, simple angles.
- **Everything runs offline** on one laptop.
- **Props OFF** and drone strapped down for any motor command. Motor value capped low, short duration.
- **Close Betaflight Configurator** before running the bridge (it holds the serial port).
- Story first. If a feature doesn't serve the demo, skip it.

## 2. Tech stack
- **Backend:** Python 3.11+, FastAPI, uvicorn, WebSocket, 10 Hz async loop
- **Hardware:** YAMSPy (MSP protocol over USB serial to Betaflight)
- **Frontend:** single `index.html` with vanilla JS + inline SVG, served by FastAPI. No React, no build step.
- **State:** in memory. No database.

## 3. File tree
```
triage/
  README.md
  requirements.txt          # fastapi, uvicorn[standard], yamspy, pyserial
  .gitignore
  config.py                 # serial port, variant specs, asset values, thresholds
  main.py                   # FastAPI app, WebSocket, 10 Hz loop, command handling
  models.py                 # dataclasses: Asset, Track, Unit, PlanLine, Event
  bridge.py                 # LiveUnit (YAMSPy) + MockUnit, same interface
  engine/
    __init__.py
    scoring.py              # threat score + factors, priority
    planner.py              # assignments, early launch, commit, recall, gap
    sim.py                  # moves tracks along waypoints, moves units
  scenarios.py              # juniper_night1, juniper_night2, tower22
  cards.json                # Velocity reconfiguration cards (real Velocity output pasted in)
  tools/
    bridge_test.py          # standalone FC test: print telemetry, motor blip, name write
    headless_run.py         # runs a scenario with no UI, prints the event timeline
  static/
    index.html              # whole UI
    outpost.svg             # fictional "Outpost Juniper" schematic
    tower22.svg             # simplified schematic based on public reporting
```

## 4. Config (`config.py`)
```python
SERIAL_PORT = "/dev/tty.usbmodem0x"   # Windows: "COM3"
USE_MOCK = False                       # True = MockUnit for Unit 1

MAP_W, MAP_H = 1000, 700               # SVG units (treat 1 unit = 1 m)
TICK_HZ = 10

VARIANTS = {
  "A": {"speed": 40, "max_range": 1500, "cost": 2000},   # placeholder numbers
  "B": {"speed": 75, "max_range": 1200, "cost": 5000},
}

ASSET_VALUE = {"housing": 1.0, "generator": 0.8, "comms": 0.7, "fuel": 0.7, "parking": 0.2}

BATTERY_V_MIN, BATTERY_V_MAX = 14.0, 16.8   # 4S, adjust to your pack
MOTOR_TEST_VALUE = 1080                     # cap, never above 1100
MOTOR_TEST_SECONDS = 1.0

THREAT_HIGH, THREAT_LOW = 70, 40     # >=70 threat, 40-69 unknown, <40 decoy
CAPABLE_SPEED_MARGIN = 1.2           # unit speed must beat threat speed x 1.2
COMMIT_ETA = 20                      # seconds, commit if score high and ETA under this
FORCE_COMMIT_ETA = 8                 # seconds, unknown defaults to threat under this
DECOY_RECALL_HOLD = 3                # seconds below THREAT_LOW while outbound -> recall
INTERCEPT_RADIUS = 15                # map units, unit "reaches" track
```

## 5. Data model (`models.py`)
```python
Asset:    name, x, y, kind            # kind keys into ASSET_VALUE

Track:    id, x, y, vx, vy, speed, heading,
          history: list[(x, y)],      # last ~20 positions
          registered_friendly: bool,
          truth: "real" | "decoy" | "friendly",   # BACKEND ONLY, never sent to UI
          target_asset: str | None,   # asset it's heading toward (computed)
          threat_score: int, factors: list[str],
          label: "threat" | "decoy" | "unknown" | "friendly",
          band: "high" | "med" | "low",
          eta: float | None, priority: int,
          status: "active" | "neutralized" | "impact" | "gone"

Unit:     id, variant, speed, max_range, range, cost,
          battery_v, battery_pct, ready: bool, live: bool,
          roll, pitch, yaw,           # live unit only
          x, y, home_x, home_y,
          state: "rack" | "outbound" | "returning" | "engaged" | "expended",
          assigned_track: str | None

PlanLine: unit_id, track_id, action: "launch_early" | "engage" | "return" | "best_effort" | "hold",
          reason: str, approved: bool, new: bool

Event:    t, kind ("contact","plan","approve","recall","neutralized","gap","impact","shelter","swap"), msg
```

## 6. WebSocket protocol (`/ws`)
**Server -> client, every tick:**
```json
{"t": 12.3, "scenario": "juniper_night1", "phase": "live",
 "assets": [...], "tracks": [... no "truth" field ...], "units": [...],
 "plan": [...], "events": [...], "gaps": [...], "alerts": ["Shelter: parking"]}
```
**Client -> server:**
```json
{"type": "load_scenario", "name": "juniper_night1"}
{"type": "start"} {"type": "pause"} {"type": "reset"}
{"type": "approve"}                       // approves all current unapproved plan lines
{"type": "veto", "unit_id": "U1"}
{"type": "swap_variant", "unit_id": "U1", "variant": "B"}
{"type": "toggle_mock"}
{"type": "show_after_action"}
```

## 7. Engine logic

### Threat score (`scoring.py`), 0-100, recomputed every tick
| Factor | Points | How |
|---|---|---|
| Heading to high-value asset | up to +35 | Angle between track velocity and vector to each asset. If < 20 deg, pick that asset. Points = 35 x ASSET_VALUE[asset]. |
| Steady, direct path | up to +25 | Std dev of heading over `history`. Low variance = 25, high variance = 0, linear in between. |
| Speed matches attack drone | up to +20 | 20 if speed inside an "attack" band (config), else scaled down. |
| Unregistered | +20 | If `registered_friendly`, score = 0 and label = friendly. Stop. |

- `factors` = human-readable strings, e.g. `"+35 heading to housing"`, `"+22 steady path"`
- **Label:** friendly if registered, else `>= THREAT_HIGH` threat (high), `>= THREAT_LOW` unknown (med), else decoy (low)
- **ETA** = distance to target asset / speed (None if no target)
- **Urgency** = clamp(1 - ETA / 60, 0, 1)
- **Priority** = round(threat_score x ASSET_VALUE[target] x (0.5 + 0.5 x urgency))

### Planner (`planner.py`), runs every tick, produces proposed lines
1. Sort active non-friendly, non-decoy tracks by priority, descending.
2. For each track, find **ready, unassigned** units that are **capable**: `unit.speed > track.speed x CAPABLE_SPEED_MARGIN` and `unit.range > distance(unit, track)`.
3. Pick the **cheapest** capable unit.
   - label threat and (ETA < COMMIT_ETA) -> `engage`
   - label threat, ETA still long -> `launch_early`
   - label unknown -> `launch_early`
4. If **no capable unit** and label is threat -> `best_effort` with the fastest ready unit + add a shelter alert for the target asset + log a `gap` event (once per track).
5. While outbound:
   - score drops below THREAT_LOW for DECOY_RECALL_HOLD seconds -> line becomes `return` (needs approval, reason "now likely decoy")
   - unknown with ETA < FORCE_COMMIT_ETA -> `engage` (reason "out of time, defaulting to threat")
6. Lines that change get `new: true` and `approved: false`. **Nothing moves until approved.**

### Sim (`sim.py`)
- Tracks move along scenario waypoints at constant speed (straight segments). Decoys use wandering or looping waypoints. Real threats head straight for an asset.
- Approved units move in a straight line toward their track's current position at unit speed.
- Unit within INTERCEPT_RADIUS:
  - `engage` / `best_effort` -> track `neutralized`, unit `expended`, event logged
- `return` -> unit flies home -> state `rack`, ready again, event "returned, not expended"
- Track reaches its asset -> status `impact`, event logged
- Live Unit 1: position is simulated, but **battery / ready / attitude are real**. `range = max_range x battery_pct`. If battery is unplugged or ready is false, Unit 1 is not ready and the planner drops it.

### Approve -> hardware
- When a line for **Unit 1** is approved -> bridge runs motor test (MOTOR_TEST_VALUE for MOTOR_TEST_SECONDS, then all motors to 1000). Run it in a background thread so the loop doesn't block.

### Swap
- `swap_variant U1 B` -> bridge writes craft name `TRIAGE-B-001`, re-reads name, parses variant from name, updates speed / max_range / cost from VARIANTS, logs a `swap` event.

## 8. Hardware bridge (`bridge.py`)
Same interface for both classes:
```python
class UnitSource:
    def read(self) -> dict      # {name, variant, battery_v, battery_pct, ready, roll, pitch, yaw}
    def motor_test(self) -> None
    def set_name(self, name: str) -> None
```
- **LiveUnit** uses YAMSPy over SERIAL_PORT at 115200. Polls about 5 Hz in a background thread and caches the latest values.
  - MSP codes: `MSP_NAME` (read craft name), `MSP_SET_NAME` (write), `MSP_ATTITUDE` (roll, pitch, yaw), `MSP_ANALOG` or `MSP_BATTERY_STATE` (voltage), `MSP_STATUS_EX` (arming disable flags -> ready), `MSP_SET_MOTOR` (8 x uint16 little-endian motor values).
  - **Check YAMSPy method names against the installed version.** It has helpers like `fast_read_attitude()` / `fast_read_analog()` and raw `send_RAW_msg` + `receive_msg` + `process_recv_data`.
  - Motor test only when disarmed, battery connected, props off. Always send all-1000 after.
  - Variant parsed from name: `TRIAGE-A-001` -> A. Unknown name -> A.
  - Battery pct = clamp((v - V_MIN) / (V_MAX - V_MIN), 0, 1).
  - **ready** = battery_v > V_MIN and no critical arming-disable flags (ignore flags that are normal on a bench, like RX loss, if needed for the demo).
- **MockUnit** returns plausible values (slow fake tilt, battery 15.8 V), no-op motor test, stores name in memory.
- If LiveUnit fails to connect -> log a warning and fall back to MockUnit automatically.

## 9. Scenarios (`scenarios.py`)
Each scenario = assets, units (positions on the rack), registered friendly flights, and a list of timed track spawns with waypoints, speed, truth.

**juniper_night1** (main demo, about 90 sec)
- t=2: friendly, registered, returning to base -> stays green
- t=5: unknown A, truth **decoy**, wandering path, slow -> Triage launches early, then recalls
- t=8: unknown B, truth **real**, straight at housing -> Triage engages
- t=40: fast real threat, truth **real**, speed above all units / 1.2, heading to **parking** -> gap, best effort, shelter alert, impact at parking (no personnel)

**juniper_night2** (after swap, about 30 sec)
- t=3: same fast real threat profile, heading to comms -> Unit 1 (Variant B) is capable -> engaged

**tower22** (replay, about 45 sec, calm, no score popups)
- tower22.svg schematic. Friendly registered drone returning from the north. At the same time, an unregistered low, slow track from the south heading for housing.
- Triage keeps the friendly green and flags the second track: "Unregistered, not friendly, heading for housing, ETA 0:40."

## 10. UI (`static/index.html`)
```
+--------------------------------------+-------------------+
|            MAP (SVG)                 |   THREAT LIST     |
| assets, tracks (colored by label),   | per track:        |
| unit paths, shelter alert highlight  | label + score     |
|                                      | -> asset, ETA     |
|                                      | priority          |
|                                      | factor breakdown  |
+--------------------------------------+-------------------+
| RACK: [U1 LIVE * 15.8V 92% tilt-icon READY A] [U2] [U3] [U4] |
+--------------------------------------------------------------+
| PLAN: U1 -> T2 launch early (reason) NEW | ...   [APPROVE]    |
+--------------------------------------------------------------+
| Scenario buttons | Start | Reset | Mock toggle | After-action |
+--------------------------------------------------------------+
```
- Colors: friendly green, unknown amber, threat red, decoy gray
- Unit 1 card: LIVE badge, voltage + %, small tilt indicator (rotate by roll, offset by pitch), variant, ready state
- After-action overlay: event list, gap count, then the matching card from `cards.json` with a **SWAP** button
- Big readable fonts. Dark theme.

`cards.json` example:
```json
[{"gap_type": "fast_threat", "unit_id": "U1", "to_variant": "B",
  "swap": ["motors", "props", "battery"], "keep": ["flight controller", "ESCs", "radio", "software"],
  "reuse_pct": 80, "cost_delta": 3000, "swap_minutes": 15,
  "source": "Kearney Velocity AI"}]
```
(Replace numbers with real Velocity output + BOM.)

## 11. Build steps + checks

| # | Step | Est. | Check (must pass before moving on) |
|---|---|---|---|
| 0 | **Setup:** repo, venv, requirements, empty FastAPI serving `static/index.html` | 15 min | `uvicorn main:app --reload` -> `localhost:8000` loads a page |
| 1 | **Bridge test** (`tools/bridge_test.py`) | 45 min | Tilting the drone changes printed roll / pitch. Voltage prints correctly with battery in. Motor blip works (props off). Name write + re-read shows new name. |
| 2 | **bridge.py** LiveUnit + MockUnit, auto fallback | 20 min | Unplugging USB falls back to mock without crashing. |
| 3 | **Loop + WebSocket**, units only | 30 min | Browser console logs state at 10 Hz, U1 values are live. |
| 4 | **UI shell:** map, rack cards, empty lists | 1 hr | **Tilt drone -> U1 card tilt indicator moves.** Unplug battery -> U1 shows NOT READY. |
| 5 | **Sim + scenarios:** tracks move on waypoints | 45 min | `tools/headless_run.py juniper_night1` prints tracks spawning and moving. Tracks animate on the map. |
| 6 | **Scoring:** threat score, factors, label, ETA, priority | 45 min | Real threat climbs above 70. Decoy drops below 40 within ~5-10 sec. Friendly stays green. Factor breakdown shows in the threat list. Truth never appears in WebSocket JSON. |
| 7 | **Planner + approve** | 1.5 hr | Nothing moves before approve. Decoy flow: launch early -> recall -> returns to rack, not expended. Real threat -> engaged -> neutralized. **Approving a U1 line spins U1 motors.** |
| 8 | **Gap + after-action + swap** | 1.5 hr | Fast threat -> "no capable unit" -> best effort + shelter alert + impact at parking + gap logged. After-action shows card. SWAP -> U1 name becomes TRIAGE-B-001 -> card shows Variant B. juniper_night2 -> U1 engages. |
| 9 | **Tower 22 scenario** | 45 min | Friendly stays green the whole time. Unregistered track flagged red with "heading for housing." |
| 10 | **Polish + backup** | rest | Reset works from any state. Mock toggle works mid-run. Full demo runs 3 times in a row clean. Screen recording saved. |

**Feature freeze: 3 AM.** Fixes only after that.

### Cut order if behind
1. Tower 22 scenario -> use a slide
2. Unit movement animations -> status text only
3. juniper_night2 -> end the demo on the swap

### Never cut
- Unit 1 live data on screen
- Decoy flow (launch early -> recall)
- Approve -> Unit 1 motor spin

## 12. Demo script (about 3 min)
1. Tower 22 replay (friendly vs. unregistered)
2. Pick up the drone, tilt it, U1 moves on screen
3. juniper_night1: decoy launched early and recalled, real threat engaged, approve spins U1
4. Unplug battery, U1 goes not ready, Triage replans
5. Fast threat, gap, shelter alert, impact at parking
6. After-action, Velocity card, swap U1 to Variant B
7. juniper_night2, U1 engages
8. Close: "Triage handles the attack. Modularity makes sure the next one goes better."
