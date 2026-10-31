"""Issue #5/#6 regressions: currency, failed funding and future identity evidence."""
from datetime import timedelta
import sys
from pathlib import Path

import pytest

from test_new_rules import CFG, T0, history, person, tx, world
from app.detect.indicators.applications import application_signals
from app.detect.indicators.flows import cumulative_signals, structuring_signals, passthrough_signals
from app.detect.indicators.loanflow import loan_outflow_signals
from app.detect.registry import available


@pytest.mark.parametrize("detector,amount", [(cumulative_signals, 6000), (structuring_signals, 8000)])
def test_flow_windows_do_not_add_different_currencies(detector, amount):
    when = T0 + timedelta(days=80)
    rows = history("C1") + [tx(f"D{i}", "C1", when + timedelta(hours=i), amount, f"NEW-{i}") for i in range(4)]
    ds, prof = world([person("C1")], rows)
    assert detector(ds, CFG, prof)
    for i, row in enumerate(rows[-4:]):
        row["currency"] = ["INR", "USD", "EUR", "GBP"][i]
    ds, prof = world([person("C1")], rows)
    assert detector(ds, CFG, prof) == []


@pytest.mark.parametrize("status,currency,amount,expected", [
    ("success", "INR", 10000, True), ("fail", "INR", 10000, False),
    ("success", "USD", 10000, False), ("success", "INR", 0, False),
])
def test_passthrough_requires_successful_same_currency_funding(status, currency, amount, expected):
    credit = tx("CR", "C1", T0, amount, "A-C1", kind="credit", sender="BANK")
    credit.update(status=status, currency=currency)
    rows = [credit] + [tx(f"O{i}", "C1", T0 + timedelta(hours=i+1), 2500, f"NEW-{i}") for i in range(3)]
    ds, prof = world([person("C1")], rows)
    signals = passthrough_signals(ds, CFG, prof)
    assert bool(signals) == expected
    if expected:
        assert set(signals[0].evidence_ids) == {"CR", "O0", "O1", "O2"}


@pytest.mark.parametrize("change", [None, "failed", "currency", "future_application", "outbound_reference", "zero"])
def test_loan_cashout_requires_valid_funding(change):
    app = {"application_id": "APP", "customer_id": "C1", "timestamp": T0.isoformat(),
           "disbursement_account": "A-C1"}
    credit = tx("CR", "C1", T0 + timedelta(hours=1), 10000, "A-C1", kind="loan_disbursement", sender="BANK")
    credit["application_id"] = "APP"
    if change == "failed": credit["status"] = "fail"
    if change == "currency": credit["currency"] = "USD"
    if change == "future_application": app["timestamp"] = (T0 + timedelta(days=1)).isoformat()
    if change == "outbound_reference": credit["type"] = "transfer"
    if change == "zero": credit["amount"] = "0"
    rows = [credit, tx("OUT", "C1", T0 + timedelta(hours=2), 8000, "NEW")]
    ds, prof = world([person("C1")], rows, apps=[app])
    assert bool(loan_outflow_signals(ds, CFG, prof, [])) == (change is None)


def test_id01_never_uses_a_future_customer_profile():
    people = [person("C1", phone="9000000001"), person("C2", phone="9000000002",
              onboarding_date=(T0 + timedelta(days=1)).isoformat())]
    apps = [{"application_id": "APP", "customer_id": "C1", "timestamp": T0.isoformat(), "phone": "9000000002"}]
    ds, _ = world(people, apps=apps)
    assert not [s for s in application_signals(ds, CFG) if s.indicator_id == "ID-01"]
    people[1]["onboarding_date"] = (T0 - timedelta(days=1)).isoformat()
    ds, _ = world(people, apps=apps)
    assert [s for s in application_signals(ds, CFG) if s.indicator_id == "ID-01"]


def test_missing_currency_is_reported_as_a_coverage_gap():
    rows = history("C1")
    for row in rows: row.pop("currency")
    ds, _ = world([person("C1")], rows)
    _, skipped = available(ds, CFG)
    for rule in ("TX-06", "TX-07", "TX-09"):
        assert "transactions.currency" in skipped[rule]


def test_independent_family_fixtures_do_not_share_one_landline():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evals"))
    from generate import Bank
    bank = Bank(2)
    for day in range(4): bank.family_landline(200 + day)
    phones = [c["phone"] for c in bank.customers]
    assert len(set(phones)) == 4
    assert all(phones[i] == phones[i + 1] for i in range(0, 8, 2))
    ds, _ = world(bank.customers, apps=bank.apps, accounts=bank.accounts)
    assert application_signals(ds, CFG) == []
