"""Write validated rows to the store. Nothing is dropped or overwritten: every input row is counted once."""

import json
from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.mapping import map_columns
from app.ingest.parsers import EXTRA_COLUMNS, Sheet
from app.ingest.validate import ID_FIELD, validate_row
from app.models import ENTITY_MODELS, PROVENANCE_COLUMNS, IngestionBatch, RejectedRow
from app.schemas import IngestReport

# (entity, field) -> (parent table, parent id). A missing parent is a warning: the row loads and links later.
PARENTS = {
    ("accounts", "customer_id"): ("customers", "customer_id"),
    ("transactions", "sender_account"): ("accounts", "account_id"),
    ("logins", "customer_id"): ("customers", "customer_id"),
    ("applications", "customer_id"): ("customers", "customer_id"),
    ("claims", "customer_id"): ("customers", "customer_id"),
}
BATCH_INSERT_SIZE = 500


def _fields(entity: str) -> list[str]:
    return [c.name for c in ENTITY_MODELS[entity].__table__.columns if c.name not in PROVENANCE_COLUMNS]


def _fingerprint(record: dict, fields: list[str]) -> str:
    return json.dumps([record.get(f) for f in fields], default=str)


def _existing(session: Session, entity: str, fields: list[str]) -> dict[str, str]:
    model = ENTITY_MODELS[entity]
    id_field = ID_FIELD[entity]
    rows = session.execute(select(*[getattr(model, f) for f in fields])).mappings()
    return {row[id_field]: _fingerprint(dict(row), fields) for row in rows}


def _link_warnings(session: Session, entity: str, records: list[tuple[int, dict]]) -> list[dict]:
    warnings = []
    for (child, field), (parent, parent_id) in PARENTS.items():
        if child != entity or not records:
            continue
        known = set(session.scalars(select(getattr(ENTITY_MODELS[parent], parent_id))))
        missing = [(row, rec[field]) for row, rec in records if rec[field] not in known]
        if missing:
            warnings.append({
                "severity": "warning", "field": field, "rows": [row for row, _ in missing[:5]],
                "reason": f"{len(missing)} row(s) reference {parent} not loaded yet, e.g. '{missing[0][1]}'; "
                          "they will link once the parent records arrive",
            })
    return warnings


def ingest_sheet(session: Session, file_name: str, sheet: Sheet, entity: str,
                 override: dict[str, str] | None = None) -> IngestReport:
    columns = list(dict.fromkeys(c for _, row in sheet.rows for c in row if c != EXTRA_COLUMNS))
    mapping, unmapped = map_columns(entity, columns, override)
    fields = _fields(entity)
    id_field = ID_FIELD[entity]
    seen = _existing(session, entity, fields)
    batch_id = f"BATCH-{uuid4().hex[:12]}"
    report = IngestReport(batch_id=batch_id, file_name=file_name, entity_type=entity,
                          mapping=mapping, unmapped=unmapped)
    accepted: list[tuple[int, dict]] = []
    rejected: list[RejectedRow] = []

    for row_no, row in sheet.rows:
        record, problems = validate_row(entity, row, mapping)
        if problems:
            report.rejected += 1
            report.errors += [{"severity": "error", "row": row_no, **p} for p in problems]
            raw = {k: v for k, v in row.items() if k != EXTRA_COLUMNS}
            rejected.append(RejectedRow(batch_id=batch_id, row=row_no, raw=raw, reasons=problems))
            continue
        key, fingerprint = record[id_field], _fingerprint(record, fields)
        if key not in seen:
            seen[key] = fingerprint
            accepted.append((row_no, record))
        elif seen[key] == fingerprint:
            report.skipped += 1
        else:
            report.conflicts += 1
            report.errors.append({"severity": "conflict", "row": row_no, "field": id_field,
                                  "reason": f"{id_field} '{key}' already exists with different data; kept the original"})

    report.accepted = len(accepted)
    report.errors += _link_warnings(session, entity, accepted)
    session.add(IngestionBatch(
        batch_id=batch_id, file_name=file_name, sheet=sheet.name, entity_type=entity,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None), accepted=report.accepted,
        rejected=report.rejected, skipped=report.skipped, conflicts=report.conflicts,
        errors=report.errors, mapping=mapping, unmapped=unmapped,
    ))
    session.flush()
    session.add_all(rejected)
    source = dict(sheet.rows)
    rows = [{**rec, "batch_id": batch_id, "source_file": file_name, "source_row": row_no, "raw": source[row_no]}
            for row_no, rec in accepted]
    table = ENTITY_MODELS[entity].__table__
    for start in range(0, len(rows), BATCH_INSERT_SIZE):
        session.execute(table.insert(), rows[start:start + BATCH_INSERT_SIZE])
    session.commit()
    return report


def record_dict(row, entity: str) -> dict:
    return {f: getattr(row, f) for f in _fields(entity)}


def load_frames(session: Session) -> dict[str, pd.DataFrame]:
    """Every non-empty stored table as a detection input frame."""
    frames = {}
    for entity, model in ENTITY_MODELS.items():
        fields = _fields(entity)
        rows = session.execute(select(*[getattr(model, f) for f in fields])).all()
        if rows:
            df = pd.DataFrame(rows, columns=fields).astype(object)
            frames[entity] = df.where(df.notna(), None)
    return frames
