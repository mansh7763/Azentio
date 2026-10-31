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
    assert not run.indicators_skipped


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
