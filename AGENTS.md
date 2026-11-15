# Rules for the coding agent

You are building the Triage hackathon MVP. The spec is `docs/BUILD_PLAN.md`. Background is `docs/PROJECT_CONTEXT.md`. Read both before writing code. `docs/BUILD_PLAN_v1_original.md` is history only, do not follow it.

## How work is assigned
- You are given **one gate** per session (S0, S1, ... or the code for an H gate). Build that gate only. Do not start the next one.
- Write the gate's tests first, from the "Must pass" column and the test lists in section 11. Then write the code.
- The gate is done when `pytest` is fully green, including every earlier gate's tests.
- If the gate is still red after two real attempts at a fix, stop and report what fails and why. Do not move on and do not paper over it.

## Things you must not do
- Do not weaken, skip, or delete a test to make it pass. Do not change thresholds in `config.py` to make a scenario pass. You may tune scenario waypoints and spawn positions.
- Do not run anything with `TRIAGE_MOCK=0` or `TRIAGE_MOTORS=1`. Do not run `tools/bridge_test.py`. Hardware commands are run by a person only. All of your runs use the mock.
- Do not add dependencies beyond `requirements.txt` in the plan. No React, no build step, no CDN links, no web fonts, no network calls at runtime.
- Do not import fastapi, serial, yamspy, or `bridge` anywhere under `engine/`.
- Do not use wall-clock time inside `engine/`.
- Do not send `truth` or `waypoints` to the client. Use `to_public()`.
- Do not add features that are not in the plan.

## Environment
- Python: `/opt/homebrew/bin/python3.12`. Create `.venv` with it. The system `python3` is 3.9 and will not work.
- Run tests with `.venv/bin/python -m pytest -q`.
- Never start uvicorn with `--reload` in instructions or scripts.

## UI work
Follow the accessibility list in section 10 of the plan. It is a requirement, not polish. Re-render list sections only when their content changes.

## When you finish a gate
Commit with message `gate-<id>: <summary>` and reply with:
1. Files added or changed
2. The final pytest output
3. Anything in the plan you could not follow exactly, and what you did instead
4. Anything a person must check by hand
