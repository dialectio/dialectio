from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_answers_head() -> None:
    """Uptime monitors check with HEAD; a 405 there looks like the site is down."""
    assert client.head("/health").status_code == 200
