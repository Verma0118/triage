"""S0 + S4: FastAPI static page, WebSocket sim loop, MockUnit bridge."""

from __future__ import annotations

import json

import main
from fastapi.testclient import TestClient
from main import app


def test_get_root_returns_200():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200


def test_app_starts_with_no_drone_attached():
    """Importing and creating a client must not require hardware or yamspy."""
    with TestClient(app) as client:
        assert client is not None
        response = client.get("/")
        assert response.status_code == 200


def test_cards_json_served_with_placeholder():
    with TestClient(app) as client:
        response = client.get("/cards.json")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) and data
        assert data[0].get("placeholder") is True
        assert data[0].get("gap_type") == "fast_threat"


# --- S4 --------------------------------------------------------------------


def test_ws_delivers_state():
    main.TICK_SLEEP = 0.0
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            msg = ws.receive_json()
            assert isinstance(msg, dict)
            for key in (
                "t",
                "scenario",
                "phase",
                "replay",
                "assets",
                "tracks",
                "units",
                "plan",
                "events",
                "gaps",
                "alerts",
            ):
                assert key in msg, f"missing {key}"


def test_truth_never_in_ws_messages_across_night1():
    main.TICK_SLEEP = 0.0
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "load_scenario", "name": "juniper_night1"})
            ws.send_json({"type": "start"})
            first_seen: dict[str, float] = {}
            saw_ended = False
            # Cap message count; night1 ~650 ticks.
            for _ in range(8000):
                msg = ws.receive_json()
                blob = json.dumps(msg)
                assert "truth" not in blob, f"truth leaked at t={msg.get('t')}"
                # Scripted operator: approve proposed lines after 2 s sim time.
                t = float(msg.get("t", 0.0))
                for line in msg.get("plan") or []:
                    if line.get("approved"):
                        continue
                    lid = line["id"]
                    if lid not in first_seen:
                        first_seen[lid] = t
                    if t - first_seen[lid] + 1e-12 >= 2.0:
                        ws.send_json({"type": "approve", "line_ids": [lid]})
                if msg.get("phase") == "ended" and t > 1.0:
                    saw_ended = True
                    break
            assert saw_ended, "night1 never ended over /ws"


def test_two_clients_sim_advances_one_second_per_ten_ticks():
    """One loop for all sockets: 10 live ticks → +1.0 s sim time, not 2x."""
    main.TICK_SLEEP = 0.0

    def _await_live(ws):
        for _ in range(500):
            msg = ws.receive_json()
            if msg.get("phase") == "live":
                return float(msg["t"])
        raise AssertionError("never reached live")

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws1:
            with client.websocket_connect("/ws") as ws2:
                ws1.send_json({"type": "load_scenario", "name": "juniper_night1"})
                ws1.send_json({"type": "start"})
                t1_0 = _await_live(ws1)
                t2_0 = _await_live(ws2)
                t1 = t1_0
                t2 = t2_0
                for _ in range(10):
                    t1 = float(ws1.receive_json()["t"])
                    t2 = float(ws2.receive_json()["t"])
                # Each client sees +1.0 s over 10 ticks (not doubled by second client).
                assert abs(t1 - t1_0 - 1.0) < 1e-9, f"ws1 {t1_0} -> {t1}"
                assert abs(t2 - t2_0 - 1.0) < 1e-9, f"ws2 {t2_0} -> {t2}"


def test_malformed_message_does_not_kill_loop():
    main.TICK_SLEEP = 0.0
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            before = ws.receive_json()
            ws.send_text("not-json{{{")
            ws.send_json({"nope": True})
            ws.send_json({"type": 123})
            after = None
            for _ in range(20):
                after = ws.receive_json()
            assert after is not None
            assert "t" in after
            assert float(after["t"]) >= float(before["t"])


def test_approve_stale_id_changes_nothing():
    main.TICK_SLEEP = 0.0
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "load_scenario", "name": "juniper_night1"})
            msg = ws.receive_json()
            assert msg.get("phase") == "idle"
            ws.send_json({"type": "approve", "line_ids": ["U9:ZZ:engage"]})
            for _ in range(10):
                msg = ws.receive_json()
            assert all(
                e.get("msg") != "approved U9:ZZ:engage"
                for e in (msg.get("events") or [])
            )
            assert msg.get("phase") == "idle"
            assert msg.get("plan") == []
