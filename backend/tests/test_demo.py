"""G9 and G10: the same logical data in any format, dirty files, re-runs and restarts."""

import filecmp

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.api.records import DEMO_DIR
from app.datagen.build_demo import GOLDEN, excel_bytes, json_bytes
from app.db import Base, engine, init_db
from app.detect.dataset import Dataset
from app.detect.engine import run_detection
from app.main import app

client = TestClient(app)
DIRTY = DEMO_DIR / "dirty" / "transactions_dirty.csv"


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(engine)
    init_db()
    yield
    client.post("/api/rules/reset")


def upload(name, content, **data):
    return client.post("/api/ingest", files={"file": (name, content)}, data=data).json()


def outcome(alerts):
    return {(a["primary_entity_id"], a["band"], a["score"]) for a in alerts}


def load_demo_and_run():
    client.post("/api/demo/load")
    return client.post("/api/detect/run").json()


def rows(name):
    return pd.read_csv(GOLDEN / f"{name}.csv", dtype=str, keep_default_na=False)


def test_demo_files_match_golden():
    message = "golden data changed: run python -m app.datagen.build_demo from backend/"
    assert filecmp.cmp(DEMO_DIR / "customers.csv", GOLDEN / "customers.csv", shallow=False), message
    assert pd.read_excel(DEMO_DIR / "transactions.xlsx", dtype=str, keep_default_na=False).equals(rows("transactions")), message
    assert len(pd.read_json(DEMO_DIR / "logins.json")) == len(rows("logins")), message


def test_mixed_formats_give_the_same_detections_as_the_source_data():
    run = load_demo_and_run()
    direct = run_detection(Dataset.from_csv_dir(GOLDEN))
    assert outcome(run["alerts"]) == {(a.primary_entity_id, a.band.value, a.score) for a in direct.alerts}
    assert len({a["alert_id"] for a in run["alerts"]}) == len(run["alerts"])


@pytest.mark.parametrize("name,encode", [
    ("t.csv", lambda f: f.to_csv(index=False).encode()),
    ("t.xlsx", lambda f: excel_bytes(f, "transactions")),
    ("t.json", json_bytes),
])
def test_each_format_stores_identical_records(name, encode):
    frame = rows("transactions").head(8)
    assert upload(name, encode(frame), entity_type="transactions")["accepted"] == 8
    items = client.get("/api/records/transactions", params={"limit": 8}).json()["items"]
    assert {(i["txn_id"], i["amount"], i["beneficiary_account"]) for i in items} == {
        (r.txn_id, float(r.amount), r.beneficiary_account) for r in frame.itertuples()}


def test_application_link_is_stored():
    client.post("/api/demo/load")
    linked = rows("transactions").query("application_id != ''")
    assert not linked.empty
    target = linked.iloc[0]
    items = client.get("/api/records/transactions", params={"limit": 500}).json()["items"]
    assert next(i for i in items if i["txn_id"] == target.txn_id)["application_id"] == target.application_id


def test_dirty_file_explains_every_row():
    client.post("/api/demo/load")
    report = upload(DIRTY.name, DIRTY.read_bytes())
    assert report["entity_type"] == "transactions" and report["unmapped"] == ["Branch"]
    assert (report["accepted"], report["rejected"], report["skipped"], report["conflicts"]) == (3, 5, 1, 1)
    errors = {e["row"]: e for e in report["errors"] if e["severity"] != "warning"}
    assert errors[5]["field"] == "timestamp" and "20/10/2026" in errors[5]["reason"]
    assert errors[6]["field"] == "amount" and "missing" in errors[6]["reason"]
    assert "above zero" in errors[7]["reason"] and "twelve" in errors[8]["reason"]
    assert errors[9]["field"] == "txn_id"
    assert errors[11]["severity"] == "conflict"
    warnings = [e for e in report["errors"] if e["severity"] == "warning"]
    assert "A-UNKNOWN" in warnings[0]["reason"]
    txns = client.get("/api/records/transactions", params={"limit": 500}).json()["items"]
    found = {t["txn_id"]: t for t in txns}
    assert found["00917"]["amount"] == 200000 and found["D-02"]["amount"] == 1500


def test_reload_rerun_decide_and_restart_keep_everything_stable():
    first = load_demo_and_run()
    assert client.post("/api/demo/load").json()["loaded"] == 0
    second = client.post("/api/detect/run").json()
    assert second["run"]["run_id"] == first["run"]["run_id"]
    cases = client.get("/api/cases").json()
    assert sorted(a["alert_id"] for a in second["alerts"]) == sorted(a["alert_id"] for a in first["alerts"])

    case_id = cases["items"][0]["case_id"]
    original = client.get(f"/api/cases/{case_id}").json()["alerts"]
    client.post(f"/api/cases/{case_id}/decision", json={"status": "Requires Investigation", "note": "call the customer"})
    client.post(f"/api/cases/{case_id}/decision", json={"status": "False Positive", "note": "customer confirmed"})

    engine.dispose()  # as a restart would: no open connections survive
    init_db()
    restarted = TestClient(app)
    assert [c["case_id"] for c in restarted.get("/api/cases").json()["items"]] == [c["case_id"] for c in cases["items"]]
    detail = restarted.get(f"/api/cases/{case_id}").json()
    assert detail["status"] == "False Positive" and len(detail["events"]) == 3
    assert detail["alerts"] == original


def test_rule_edits_survive_a_restart():
    before = client.get("/api/rules").json()["version"]
    assert client.put("/api/rules/TX-03", json={"weight": 0.27}).status_code == 200
    engine.dispose()
    rules = TestClient(app).get("/api/rules").json()
    assert rules["version"] != before and rules["indicators"]["TX-03"]["weight"] == 0.27
    client.post("/api/rules/reset")
    assert client.get("/api/rules").json()["version"] == before


def test_invalid_rule_edit_is_not_saved():
    before = client.get("/api/rules").json()["version"]
    assert client.put("/api/rules/TX-03", json={"weight": "heavy"}).status_code == 422
    assert client.get("/api/rules").json()["version"] == before


@pytest.mark.parametrize("limit,status", [(500, 200), (501, 422), (0, 422)])
def test_records_limit_is_capped(limit, status):
    assert client.get("/api/records/transactions", params={"limit": limit}).status_code == status
