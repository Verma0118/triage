# Remaining work (from Sat ~8:15 PM)

Done and tagged: S0, S1, S2, S2.1, S3, S3.1, S4, S5, S5.1, S6. H1 passed on the real drone.
Paste the prompts below into Cursor **one at a time, in order**. After each: run `.venv/bin/python -m pytest -q`. All green -> next. Red -> tell Cursor "tests are red, fix without loosening assertions or changing config.py".

Always: Betaflight Configurator tab closed. Never use `--reload`. Stop the server (Ctrl-C) before Cursor works, restart after.

---

## Prompt 1: S6.1 fix + S7 Tower 22

```
Read AGENTS.md and docs/BUILD_PLAN.md. Gates S0-S6 are done. Two steps, two commits.

STEP 1 - review fix. In juniper_night2 the fast threat T1 gets "launch_early" at t=4.9 and then a second "engage" approval at t=7.1, and is neutralized only 0.7 s later. Cause: the smoothed score ramps up from zero, so at the end of the new-contact window the label is still "unknown" for a track whose raw score is already a threat. Fix in engine/scoring.py: seed the smoothed score with the raw score at the first scoring tick after the new-contact window ends (no ramp from zero). Then make sure in juniper_night2 T1 spawns far enough that its ETA at spawn is at least 20 s, while unit-to-track distance when the line is proposed stays under 600. Add tests: in juniper_night2 after swap, T1's first and only launch line is U1 "engage" (never launch_early) and at least 6 s pass between that proposal and the time T1 would impact if nobody approved; in juniper_night1, C is "threat" within 3 s of spawn. All existing tests must stay green, including: A is unknown then decoy and never threat, B's only launch line is engage, the gap and best_effort flow for C. Tune scenario waypoints if needed. Do not change config.py. Commit "gate-S6.1: seed smoothed score, night2 single approval".

STEP 2 - build gate S7 only (sections 9 and 11 of docs/BUILD_PLAN.md): the tower22 replay. replay: True, scoring only, planner off, no alerts, no units launched. Friendly registered drone returning from the north stays "friendly" on every tick. Unregistered slow track from the south heading for housing reads "threat" with a "heading to housing" factor and a non-null ETA. UI in replay mode: plan bar hidden, rack actions hidden, a calm banner "Replay: simplified schematic based on public reporting", no flashing, no effects. Write the S7 tests first (planner produces zero lines for the whole run; friendly label on every tick; unregistered track threat with the factor and ETA). Commit "gate-S7: tower22 replay".

Do not touch tools/bridge_test.py. Do not run anything with TRIAGE_MOCK=0 or TRIAGE_MOTORS=1. Do not push. Use the report format from AGENTS.md.
```

Human check after: run night1 -> After-action -> SWAP -> night2 (one approve, U1 kills it) -> tower22 (no plan bar, friendly green, second track red).

---

## Prompt 2: LiveUnit bridge (SAFETY-CRITICAL, read the diff yourself)

```
Read AGENTS.md, section 8 of docs/BUILD_PLAN.md (including the "H1 facts" bullet), and tools/bridge_test.py. tools/bridge_test.py has been run on the real flight controller and its MSP calls are known to work: copy its approach for connect, identify, attitude, status, name read/write, and motors. Voltage must come from MSP_ANALOG only (YAMSPy mis-parses MSP_BATTERY_STATE on this firmware).

Build LiveUnit in bridge.py exactly per section 8, and wire main.py to use it when config.USE_MOCK is False:
- ONE background thread owns the serial port. Polling (~5 Hz), motor tests and name writes all go through that thread via a command queue. read() returns a cached snapshot and never blocks. No other thread touches the port.
- snapshot: source "live", name, variant (parsed from name, unknown -> A), battery_v, battery_pct, ready, armed, roll, pitch, yaw, age.
- ready = snapshot age < 1 s AND battery_v > BATTERY_V_MIN AND gyro present (activeSensors bit 5). Ignore RXLOSS / ANGLE / MSP / THROTTLE arming flags.
- motor_test(): refuse (return False, log an "hw" event) unless ALL of: config.MOTORS_ENABLED is True, FC reports disarmed, battery_v > BATTERY_V_MIN, no motor test currently running (single-flight; a second request during a run is dropped). Value = min(config.MOTOR_TEST_VALUE, config.MOTOR_HARD_CAP). Re-send every 100 ms for config.MOTOR_TEST_SECONDS, then all-1000 three times in a finally block.
- motors_off() sends all-1000 three times. Call it from: atexit, SIGINT and SIGTERM handlers, the serial-exception handler, the "reset" command, close(), and FastAPI lifespan shutdown.
- set_name(): MSP_SET_NAME then re-read. NEVER send an EEPROM save. If re-read mismatches, keep the variant in app state and log an "hw" event "name write unverified".
- On startup in live mode, if the craft name is not of the form TRIAGE-<A|B>-001, write TRIAGE-A-001.
- Fallback: if connect fails or the port drops, switch to MockUnit, log an "hw" event, retry live every 3 s. The snapshot's source must flip to "mock" immediately so the UI badge is honest. set_mock closes the port cleanly first.
- yamspy and serial are imported only inside LiveUnit code paths so the app and tests run with no drone and no port.

Tests (tests/test_bridge.py), using a fake board object injected into LiveUnit, NO real serial port:
- motor_test refused when MOTORS_ENABLED is False; when armed; when voltage <= BATTERY_V_MIN.
- motor value sent never exceeds MOTOR_HARD_CAP even if MOTOR_TEST_VALUE is set to 1500.
- two motor_test calls back to back -> only one run.
- after a run the last three motor frames are all-1000; same if the fake board raises mid-run.
- voltage is read via MSP_ANALOG, never MSP_BATTERY_STATE.
- connect failure -> source "mock"; app still starts.
- stale snapshot (age > 1 s) -> ready False.

You must NOT open the real serial port, must NOT run with TRIAGE_MOCK=0 or TRIAGE_MOTORS=1, must NOT run tools/bridge_test.py. All your runs use mock or the fake board. Do not change config.py thresholds. Do not push. Commit "gate-H3-code: LiveUnit bridge". Report per AGENTS.md and list every code path that can send a motor value above 1000.
```

