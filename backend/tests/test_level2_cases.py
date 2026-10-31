import json

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine, init_db
from app.main import app
from app.models import AlertRow

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(engine)
    init_db()
    yield
    client.post("/api/rules/reset")


@pytest.fixture
def run():
    client.post("/api/demo/load")
    return client.post("/api/detect/run").json()


def holding(run, entity):
    alert = next(a for a in run["alerts"] if a["primary_entity_id"] == entity)
    return next(c for c in client.get("/api/cases").json()["items"] if alert["alert_id"] in c["alert_ids"])


def act(case_id, action, **body):
    return client.post(f"/api/cases/{case_id}/actions", json={"action": action, "note": "reviewed", "actor": "Harsh", **body})


def test_loan_chain_is_one_investigation_with_a_reason(run):
    case = holding(run, "T-C011-OUT2")
    assert case["case_id"] == holding(run, "APP-C011")["case_id"] == holding(run, "DEV-RING")["case_id"]
    assert "linked group" in case["grouping_reason"] and "DEV-RING" in case["grouping_reason"]


def test_same_customer_transfers_are_consolidated(run):
    case = holding(run, "T-C006-F4")
    assert case["case_id"] == holding(run, "T-C006-F0")["case_id"]
    assert "C006" in case["grouping_reason"] and "72 hours" in case["grouping_reason"]


def test_unrelated_customers_stay_separate(run):
    assert holding(run, "T-C002-ATO")["case_id"] != holding(run, "T-C006-F4")["case_id"]


def test_consolidation_loses_no_actionable_alert(run):
    cases = client.get("/api/cases").json()["items"]
    held = {i for c in cases for i in c["alert_ids"]}
    assert {a["alert_id"] for a in run["alerts"] if a["band"] != "Low"} <= held
    assert len(cases) < sum(a["band"] != "Low" for a in run["alerts"])


def test_queue_is_sorted_by_priority_with_factors(run):
    items = client.get("/api/cases").json()["items"]
    assert [c["priority"] for c in items] == sorted((c["priority"] for c in items), reverse=True)
    assert all(c["priority_factors"] for c in items)


@pytest.mark.parametrize("action,status", [
    ("confirm", "Requires Investigation"), ("false_positive", "False Positive"), ("request_info", "Awaiting Information"),
    ("escalate", "Escalated"), ("conclude", "Closed"),
])
def test_actions_set_status(run, action, status):
    case = holding(run, "T-C002-ATO")
    body = act(case["case_id"], action).json()
    assert body["status"] == status and body["events"][-1]["type"] == "action" and body["events"][-1]["actor"] == "Harsh"


def test_conclusion_can_confirm_fraud(run):
    assert act(holding(run, "T-C002-ATO")["case_id"], "conclude", outcome="Confirmed Fraud").json()["status"] == "Confirmed Fraud"


@pytest.mark.parametrize("action", ["recommend_hold", "recommend_verification"])
def test_recommendations_change_nothing_and_are_not_executed(run, action):
    case = holding(run, "T-C002-ATO")
    body = act(case["case_id"], action).json()
    assert body["status"] == case["status"]
    assert body["events"][-1]["detail"] == {"action": action, "recommendation": True, "executed": False}


@pytest.mark.parametrize("payload", [{"action": "confirm", "note": " "}, {"action": "confirm", "note": "x", "actor": " "},
                                     {"action": "nope", "note": "x"}, {"action": "reclassify", "note": "x"}])
def test_invalid_actions_are_refused(run, payload):
    case_id = holding(run, "T-C002-ATO")["case_id"]
    assert client.post(f"/api/cases/{case_id}/actions", json=payload).status_code == 422


def test_reclassify_keeps_the_original_and_survives_a_new_run(run):
    case = holding(run, "T-C002-ATO")
    before = client.get(f"/api/cases/{case['case_id']}").json()["alerts"]
    body = act(case["case_id"], "reclassify", band="Low").json()
    assert body["band"] == "Low" and body["system_band"] == "High"
    assert body["events"][-1]["detail"] == {"action": "reclassify", "from_band": "High", "to_band": "Low", "system_band": "High"}
    assert body["alerts"] == before
    client.put("/api/rules/TX-03", json={"weight": 0.26})
    client.post("/api/detect/run")
    after = client.get(f"/api/cases/{case['case_id']}").json()
    assert after["band"] == "Low" and after["system_band"] == "High"


