"""Ingestion, demo data, stored records and customer 360."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.alert_store import involves_customer, latest_alerts
from app.db import get_session
from app.detect.dataset import TABLES
from app.ingest.mapping import SCHEMAS, detect_entity
from app.ingest.parsers import EXTRA_COLUMNS, FileError, Sheet, parse_file
from app.ingest.store import ingest_sheet, record_dict
from app.ingest.validate import ID_FIELD
from app.models import ENTITY_MODELS, IngestionBatch, RejectedRow
from app.schemas import IngestReport

router = APIRouter(tags=["records"])

DEMO_DIR = Path(__file__).resolve().parents[2] / "tests" / "golden"  # replaced by datagen fixtures in step 11


def _columns(sheet: Sheet) -> list[str]:
    return list(dict.fromkeys(c for _, row in sheet.rows for c in row if c != EXTRA_COLUMNS))


def _choose_sheet(sheets: list[Sheet], entity_type: str | None) -> tuple[Sheet, str, list[Sheet]]:
    """The first sheet we can place. Any other sheet is reported, never silently ignored."""
    for sheet in sheets:
        entity = entity_type or detect_entity(_columns(sheet), sheet.name)
        if entity:
            return sheet, entity, [s for s in sheets if s is not sheet]
    columns = ", ".join(_columns(sheets[0])[:12])
    raise HTTPException(422, f"could not tell what this file holds (columns: {columns}); choose an entity_type")


@router.post("/ingest", response_model=IngestReport)
async def ingest(file: UploadFile = File(...), entity_type: str | None = Form(None), mapping: str | None = Form(None),
                 session: Session = Depends(get_session)):
    if entity_type and entity_type not in SCHEMAS:
        raise HTTPException(422, f"unknown entity_type '{entity_type}'; use one of {', '.join(SCHEMAS)}")
    try:
        override = json.loads(mapping) if mapping else None
    except json.JSONDecodeError:
        raise HTTPException(422, "mapping must be JSON: {source_column: canonical_field}") from None
    file_name = file.filename or "upload"
    try:
        sheets = parse_file(file_name, await file.read())
        sheet, entity, others = _choose_sheet(sheets, entity_type)
        report = ingest_sheet(session, file_name, sheet, entity, override)
    except (FileError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from None
    report.errors += [{"severity": "warning", "field": "sheet",
                       "reason": f"sheet '{s.name}' was not imported; upload it separately"} for s in others]
    return report


@router.post("/demo/load")
def load_demo(session: Session = Depends(get_session)):
    reports = []
    for entity in TABLES:  # parents first, so demo links resolve
        path = DEMO_DIR / f"{entity}.csv"
        if path.exists():
            sheet = parse_file(path.name, path.read_bytes())[0]
            reports.append(ingest_sheet(session, path.name, sheet, entity))
    return {"loaded": sum(r.accepted for r in reports), "reports": reports}


@router.get("/ingest/batches")
def list_batches(session: Session = Depends(get_session)):
    rows = session.scalars(select(IngestionBatch).order_by(IngestionBatch.created_at.desc())).all()
    return {"items": [{c.name: getattr(b, c.name) for c in IngestionBatch.__table__.columns} for b in rows],
            "total": len(rows)}


@router.get("/ingest/batches/{batch_id}/rejected")
def rejected_rows(batch_id: str, session: Session = Depends(get_session)):
    if session.get(IngestionBatch, batch_id) is None:
        raise HTTPException(404, f"batch {batch_id} not found")
    rows = session.scalars(select(RejectedRow).where(RejectedRow.batch_id == batch_id).order_by(RejectedRow.row)).all()
    return {"items": [{"row": r.row, "raw": r.raw, "reasons": r.reasons} for r in rows], "total": len(rows)}


@router.get("/records/{entity}")
def list_records(entity: str, limit: int = 50, offset: int = 0, session: Session = Depends(get_session)):
    if entity not in ENTITY_MODELS:
        raise HTTPException(404, f"unknown entity '{entity}'; use one of {', '.join(ENTITY_MODELS)}")
    model = ENTITY_MODELS[entity]
    query = select(model).order_by(getattr(model, ID_FIELD[entity])).limit(limit).offset(offset)
    return {"items": [record_dict(r, entity) for r in session.scalars(query)],
            "total": session.scalar(select(func.count()).select_from(model)), "entity": entity}


@router.get("/customers/{customer_id}/360")
def customer_360(customer_id: str, session: Session = Depends(get_session)):
    def owned(entity: str) -> list[dict]:
        model = ENTITY_MODELS[entity]
        return [record_dict(r, entity) for r in session.scalars(select(model).where(model.customer_id == customer_id))]

    customer = session.get(ENTITY_MODELS["customers"], customer_id)
    accounts = owned("accounts")
    model = ENTITY_MODELS["transactions"]
    senders = [a["account_id"] for a in accounts]
    txns = session.scalars(select(model).where(model.sender_account.in_(senders))).all()
    return {"customer": record_dict(customer, "customers") if customer else {"customer_id": customer_id},
            "accounts": accounts, "transactions": [record_dict(t, "transactions") for t in txns],
            "logins": owned("logins"), "applications": owned("applications"), "claims": owned("claims"),
            "alerts": [a for a in latest_alerts(session) if involves_customer(a, customer_id)]}
