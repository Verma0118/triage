# Triage

AI battle manager for the watch officer at a small outpost. Kearney x PERLab Hackathon, Startup Track A&D.

See `docs/PROJECT_CONTEXT.md` and `docs/BUILD_PLAN.md`.

## Setup

```bash
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run (mock only)

```bash
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Do not use `--reload` with the live bridge. Open http://127.0.0.1:8000/

## Tests

```bash
.venv/bin/python -m pytest -q
```
