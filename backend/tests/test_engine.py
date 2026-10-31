import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from app.detect.dataset import Dataset
from app.detect.engine import run_detection
from app.main import app
from app.schemas import Alert, Band

GOLDEN = Path(__file__).resolve().parent / "golden"
EXPECTED_CASES = yaml.safe_load((GOLDEN / "expected.yaml").read_text(encoding="utf-8"))
ORDER = {Band.low: 0, Band.medium: 1, Band.high: 2}


@pytest.fixture(scope="module")
def golden_result(raw_golden):
    return run_detection(raw_golden)


def _matches(alerts, case):
    return [a for a in alerts if a.unit_type.value == case["unit_type"]
            and ("entity" not in case or a.primary_entity_id == case["entity"])
            and ("customer" not in case or a.customer_id == case["customer"])]


@pytest.mark.parametrize("case", EXPECTED_CASES, ids=lambda c: c["id"])
def test_golden_case(golden_result, case):
    found = _matches(golden_result.alerts, case)
    detail = [(a.primary_entity_id, a.score, a.band.value, a.category.value) for a in found]
    if case.get("no_alert"):
        assert not found, detail
    if "band" in case:
        assert any(a.band == Band(case["band"]) for a in found), detail
    if "min_band" in case:
        assert found and all(ORDER[a.band] >= ORDER[Band(case["min_band"])] for a in found), detail
    if "max_band" in case:
        assert all(ORDER[a.band] <= ORDER[Band(case["max_band"])] for a in found), detail
    if "category" in case:
        assert found and all(a.category.value == case["category"] for a in found), detail
    if case.get("one_alert_for"):
        assert len(found) == 1, detail
    if case.get("no_chain"):
        assert not any(c.indicator_id and c.indicator_id.startswith("CHAIN:") for a in found for c in a.contributions)


def test_contributions_sum_and_evidence_exist(golden_result):
    assert golden_result.alerts
    for a in golden_result.alerts:
        assert sum(c.points for c in a.contributions) == a.score, a.alert_id
        assert any(c.kind == "risk" for c in a.contributions), a.alert_id
        known = {row_id for rows in a.evidence.values() for row in rows for row_id in row.values() if isinstance(row_id, str)}
        for c in a.contributions:
            assert c.evidence_ids, (a.alert_id, c.indicator_id)
            assert set(c.evidence_ids) <= known, (a.alert_id, c.indicator_id, set(c.evidence_ids) - known)


def _dump(result):
    return json.dumps([a.model_dump(mode="json") for a in result.alerts], sort_keys=True)


def test_deterministic(raw_golden):
    assert _dump(run_detection(raw_golden)) == _dump(run_detection(raw_golden))


def test_row_order_independent(raw_golden):
    shuffled = Dataset({name: df.sample(frac=1, random_state=7).reset_index(drop=True)
                        for name, df in raw_golden.frames.items()})
    assert _dump(run_detection(shuffled)) == _dump(run_detection(raw_golden))


def test_dedupe_keys_unique(golden_result):
    keys = [a.dedupe_key for a in golden_result.alerts]
    assert len(keys) == len(set(keys))


def test_run_summary(golden_result):
    run = golden_result.run
    assert run.alerts_total == len(golden_result.alerts)
    assert sum(run.counts_by_band.values()) == run.alerts_total
    assert run.records_processed["transactions"] > 0
    assert set(run.indicators_skipped.values()) == {"disabled in rules"}  # only TX-02 (revision 4)


def test_only_customers_and_transactions(raw_golden):
    partial = Dataset({k: v for k, v in raw_golden.frames.items() if k in ("customers", "accounts", "transactions")})
    result = run_detection(partial)
    skipped = result.run.indicators_skipped
    for ind in ("LG-01", "LG-02", "LG-03", "DV-01", "DV-03", "AP-01", "AP-02"):
        assert ind in skipped and "missing" in skipped[ind]
    assert "TX-01" in result.run.indicators_run
    assert any(a.primary_entity_id == "T-C005-BIG" for a in result.alerts)


