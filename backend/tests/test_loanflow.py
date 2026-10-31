import pandas as pd

from app.detect.dataset import Dataset, prepare
from app.detect.indicators.applications import application_signals
from app.detect.indicators.loanflow import loan_outflow_signals
from app.features.profiles import transaction_profiles


def _signals(ds, cfg):
    return loan_outflow_signals(ds, cfg, transaction_profiles(ds, cfg), application_signals(ds, cfg))


def test_cashout_fires_when_threshold_crossed(golden, cfg):
    ap03 = [s for s in _signals(golden, cfg) if s.indicator_id == "AP-03"]
    assert [s.entity_id for s in ap03] == ["T-C011-OUT2"]  # 160k (53%) after OUT1, 240k (80%) after OUT2
    s = ap03[0]
    assert s.strength == 1.0  # the application itself was flagged (AP-01 / ID-01)
    assert {"APP-C011", "T-C011-DISB", "T-C011-OUT0", "T-C011-OUT1", "T-C011-OUT2"} <= set(s.evidence_ids)
    assert "80%" in s.reason


def test_known_supplier_payment_is_not_cashout(golden, cfg):
    assert not [s for s in _signals(golden, cfg) if s.entity_id == "T-C016-SUP"]


def test_no_explicit_disbursement_link_no_signal(cfg):
    """Revision 4: without an explicit application/disbursement link, never infer loan proceeds."""
    accounts = pd.DataFrame([{"account_id": "A1", "customer_id": "C1"}])
    apps = pd.DataFrame([{"application_id": "APP1", "customer_id": "C1", "timestamp": "2026-09-01T10:00:00Z",
                          "disbursement_account": "A1"}])
    txns = pd.DataFrame([
        {"txn_id": "CR", "sender_account": "X", "timestamp": "2026-09-02T10:00:00Z", "amount": "100000",
         "beneficiary_account": "A1", "type": "credit"},
        {"txn_id": "O1", "sender_account": "A1", "timestamp": "2026-09-02T12:00:00Z", "amount": "90000",
         "beneficiary_account": "NEW1"},
    ])
    ds = prepare(Dataset.from_frames(accounts=accounts, applications=apps, transactions=txns), cfg)
    assert _signals(ds, cfg) == []
