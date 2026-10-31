"""Turn one mapped text row into a canonical record, or into the reasons it was refused."""

import hashlib
import re
from datetime import datetime, timezone

from pydantic import ValidationError

from app.ingest.mapping import SCHEMAS
from app.ingest.parsers import EXTRA_COLUMNS

ID_FIELD = {
    "customers": "customer_id", "accounts": "account_id", "transactions": "txn_id",
    "logins": "event_id", "applications": "application_id", "claims": "claim_id",
}
AMOUNT_FIELDS = {"amount", "balance"}
POSITIVE_AMOUNTS = {"transactions", "claims"}
OUTCOMES = {
    "success": "success", "successful": "success", "ok": "success", "passed": "success", "true": "success",
    "fail": "fail", "failed": "fail", "failure": "fail", "denied": "fail", "false": "fail",
}
_NOT_NUMBER = re.compile(r"[^\d.\-]")


def _clean_amount(value: str) -> str:
    cleaned = _NOT_NUMBER.sub("", value)
    if not re.search(r"\d", value) or cleaned.count(".") > 1 or "-" in cleaned[1:]:
        return value  # leave it unparsable, so validation reports the original text
    return cleaned


def _login_id(record: dict) -> str:
    key = f"{record['customer_id']}|{record['timestamp'].isoformat()}|{record.get('device_id')}|{record['outcome']}"
    return "L-" + hashlib.sha256(key.encode()).hexdigest()[:12]


def _utc(value: datetime) -> datetime:
    """Stored naive in UTC; a timestamp with no zone is taken as UTC."""
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def _reason(error: dict) -> tuple[str, str]:
    field = str(error["loc"][0]) if error["loc"] else "row"
    if error["type"] == "missing" or error.get("input") is None:
        return field, "missing mandatory value"
    return field, f"invalid value '{error['input']}': {error['msg']}"


def validate_row(entity: str, row: dict, mapping: dict[str, str]) -> tuple[dict | None, list[dict]]:
    """Returns (record, []) or (None, [{field, reason}, ...])."""
    values = {}
    for source, target in mapping.items():
        text = row.get(source)
        text = text.strip() if isinstance(text, str) else text
        if text in ("", None):
            continue
        values[target] = _clean_amount(text) if target in AMOUNT_FIELDS else text

    problems = []
    if row.get(EXTRA_COLUMNS):
        problems.append({"field": "row", "reason": "more values than the header has columns"})
    try:
        record = SCHEMAS[entity](**values).model_dump()
    except ValidationError as exc:
        return None, problems + [dict(zip(("field", "reason"), _reason(e))) for e in exc.errors()]

    if entity in POSITIVE_AMOUNTS and record["amount"] <= 0:
        problems.append({"field": "amount", "reason": f"amount must be above zero, got {record['amount']:g}"})
    if entity == "logins":
        outcome = OUTCOMES.get(record["outcome"].lower())
        if outcome is None:
            problems.append({"field": "outcome", "reason": f"unknown outcome '{record['outcome']}'"})
        record["outcome"] = outcome
    if problems:
        return None, problems

    record = {k: _utc(v) if isinstance(v, datetime) else v for k, v in record.items()}
    if entity == "logins" and not record["event_id"]:
        record["event_id"] = _login_id(record)
    return record, []