def test_rule_override_changes_version_and_scores(raw_golden):
    base = run_detection(raw_golden)
    tuned = run_detection(raw_golden, config=None, overrides={"indicators": {"TX-03": {"enabled": False}}})
    assert base.run.rules_version != tuned.run.rules_version
    assert "TX-03" in tuned.run.indicators_skipped


def test_detect_endpoint_returns_alerts():
    client = TestClient(app)
    body = client.post("/api/detect/run").json()
    assert body["alerts"] and body["run"]["alerts_total"] == len(body["alerts"])
    Alert.model_validate(body["alerts"][0])
    rules = client.get("/api/rules").json()
    assert rules["indicators"]["TX-01"]["weight"] == 0.45


def test_device_cluster_key_stable_when_logins_added(raw_golden):
    import pandas as pd
    before = {a.primary_entity_id: a.dedupe_key for a in run_detection(raw_golden).alerts}
    extra = pd.DataFrame([{"event_id": "L-EXTRA-RING", "customer_id": "C010", "timestamp": "2026-10-20T10:00:00Z",
                           "device_id": "DEV-RING", "outcome": "success", "event_type": "login"}])
    grown = Dataset({**raw_golden.frames, "logins": pd.concat([raw_golden.frames["logins"], extra], ignore_index=True)})
    after = {a.primary_entity_id: a.dedupe_key for a in run_detection(grown).alerts}
    assert after["DEV-RING"] == before["DEV-RING"]


def test_coverage_reported_separately_from_risk(golden_result):
    cov = golden_result.run.coverage
    assert cov["evaluated_units"] >= golden_result.run.alerts_total
    for key in ("insufficient_history", "unresolved_link", "derived_device_link"):
        assert key in cov
    assert cov["insufficient_history"] > 0


def test_future_rows_do_not_change_earlier_scores(raw_golden):
    """G6: cut the data at an event; its score must be the same as with the full data."""
    full = {a.primary_entity_id: a for a in run_detection(raw_golden).alerts}
    for entity, table, col in (("T-C005-BIG", "transactions", "txn_id"), ("APP-C011", "applications", "application_id"),
                               ("T-C002-ATO", "transactions", "txn_id")):
        cutoff = raw_golden.frames[table].set_index(col).loc[entity, "timestamp"]
        cut = Dataset({name: df[df["timestamp"] <= cutoff] if "timestamp" in df else df
                       for name, df in raw_golden.frames.items()})
        early = {a.primary_entity_id: a for a in run_detection(cut).alerts}
        assert early[entity].score == full[entity].score, entity
        assert [c.points for c in early[entity].contributions] == [c.points for c in full[entity].contributions]


def test_every_risk_reason_is_concrete(golden_result):
    """EX-03: each reason names a number or an identifier from the evidence, not just a rule name."""
    for a in golden_result.alerts:
        values = {str(v) for rows in a.evidence.values() for row in rows for v in row.values() if v is not None}
        for c in a.contributions:
            if c.kind == "risk":
                assert any(ch.isdigit() for ch in c.reason) or any(v in c.reason for v in values), (a.alert_id, c.reason)


def test_suspended_mitigation_is_stated(golden_result):
    """EX-05"""
    ato = [a for a in golden_result.alerts if a.primary_entity_id == "T-C002-ATO"][0]
    assert "suspended" in ato.narrative.lower()


def test_unresolved_account_counted_in_coverage(raw_golden):
    import pandas as pd
    orphan = pd.DataFrame([{"txn_id": "TX-ORPHAN", "sender_account": "A-UNKNOWN", "timestamp": "2026-10-20T10:00:00Z",
                            "amount": "90000", "currency": "INR", "beneficiary_account": "BEN-X", "status": "success"}])
    ds = Dataset({**raw_golden.frames,
                  "transactions": pd.concat([raw_golden.frames["transactions"], orphan], ignore_index=True)})
    assert run_detection(ds).run.coverage["unresolved_link"] == 1
