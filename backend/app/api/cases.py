"""Case queue, case detail and decisions (append-only log; the original alert never changes)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.alert_store import incident_alerts, now
from app.db import get_session
from app.models import CaseEventRow, CaseRow
from app.schemas import Case, CaseDecision, CaseDetail, CaseEvent, CaseStatus, Page

router = APIRouter(tags=["cases"])

CASE_FIELDS = tuple(Case.model_fields)


def _case(row: CaseRow) -> Case:
    return Case(**{f: getattr(row, f) for f in CASE_FIELDS})


def _find(session: Session, case_id: str) -> CaseRow:
    row = session.get(CaseRow, case_id)
    if row is None:
        raise HTTPException(404, f"case {case_id} not found")
    return row


def _detail(session: Session, row: CaseRow) -> CaseDetail:
    query = select(CaseEventRow).where(CaseEventRow.case_id == row.case_id).order_by(CaseEventRow.id)
    events = [CaseEvent(case_id=e.case_id, at=e.at, actor=e.actor, from_status=e.from_status, to_status=e.to_status,
                        note=e.note) for e in session.scalars(query)]
    return CaseDetail(**_case(row).model_dump(), alerts=incident_alerts(session, row.incident_key), events=events)


@router.get("/cases", response_model=Page[Case])
def list_cases(status: str | None = None, band: str | None = None, category: str | None = None,
               customer_id: str | None = None, session: Session = Depends(get_session)):
    query = select(CaseRow).order_by(CaseRow.score.desc(), CaseRow.case_id)
    for column, value in ((CaseRow.status, status), (CaseRow.band, band), (CaseRow.category, category),
                          (CaseRow.customer_id, customer_id)):
        if value is not None:
            query = query.where(column == value)
    items = [_case(r) for r in session.scalars(query)]
    return Page[Case](items=items, total=len(items))


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, session: Session = Depends(get_session)):
    return _detail(session, _find(session, case_id))


@router.post("/cases/{case_id}/decision", response_model=CaseDetail)
def decide(case_id: str, decision: CaseDecision, session: Session = Depends(get_session)):
    row = _find(session, case_id)
    previous = CaseStatus(row.status)
    note = (decision.note or "").strip() or None
    actor = decision.actor.strip()
    if note is None or not actor:
        raise HTTPException(422, "a decision needs a non-empty actor and note")
    stamp = now()
    session.add(CaseEventRow(case_id=case_id, at=stamp, actor=actor, from_status=previous.value,
                             to_status=decision.status.value, note=note))
    row.status, row.updated_at = decision.status.value, stamp
    row.notes = note
    session.commit()
    return _detail(session, row)
