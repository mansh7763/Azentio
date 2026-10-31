import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


@pytest.mark.parametrize("method,path", [
    ("get", "/api/alerts"),
    ("get", "/api/cases"),
    ("get", "/api/dashboard/summary"),
    ("get", "/api/records/transactions"),
    ("get", "/api/customers/C001/360"),
    ("get", "/api/rules"),
    ("post", "/api/detect/run"),
    ("post", "/api/demo/load"),
])
def test_contract_routes_exist(method, path):
    assert getattr(client, method)(path).status_code == 200


def test_ingest_accepts_file():
    r = client.post("/api/ingest", data={"entity_type": "transactions"},
                    files={"file": ("t.csv", b"txn_id,amount\nT1,10\n", "text/csv")})
    assert r.status_code == 200 and r.json()["file_name"] == "t.csv"
    assert r.json()["rejected"] == 1


def test_no_public_reset_endpoint():
    assert client.post("/api/admin/reset").status_code in (404, 405)
