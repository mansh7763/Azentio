import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db import Base, SessionLocal, engine, init_db
from app.main import app
from app.models import AlertRow, CaseEventRow, CaseRow, DetectionRunRow

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(engine)  # drops the triggers too; alerts cannot be deleted row by row
    init_db()


@pytest.fixture
def run():
    client.post("/api/demo/load")
    return client.post("/api/detect/run").json()


def ato_case():
    items = client.get("/api/cases", params={"customer_id": "C002"}).json()["items"]
    return next(c for c in items if c["category"] == "account_takeover")


def count(model):
    with SessionLocal() as session:
        return session.query(model).count()


def bump_rule():
    assert client.put("/api/rules/TX-03", json={"weight": 0.26}).status_code == 200


@pytest.fixture
def restore_rules():
    yield
    client.post("/api/rules/reset")


def test_alerts_are_stored_and_listed_without_low_by_default(run):
    assert count(AlertRow) == len(run["alerts"])
    listed = client.get("/api/alerts").json()
    assert listed["items"] and all(a["band"] != "Low" for a in listed["items"])
    everything = client.get("/api/alerts", params={"include_low": True}).json()
    assert everything["total"] == len(run["alerts"])
    assert [a["score"] for a in listed["items"]] == sorted((a["score"] for a in listed["items"]), reverse=True)


def test_alert_detail_has_evidence(run):
    alert = client.get("/api/alerts").json()["items"][0]
    detail = client.get(f"/api/alerts/{alert['alert_id']}").json()
    assert detail["contributions"] and detail["evidence"] and detail["narrative"]
    assert client.get("/api/alerts/ALT-nope").status_code == 404


@pytest.mark.parametrize("params,check", [
    ({"customer_id": "C002"}, lambda a: "C002" in {a["customer_id"], *[e["entity_id"] for e in a["entities"]]}),
    ({"txn_id": "T-C002-ATO"}, lambda a: "T-C002-ATO" in a["event_ids"]),
    ({"band": "High"}, lambda a: a["band"] == "High"),
    ({"band": "Low"}, lambda a: a["band"] == "Low"),
    ({"category": "account_takeover"}, lambda a: a["category"] == "account_takeover"),
    ({"detection_type": "LG-02"}, lambda a: "LG-02" in a["detection_types"]),
    ({"product": "savings"}, lambda a: a["product"] == "savings"),
])
def test_each_filter(run, params, check):
    items = client.get("/api/alerts", params={"include_low": True, **params}).json()["items"]
    assert items and all(check(a) for a in items)


def test_date_filter_uses_event_time(run):
    times = sorted(a["event_time"][:10] for a in run["alerts"])
    day = times[-1]
    items = client.get("/api/alerts", params={"include_low": True, "date_from": day, "date_to": day}).json()["items"]
    assert items and all(a["event_time"][:10] == day for a in items)
    assert client.get("/api/alerts", params={"date_from": "not-a-date"}).status_code == 422


def test_filters_combine(run):
    params = {"customer_id": "C002", "band": "High", "category": "account_takeover", "detection_type": "CHAIN:ato_full",
              "product": "savings", "txn_id": "T-C002-ATO"}
    assert client.get("/api/alerts", params=params).json()["total"] == 1
    assert client.get("/api/alerts", params={**params, "band": "Low"}).json()["total"] == 0


def test_only_actionable_alerts_open_cases(run):
    actionable = [a for a in run["alerts"] if a["band"] in ("Medium", "High")]
    cases = client.get("/api/cases").json()
    assert cases["total"] == len(actionable) == count(CaseRow)
    bands = {c["band"] for c in cases["items"]}
    assert "Low" not in bands


def test_case_has_required_fields_and_affected_entity(run):
    case = ato_case()
    assert case["case_id"].startswith("CASE-") and case["customer_id"] == "C002" and case["account_id"]
    assert case["band"] == "High" and case["status"] == "New"
    device = next(c for c in client.get("/api/cases").json()["items"] if c["category"] == "shared_device")
    assert device["customer_id"]


def test_decisions_are_logged_and_original_alert_is_unchanged(run):
    case = ato_case()
    before = client.get(f"/api/cases/{case['case_id']}").json()["alerts"]
    first = client.post(f"/api/cases/{case['case_id']}/decision", json={"status": "Requires Investigation", "note": "call"})
    second = client.post(f"/api/cases/{case['case_id']}/decision", json={"status": "False Positive", "note": "verified"})
    assert first.status_code == 200 and second.json()["status"] == "False Positive"
    trail = [(e["from_status"], e["to_status"]) for e in second.json()["events"]]
    assert trail == [(None, "New"), ("New", "Requires Investigation"), ("Requires Investigation", "False Positive")]
    assert second.json()["alerts"] == before


