import pandas as pd
import pytest

from app.detect.config import load_rules
from app.detect.dataset import Dataset, prepare


def test_from_csv_dir_keeps_ids_as_text(tmp_path):
    (tmp_path / "customers.csv").write_text("customer_id,name\n00123,Asha\n", encoding="utf-8")
    ds = Dataset.from_csv_dir(tmp_path)
    assert ds.get("customers").loc[0, "customer_id"] == "00123"
    assert ds.has("customers") and not ds.has("logins")


def test_prepare_derives_customer_and_device(golden):
    txns = golden.get("transactions").set_index("txn_id")
    ato = txns.loc["T-C002-ATO"]
    assert ato["customer_id"] == "C002"
    assert ato["device_id"] == "DEV-X"
    assert ato["device_link"] == "derived"


def _txn_frame(amount):
    return {
        "accounts": pd.DataFrame([{"account_id": "A1", "customer_id": "C1"}]),
        "transactions": pd.DataFrame([{
            "txn_id": "T1", "sender_account": "A1", "timestamp": "2026-10-01T10:00:00Z",
            "amount": amount, "beneficiary_account": "B1",
        }]),
    }


def test_prepare_rejects_unparseable_amount():
    with pytest.raises(ValueError, match="transactions.amount"):
        prepare(Dataset.from_frames(**_txn_frame("abc")), load_rules())


@pytest.mark.parametrize("raw,expected", [("1,50,000", 150000.0), ("₹2,000", 2000.0), (" 99.5 ", 99.5)])
def test_prepare_parses_formatted_amount(raw, expected):
    ds = prepare(Dataset.from_frames(**_txn_frame(raw)), load_rules())
    assert ds.get("transactions").loc[0, "amount"] == expected


def test_prepare_sorts_by_time_then_id():
    frames = _txn_frame("10")
    frames["transactions"] = pd.DataFrame([
        {"txn_id": "T2", "sender_account": "A1", "timestamp": "2026-10-01T10:00:00Z", "amount": "1", "beneficiary_account": "B"},
        {"txn_id": "T1", "sender_account": "A1", "timestamp": "2026-10-01T10:00:00Z", "amount": "1", "beneficiary_account": "B"},
    ])
    out = prepare(Dataset.from_frames(**frames), load_rules()).get("transactions")
    assert list(out["txn_id"]) == ["T1", "T2"]
    assert list(out["seq"]) == [0, 1]


def test_logins_without_event_id_get_stable_hash():
    frames = {"logins": pd.DataFrame([{"customer_id": "C1", "timestamp": "2026-10-01T10:00:00Z", "outcome": "fail"}])}
    a = prepare(Dataset.from_frames(**frames), load_rules()).get("logins").loc[0, "event_id"]
    b = prepare(Dataset.from_frames(**frames), load_rules()).get("logins").loc[0, "event_id"]
    assert a == b and a.startswith("L-")


def test_rules_version_changes_with_override():
    assert load_rules().version != load_rules({"indicators": {"TX-01": {"weight": 0.5}}}).version
    assert load_rules().indicators["TX-01"].weight == 0.45
