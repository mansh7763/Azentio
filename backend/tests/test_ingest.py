import io
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db import SessionLocal
from app.detect.router import load_dataset
from app.ingest.mapping import detect_entity, map_columns
from app.ingest.parsers import FileError, parse_file
from app.main import app
from app.models import ENTITY_MODELS, IngestionBatch, RejectedRow

client = TestClient(app)
TXN_HEADER = "txn_id,sender_account,timestamp,amount,currency,beneficiary_account,status\n"
GOOD = "00123,A1,2026-09-01T10:00:00Z,500,INR,B1,success\n"


@pytest.fixture(autouse=True)
def clean_store():
    with SessionLocal() as session:
        for model in (RejectedRow, IngestionBatch, *ENTITY_MODELS.values()):
            session.execute(delete(model))
        session.commit()


def upload(name: str, content: bytes, **data):
    return client.post("/api/ingest", files={"file": (name, content)}, data=data)


def totals(report, rows):
    assert report["accepted"] + report["rejected"] + report["skipped"] + report["conflicts"] == rows


def test_csv_keeps_leading_zeros():
    r = upload("t.csv", (TXN_HEADER + GOOD).encode()).json()
    assert r["accepted"] == 1 and r["entity_type"] == "transactions"
    assert client.get("/api/records/transactions").json()["items"][0]["txn_id"] == "00123"


def test_invalid_rows_have_visible_reasons_and_counts_reconcile():
    body = TXN_HEADER + GOOD + (
        "T2,A1,not-a-date,500,INR,B1,success\n"
        ",A1,2026-09-01T10:00:00Z,500,INR,B1,success\n"
        "T4,A1,2026-09-01T10:00:00Z,-5,INR,B1,success\n"
        "T5,A1,2026-09-01T10:00:00Z,abc,INR,B1,success\n"
    )
    r = upload("t.csv", body.encode()).json()
    assert (r["accepted"], r["rejected"]) == (1, 4)
    totals(r, 5)
    errors = {e["row"]: e for e in r["errors"] if e["severity"] == "error"}
    assert errors[3]["field"] == "timestamp" and "not-a-date" in errors[3]["reason"]
    assert errors[4]["field"] == "txn_id" and "missing" in errors[4]["reason"]
    assert errors[5]["field"] == "amount"
    assert errors[6]["field"] == "amount" and "abc" in errors[6]["reason"]
    stored = client.get(f"/api/ingest/batches/{r['batch_id']}/rejected").json()
    assert stored["total"] == 4 and stored["items"][0]["raw"]["timestamp"] == "not-a-date"


def test_reupload_is_skipped_not_duplicated():
    upload("t.csv", (TXN_HEADER + GOOD).encode())
    r = upload("t.csv", (TXN_HEADER + GOOD).encode()).json()
    assert (r["accepted"], r["skipped"]) == (0, 1)
    assert client.get("/api/records/transactions").json()["total"] == 1


def test_same_id_different_data_is_a_conflict_and_keeps_original():
    upload("t.csv", (TXN_HEADER + GOOD).encode())
    r = upload("t.csv", (TXN_HEADER + GOOD.replace(",500,", ",900,")).encode()).json()
    assert r["conflicts"] == 1 and r["accepted"] == 0
    assert client.get("/api/records/transactions").json()["items"][0]["amount"] == 500


def test_duplicates_inside_one_file():
    body = TXN_HEADER + GOOD + GOOD + GOOD.replace(",500,", ",900,")
    r = upload("t.csv", body.encode()).json()
    assert (r["accepted"], r["skipped"], r["conflicts"]) == (1, 1, 1)
    totals(r, 3)


def test_unknown_parent_warns_and_still_loads():
    r = upload("t.csv", (TXN_HEADER + GOOD).encode()).json()
    assert r["accepted"] == 1
    assert [e for e in r["errors"] if e["severity"] == "warning" and e["field"] == "sender_account"]


def test_aliases_and_override():
    body = b"TxnID,From Account,To Account,Txn Date,Amt,Weird\nT1,A1,B1,2026-09-01,10,x\n"
    r = upload("t.csv", body).json()
    assert r["entity_type"] == "transactions" and r["accepted"] == 1 and r["unmapped"] == ["Weird"]
    body = b"id,sender_account,beneficiary_account,timestamp,amount\nT2,A1,B1,2026-09-01,10\n"
    r = upload("t.csv", body, entity_type="transactions", mapping=json.dumps({"id": "txn_id"})).json()
    assert r["accepted"] == 1


