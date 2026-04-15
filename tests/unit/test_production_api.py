import pytest

fastapi = pytest.importorskip("fastapi")
TestClient = pytest.importorskip("fastapi.testclient").TestClient

from core.atena_production_api import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_endpoint():
    response = client.get("/production/ready")
    assert response.status_code == 200
    assert "status" in response.json()


def test_gate_endpoint():
    response = client.get(
        "/production/gate",
        params={
            "window_days": 30,
            "min_success_rate": 0.1,
            "max_avg_latency_ms": 99999,
            "max_cost_units": 9999,
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] in {"GO", "NO_GO"}


def test_internet_challenge_endpoint():
    response = client.post("/production/internet-challenge", json={"topic": "retrieval augmented generation"})
    assert response.status_code == 200
    assert "status" in response.json()


def test_programming_probe_endpoint():
    response = client.post("/production/programming-probe", json={"prefix": "api_probe_test", "site_template": "basic"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "warn"}
    assert payload["total"] >= 3