@pytest.mark.parametrize("body", [
    {"status": "False Positive"},
    {"status": "False Positive", "note": "   "},
    {"status": "False Positive", "note": "ok", "actor": " "},
])
def test_decision_needs_actor_and_note(run, body):
    case_id = ato_case()["case_id"]
    assert client.post(f"/api/cases/{case_id}/decision", json=body).status_code == 422
    detail = client.get(f"/api/cases/{case_id}").json()
    assert detail["status"] == "New" and len(detail["events"]) == 1


def test_decision_can_be_reversed(run):
    case_id = ato_case()["case_id"]
    client.post(f"/api/cases/{case_id}/decision", json={"status": "False Positive", "note": "looks fine"})
    reversed_ = client.post(f"/api/cases/{case_id}/decision", json={"status": "Requires Investigation", "note": "new info"})
    assert reversed_.json()["status"] == "Requires Investigation"


def test_unknown_case_and_status(run):
    assert client.get("/api/cases/CASE-nope").status_code == 404
    case_id = ato_case()["case_id"]
    assert client.post(f"/api/cases/{case_id}/decision", json={"status": "Maybe"}).status_code == 422


def test_identical_rerun_returns_the_same_result_with_no_new_rows(run):
    alerts, cases = count(AlertRow), count(CaseRow)
    again = client.post("/api/detect/run").json()
    assert again["run"]["run_id"] == run["run"]["run_id"]
    assert sorted(a["alert_id"] for a in again["alerts"]) == sorted(a["alert_id"] for a in run["alerts"])
    assert (count(AlertRow), count(CaseRow), count(DetectionRunRow)) == (alerts, cases, 1)
    assert client.get("/api/alerts").json()["total"] > 0


def test_new_rule_version_keeps_history_and_reuses_cases(run, restore_rules):
    case = ato_case()
    client.post(f"/api/cases/{case['case_id']}/decision", json={"status": "Requires Investigation", "note": "call"})
    cases, alerts = count(CaseRow), count(AlertRow)
    bump_rule()
    second = client.post("/api/detect/run").json()
    assert second["run"]["run_id"] != run["run"]["run_id"]
    assert count(CaseRow) == cases and count(AlertRow) == alerts + len(second["alerts"])
    assert client.get("/api/alerts", params={"include_low": True}).json()["total"] == len(second["alerts"])
    detail = client.get(f"/api/cases/{case['case_id']}").json()
    assert detail["status"] == "Requires Investigation" and len(detail["alerts"]) == 2


def test_rerun_of_an_earlier_version_becomes_current_again(run, restore_rules):
    bump_rule()
    client.post("/api/detect/run")
    client.post("/api/rules/reset")
    back = client.post("/api/detect/run").json()
    assert back["run"]["run_id"] == run["run"]["run_id"]
    assert client.get("/api/alerts", params={"include_low": True}).json()["total"] == len(run["alerts"])


def test_trial_rules_are_not_saved(run):
    trial = client.post("/api/detect/run", json={"rules": {"bands": {"medium": 10}}})
    assert trial.status_code == 200
    assert count(DetectionRunRow) == 1


@pytest.mark.parametrize("statement", [
    "UPDATE alert SET payload = '{}'", "DELETE FROM alert",
    "UPDATE case_event SET note = 'x'", "DELETE FROM case_event",
])
def test_database_refuses_to_change_alerts_and_the_log(run, statement):
    with SessionLocal() as session:
        with pytest.raises(DBAPIError, match="immutable"):
            session.execute(text(statement))


def test_results_survive_a_new_session(run):
    case = ato_case()
    client.post(f"/api/cases/{case['case_id']}/decision", json={"status": "False Positive", "note": "ok"})
    with SessionLocal() as session:
        row = session.get(CaseRow, case["case_id"])
        assert row.status == "False Positive"
        assert session.query(CaseEventRow).filter_by(case_id=case["case_id"]).count() == 2
        payload = session.query(AlertRow).first().payload
    assert json.dumps(payload)


def test_customer_360_shows_stored_alerts(run):
    alerts = client.get("/api/customers/C002/360").json()["alerts"]
    assert any(a["primary_entity_id"] == "T-C002-ATO" for a in alerts)