Before running it live, check the diff yourself: search bridge.py for `send_RAW_MOTORS` / `MSP_SET_MOTOR`. There must be exactly one place that sends a value above 1000, and it must be behind the MOTORS_ENABLED + disarmed + voltage + single-flight checks and the hard cap.

---

## Human hardware steps (you, at the drone)

**H2 motor blip, standalone.** Props OFF. Drone strapped down. Battery in. Hand on battery lead.
```
cd ~/Desktop/triage
TRIAGE_MOTORS=1 .venv/bin/python tools/bridge_test.py --motor
```
Type YES. Pass = motors spin about 1 s and stop by themselves. Run again and hit Ctrl-C mid-spin: motors must stop. If motors ever keep spinning: pull the battery.
If nothing spins: ESCs may need the battery plugged in before USB, or motor protocol needs the FC armed-off motor test enabled. Tell Cursor what you saw. Do not raise the value above 1100.

**H3 live telemetry (no motors).** After Prompt 2 is committed:
```
TRIAGE_MOCK=0 .venv/bin/python -m uvicorn main:app --port 8000
```
Pass = U1 card says LIVE and the tilt indicator follows the drone. Pull USB -> MOCK within ~2 s, no crash. Re-plug -> LIVE. Pull battery -> NOT READY.

**H4 full demo with motors.**
```
TRIAGE_MOCK=0 TRIAGE_MOTORS=1 .venv/bin/python -m uvicorn main:app --port 8000
```
Pass = approving U1's launch on the decoy spins the motors once. Approving the recall does not. SWAP changes U1 to Variant B. night2 approve spins again.

---

## Prompt 3: polish (only after H3 works)

```
Read AGENTS.md and docs/BUILD_PLAN.md sections 11-13. All gates are built. Polish only, no new features:
1. Reset works cleanly from every phase and scenario, including mid-flight and with the after-action overlay open. Add a test for any case not covered.
2. Add a "Swap U1 back to A" control in the after-action overlay or controls bar (idle/ended only) so the demo can be re-run. Test it.
3. Mock toggle mid-run does not crash or lose sim state. Test with MockUnit.
4. Projector pass on static/index.html: nothing overlaps at 1440x800 and 1920x1080, the plan bar and APPROVE are always visible, U1 tilt indicator is easy to see from across a room. Add a roll/pitch zero-offset: a "Zero tilt" button that stores the current roll and pitch as the level reference (the board is mounted rotated).
5. README.md: exact run commands for mock, live, and live+motors, and the pre-demo checklist from section 13.
Keep all tests green. Do not change config.py thresholds. Do not run with TRIAGE_MOCK=0 or TRIAGE_MOTORS=1. Do not push. Commit "polish: reset, re-run, projector pass".
```

---

## Yours, no Cursor needed
- **Charge the battery.** It was 15.16 V (54%). Want 60%+ for the demo.
- **Silence the beeper** in Betaflight Configurator (Beeper + DShot Beacon: RX_LOST, RX_SET off). Turn back on before ever flying.
- **Velocity (V1):** run the fast-threat gap through Velocity, paste the result into `cards.json`, set `"placeholder": false`. If Variant B's speed changes it must stay above 48.
- **Push to GitHub** after each green gate: `git push origin main --tags`
- **Backup video #1 in mock tonight**, as soon as Prompt 1 is green. Do not wait for hardware.
- **Feature freeze 3 AM.** After that, fixes only.

## Cut order if behind
1. Tower 22 -> slide
2. night2 -> end demo on the swap
3. Live motors -> keep live tilt + battery, describe the motor spin

## Never cut
U1 live data on screen. Decoy launch-early -> recall. Approve -> U1 motor spin.