def test_split_makes_a_new_case_and_keeps_alerts(run):
    case = holding(run, "T-C011-OUT2")
    moved = next(a for a in run["alerts"] if a["primary_entity_id"] == "DEV-RING")["alert_id"]
    alerts = client.get("/api/alerts", params={"include_low": True}).json()["total"]
    new = client.post(f"/api/cases/{case['case_id']}/split", json={"alert_ids": [moved], "reason": "family device", "actor": "Harsh"}).json()
    assert new["alert_ids"] == [moved] and "family device" in new["grouping_reason"]
    original = client.get(f"/api/cases/{case['case_id']}").json()
    assert moved not in original["alert_ids"] and original["events"][-1]["detail"]["new_case_id"] == new["case_id"]
    assert client.get("/api/alerts", params={"include_low": True}).json()["total"] == alerts


def test_split_survives_reconsolidation(run):
    case = holding(run, "T-C011-OUT2")
    moved = next(a for a in run["alerts"] if a["primary_entity_id"] == "DEV-RING")["alert_id"]
    new = client.post(f"/api/cases/{case['case_id']}/split", json={"alert_ids": [moved], "reason": "family device"}).json()
    total = client.get("/api/cases").json()["total"]
    client.put("/api/rules/TX-03", json={"weight": 0.26})
    second = client.post("/api/detect/run").json()
    assert second["run"]["run_id"] != run["run"]["run_id"]
    assert client.get("/api/cases").json()["total"] == total
    assert client.get(f"/api/cases/{new['case_id']}").json()["alert_ids"] == [moved]
    assert moved not in client.get(f"/api/cases/{case['case_id']}").json()["alert_ids"]


@pytest.mark.parametrize("body", [{"alert_ids": [], "reason": "x"}, {"alert_ids": ["ALT-nope"], "reason": "x"}])
def test_bad_split_is_refused(run, body):
    case_id = holding(run, "T-C011-OUT2")["case_id"]
    assert client.post(f"/api/cases/{case_id}/split", json=body).status_code == 422


def test_split_must_leave_something_behind(run):
    case = holding(run, "T-C011-OUT2")
    assert client.post(f"/api/cases/{case['case_id']}/split", json={"alert_ids": case["alert_ids"], "reason": "x"}).status_code == 422
    assert client.post(f"/api/cases/{case['case_id']}/split", json={"alert_ids": case["alert_ids"][:1], "reason": " "}).status_code == 422


def test_ai_assessment_is_labelled_and_can_be_corrected(run):
    case_id = holding(run, "T-C002-ATO")["case_id"]
    url = f"/api/cases/{case_id}/events"
    first = client.post(url, json={"type": "ai_assessment", "note": "Likely takeover", "actor": "assistant"}).json()["events"][-1]
    assert first["type"] == "ai_assessment" and first["detail"]["ai_generated"] is True
    body = client.post(url, json={"type": "correction", "note": "Customer confirmed", "detail": {"rejects": first["id"]}}).json()
    assert [e["type"] for e in body["events"][-2:]] == ["ai_assessment", "correction"]
    assert client.post(url, json={"type": "decision", "note": "x"}).status_code == 422


def test_report_downloads_as_json_and_markdown(run):
    case_id = holding(run, "T-C002-ATO")["case_id"]
    act(case_id, "recommend_hold")
    client.post(f"/api/cases/{case_id}/events", json={"type": "ai_assessment", "note": "Likely takeover"})
    r = client.get(f"/api/cases/{case_id}/report")
    assert "attachment" in r.headers["content-disposition"]
    data = json.loads(r.text)
    assert data["original_alerts"][0]["evidence"] and data["indicators"] and data["ai_assessments"]
    assert any(e["actor"] == "Harsh" for e in data["decisions_and_actions"])
    text = client.get(f"/api/cases/{case_id}/report", params={"format": "markdown"}).text
    assert case_id in text and "Likely takeover" in text and "Grouped because" in text
    assert client.get(f"/api/cases/{case_id}/report", params={"format": "pdf"}).status_code == 422
    assert client.get("/api/cases/CASE-nope/report").status_code == 404


def test_history_finds_earlier_reviews_by_entity(run):
    case_id = holding(run, "T-C002-ATO")["case_id"]
    act(case_id, "escalate")
    found = client.get("/api/cases/history", params={"entity_id": "c002"}).json()
    assert found["items"][0]["case_id"] == case_id and found["items"][0]["events"][-1]["note"] == "reviewed"
    assert client.get("/api/cases/history", params={"entity_id": "NOPE"}).json()["total"] == 0


def test_original_alert_rows_are_unchanged_by_case_work(run):
    with SessionLocal() as session:
        before = {(r.alert_id, json.dumps(r.payload, sort_keys=True)) for r in session.query(AlertRow)}
    case = holding(run, "T-C011-OUT2")
    act(case["case_id"], "reclassify", band="Low")
    client.post(f"/api/cases/{case['case_id']}/split", json={"alert_ids": case["alert_ids"][:1], "reason": "unrelated"})
    with SessionLocal() as session:
        assert before == {(r.alert_id, json.dumps(r.payload, sort_keys=True)) for r in session.query(AlertRow)}