def test_lookalike_columns_are_never_swapped():
    mapped, _ = map_columns("transactions", ["sender_account", "beneficiary_account"])
    assert mapped == {"sender_account": "sender_account", "beneficiary_account": "beneficiary_account"}


def test_unknown_override_target_is_refused():
    r = upload("t.csv", b"a,b\n1,2\n", entity_type="transactions", mapping=json.dumps({"a": "nope"}))
    assert r.status_code == 422 and "nope" in r.json()["detail"]


def test_excel_upload_and_extra_sheet_warning():
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer) as writer:
        pd.DataFrame({"customer_id": ["007"], "name": ["A"]}).to_excel(writer, sheet_name="customers", index=False)
        pd.DataFrame({"note": ["x"]}).to_excel(writer, sheet_name="notes", index=False)
    r = upload("c.xlsx", buffer.getvalue()).json()
    assert r["entity_type"] == "customers" and r["accepted"] == 1
    assert client.get("/api/records/customers").json()["items"][0]["customer_id"] == "007"
    assert any("notes" in e["reason"] for e in r["errors"])


def test_json_logins_normalise_outcome_and_generate_ids():
    rows = [{"customer_id": "C1", "timestamp": "2026-09-01T10:00:00+05:30", "outcome": "FAILED", "device": {"id": "D1"}}]
    r = upload("l.json", json.dumps({"records": rows}).encode(), entity_type="logins").json()
    assert r["accepted"] == 1 and r["mapping"]["device_id"] == "device_id"
    item = client.get("/api/records/logins").json()["items"][0]
    assert item["outcome"] == "fail" and item["event_id"].startswith("L-") and item["device_id"] == "D1"
    assert item["timestamp"].startswith("2026-09-01T04:30")  # stored in UTC
    assert upload("l.json", json.dumps(rows).encode(), entity_type="logins").json()["skipped"] == 1


def test_bad_outcome_is_rejected_with_reason():
    r = upload("l.csv", b"customer_id,timestamp,outcome\nC1,2026-09-01,maybe\n", entity_type="logins").json()
    assert r["rejected"] == 1 and "maybe" in r["errors"][0]["reason"]


@pytest.mark.parametrize("name,content,fragment", [
    ("t.pdf", b"x", "unsupported"), ("t.csv", b"  ", "empty"), ("t.csv", b"a,b\n", "no data"),
    ("t.json", b"{bad", "invalid JSON"), ("t.json", b"[1,2]", "object"), ("t.xlsx", b"not excel", "Excel"),
])
def test_unusable_files_explain_themselves(name, content, fragment):
    with pytest.raises(FileError, match=fragment):
        parse_file(name, content)


def test_unrecognised_file_asks_for_entity():
    r = upload("x.csv", b"foo,bar\n1,2\n")
    assert r.status_code == 422 and "entity_type" in r.json()["detail"]


def test_detect_entity():
    assert detect_entity(["account_id", "customer_id", "balance"]) == "accounts"
    assert detect_entity(["customer_id", "timestamp", "outcome"]) == "logins"
    assert detect_entity(["foo"]) is None


def test_demo_load_is_repeatable_and_reaches_detection():
    first = client.post("/api/demo/load").json()
    assert first["loaded"] > 0
    assert client.post("/api/demo/load").json()["loaded"] == 0
    ds = load_dataset()
    assert ds.has("transactions") and ds.has("logins") and ds.has("applications")
    run = client.post("/api/detect/run").json()
    high = {a["primary_entity_id"] for a in run["alerts"] if a["band"] == "High"}
    assert "T-C002-ATO" in high
    regular = [a for a in run["alerts"] if a["primary_entity_id"] == "T-C001-NEW"]
    assert all(a["band"] == "Low" for a in regular)


def test_empty_store_does_not_invent_results():
    run = client.post("/api/detect/run").json()
    assert run["alerts"] == []


def test_customer_360_uses_stored_records():
    client.post("/api/demo/load")
    body = client.get("/api/customers/C002/360").json()
    assert body["customer"]["name"] == "Priya Nair" and body["accounts"] and body["transactions"] and body["logins"]
