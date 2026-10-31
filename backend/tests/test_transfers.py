import math

import pandas as pd
import pytest

from app.detect.config import load_rules
from app.detect.dataset import Dataset, prepare
from app.detect.indicators.transfers import hv_threshold, transfer_signals
from app.features.profiles import denominator, transaction_profiles


@pytest.fixture(scope="module")
def profiles(golden, cfg):
    return transaction_profiles(golden, cfg)


@pytest.fixture(scope="module")
def signals(golden, cfg, profiles):
    by_txn = {}
    for s in transfer_signals(golden, cfg, profiles):
        by_txn.setdefault(s.entity_id, set()).add(s.indicator_id)
    return by_txn


def _frames(rows):
    """rows: (txn_id, customer, iso time, amount, payee)."""
    customers = sorted({r[1] for r in rows})
    return {
        "accounts": pd.DataFrame([{"account_id": f"A-{c}", "customer_id": c} for c in customers]),
        "transactions": pd.DataFrame([
            {"txn_id": t, "sender_account": f"A-{c}", "timestamp": ts, "amount": str(a), "beneficiary_account": p}
            for t, c, ts, a, p in rows
        ]),
    }


def test_fraud_amount_not_in_own_baseline(profiles):
    row = profiles.loc["T-C005-BIG"]
    assert row["prior_max"] <= 5000
    assert row["baseline_source"] == "customer"


def test_first_payment_to_later_repeated_payee_is_new(profiles):
    assert profiles.loc["T-C005-BIG", "is_new_payee"] is True
    assert profiles.loc["T-C005-LATER", "is_new_payee"] is False


def test_emi_mad_zero_no_error_and_no_tx01(profiles, signals):
    row = profiles.loc["T-C007-EMI"]
    assert row["prior_mad"] == 0
    assert row["denom"] >= 100 and math.isfinite(row["z"])
    assert "TX-01" not in signals.get("T-C007-EMI", set())


def test_denominator_floors():
    assert denominator(12000, 0, 100) == 1200
    assert denominator(0, 0, 100) == 100
    assert denominator(1000, 500, 100) == pytest.approx(741.3)


def test_no_customer_history_uses_global_baseline(cfg):
    rows = [(f"T{i}", "OLD", f"2026-09-0{i + 1}T10:00:00Z", 1000 + i, "B") for i in range(6)]
    rows.append(("TNEW", "NEW", "2026-09-09T10:00:00Z", 5000, "B2"))
    prof = transaction_profiles(prepare(Dataset.from_frames(**_frames(rows)), cfg), cfg)
    assert prof.loc["TNEW", "baseline_source"] == "global"
    assert math.isfinite(prof.loc["TNEW", "z"])


def test_first_ever_transaction_has_no_baseline(cfg):
    prof = transaction_profiles(prepare(Dataset.from_frames(**_frames([("T1", "C", "2026-09-01T10:00:00Z", 50, "B")])), cfg), cfg)
    assert prof.loc["T1", "baseline_source"] == "none"
    assert prof.loc["T1", "z"] == 0


def test_same_timestamp_order_is_deterministic(cfg):
    rows = [(f"T{i}", "C", "2026-09-01T10:00:00Z", 100 * (i + 1), f"B{i}") for i in range(7)]
    a = transaction_profiles(prepare(Dataset.from_frames(**_frames(rows)), cfg), cfg)
    b = transaction_profiles(prepare(Dataset.from_frames(**_frames(list(reversed(rows)))), cfg), cfg)
    pd.testing.assert_frame_equal(a.sort_index(), b.sort_index())


def test_regular_payer_no_tx01_tx02_tx03(signals):
    fired = signals.get("T-C001-NEW", set())
    assert not fired & {"TX-01", "TX-02", "TX-03"}
    assert "HV-01" in fired


def test_large_transfer_to_new_payee(signals):
    assert {"TX-01", "TX-02", "TX-03"} <= signals["T-C005-BIG"]


def test_fanout_emits_tx04_tx05(signals):
    assert {"TX-04", "TX-05"} <= signals["T-C006-F5"]


def test_short_history_skips_tx03(cfg):
    rows = [("T1", "C", "2026-09-01T10:00:00Z", 100, "B1"), ("T2", "C", "2026-09-02T10:00:00Z", 100, "B1"),
            ("T3", "C", "2026-09-03T10:00:00Z", 100, "B9")]
    ds = prepare(Dataset.from_frames(**_frames(rows)), cfg)
    prof = transaction_profiles(ds, cfg)
    assert prof.loc["T3", "is_new_payee"] is None
    assert not [s for s in transfer_signals(ds, cfg, prof) if s.indicator_id == "TX-03"]


def test_hv_threshold_is_p90_unless_configured(golden, cfg):
    amounts = golden.get("transactions")["amount"]
    assert hv_threshold(golden, cfg) == pytest.approx(amounts.quantile(0.9))
    fixed = load_rules({"indicators": {"HV-01": {"params": {"threshold": 5000}}}})
    assert hv_threshold(golden, fixed) == 5000


def test_reason_names_concrete_values(golden, cfg, profiles):
    tx01 = [s for s in transfer_signals(golden, cfg, profiles) if s.indicator_id == "TX-01" and s.entity_id == "T-C005-BIG"][0]
    assert "150,000" in tx01.reason and "×" in tx01.reason
