"""S0: FastAPI serves placeholder static page; app starts with no drone."""

from fastapi.testclient import TestClient

from main import app


def test_get_root_returns_200():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200


def test_app_starts_with_no_drone_attached():
    """Importing and creating a client must not require hardware or yamspy."""
    client = TestClient(app)
    assert client is not None
    response = client.get("/")
    assert response.status_code == 200
