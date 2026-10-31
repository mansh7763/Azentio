import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


@pytest.mark.parametrize("method,path", [
    ("get", "/api/alerts"),
    ("get", "/api/alerts/ALT-1"),
    ("get", "/api/cases"),
    ("get", "/api/cases/CASE-1"),
    ("get", "/api/dashboard/summary"),
    ("get", "/api/records/transactions"),
    ("get", "/api/customers/C001/360"),
    ("get", "/api/rules"),
    ("post", "/api/detect/run"),
    ("post", "/api/demo/load"),
    ("post", "/api/admin/reset"),
])
def test_contract_routes_exist(method, path):
    assert getattr(client, method)(path).status_code == 200


def test_case_decision_placeholder():
    r = client.post("/api/cases/CASE-1/decision", json={"status": "False Positive", "note": "ok"})
    assert r.status_code == 200 and r.json()["status"] == "False Positive"


def test_ingest_placeholder_accepts_file():
    r = client.post("/api/ingest", files={"file": ("t.csv", b"txn_id,amount\nT1,10\n", "text/csv")})
    assert r.status_code == 200 and r.json()["file_name"] == "t.csv"
