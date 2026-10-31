"""Issue #6 fixes and #5 §2.4: config cannot drift, devices are windowed, households cannot hide a payout ring,
and skipped indicators name the missing column."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
import yaml

from app.detect.config import RULES_FILE, RulesConfig, Windows, load_rules
from app.detect.dataset import Dataset, prepare
from app.detect.indicators.devices import device_signals
from app.detect.registry import available

T0 = datetime(2026, 10, 1, 9, tzinfo=timezone.utc)


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _logins(rows):
    return pd.DataFrame([{"event_id": f"L{i}", "customer_id": c, "timestamp": _iso(t), "device_id": d,
                          "outcome": "success", "event_type": "login"} for i, (c, t, d) in enumerate(rows)])


def _customers(rows):
    return pd.DataFrame([{"customer_id": c, "name": n, "address": a, "city": "Pune"} for c, n, a in rows])


def _ids(signals):
    return [s.indicator_id for s in signals]


# --- config cannot drift -------------------------------------------------------------------------------------

def test_window_defaults_equal_rules_yaml():
    assert Windows().model_dump() == yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))["windows"]


def test_missing_param_is_an_error_not_a_silent_default():
    raw = _raw()
    raw["indicators"]["TX-04"] = {"weight": 0.4, "params": {"count": 5}}  # "minutes" removed
    with pytest.raises(ValueError, match="TX-04 is missing params: minutes"):
        RulesConfig.model_validate(raw)


def test_no_single_indicator_may_reach_high_alone():
    with pytest.raises(ValueError, match="must stay below 0.7"):
        load_rules({"indicators": {"TX-01": {"weight": 0.7}}})


def _raw():
    return yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))


# --- DV-01 time window (#5 §2.4) -----------------------------------------------------------------------------

UNRELATED = [("C1", "Asha Rao", "1 A St"), ("C2", "Ben Das", "2 B St"), ("C3", "Chen Li", "3 C St")]


def _device_run(spacing: timedelta, customers=UNRELATED, apps=None):
    cfg = load_rules()
    logins = _logins([(c, T0 + i * spacing, "DEV-X") for i, (c, _, _) in enumerate(customers)])
    frames = {"customers": _customers(customers), "logins": logins}
    if apps is not None:
        frames["applications"] = apps
    return device_signals(prepare(Dataset.from_frames(**frames), cfg), cfg)


def test_device_shared_within_window_is_flagged():
    signals = _device_run(timedelta(days=5))
    assert "DV-01" in _ids(signals)
    assert "within 30 days" in next(s for s in signals if s.indicator_id == "DV-01").reason


def test_device_passed_on_over_months_is_not_a_shared_device():
    """Three customers 100 days apart (a resold or reassigned phone) never overlap in one 30-day window."""
    assert _device_run(timedelta(days=100)) == []


def test_window_boundary():
    assert "DV-01" in _ids(_device_run(timedelta(days=15)))           # first-to-last 30 days: inside
    assert _device_run(timedelta(days=15, seconds=1)) == []           # 30 days + 2 s: outside


# --- household guard (#6, F22) ---------------------------------------------------------------------------------

FAMILY = [("H1", "Ravi Sharma", "55 Rose Lane"), ("H2", "Anita Sharma", "55 Rose Lane"), ("H3", "Ishaan Sharma", "55 Rose Lane")]


def _apps(payouts):
    return pd.DataFrame([{"application_id": f"APP-{c}", "customer_id": c, "product": "personal_loan",
                          "amount": "100000", "timestamp": _iso(T0), "disbursement_account": p}
                         for c, p in payouts])


def test_household_keeps_its_mitigation():
    signals = _device_run(timedelta(hours=2), FAMILY, _apps([("H1", "A-H1"), ("H2", "A-H2")]))
    assert "MT-HOUSE" in _ids(signals)


def test_household_converging_on_one_payout_loses_the_mitigation():
    signals = _device_run(timedelta(hours=2), FAMILY, _apps([("H1", "MULE-9"), ("H2", "MULE-9"), ("H3", "A-H3")]))
    assert "MT-HOUSE" not in _ids(signals)
    dv = next(s for s in signals if s.indicator_id == "DV-01")
    assert "MULE-9" in dv.reason and "household context is not applied" in dv.reason


# --- missing columns are named --------------------------------------------------------------------------------

def test_missing_column_is_reported_by_name():
    cfg = load_rules()
    logins = _logins([("C1", T0, "D1")]).drop(columns=["device_id"])
    ds = prepare(Dataset.from_frames(logins=logins), cfg)
    run, skipped = available(ds, cfg)
    assert skipped["DV-01"] == "missing column: logins.device_id"
    assert "LG-01" in run


def test_either_column_satisfies_an_alternative():
    cfg = load_rules()
    apps = _apps([("C1", None)]).assign(phone="9800000001")
    txns = pd.DataFrame([{"txn_id": "T1", "sender_account": "A1", "timestamp": _iso(T0), "amount": "10",
                          "beneficiary_account": "B1", "application_id": "APP-C1"}])
    ds = prepare(Dataset.from_frames(applications=apps, transactions=txns), cfg)
    run, skipped = available(ds, cfg)
    assert "AP-03" in run, skipped.get("AP-03")
