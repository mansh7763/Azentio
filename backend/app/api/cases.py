"""Case queue, workspace actions, split, audit history and report (the original alerts never change)."""

import json
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.alert_store import case_incidents, incident_alerts, incident_key, involves_customer, now, refresh_case
from app.db import get_session
from app.models import AlertRow, CaseEventRow, CaseIncidentRow, CaseRow
from app.schemas import Alert, Case, CaseAction, CaseDecision, CaseDetail, CaseEvent, CaseEventCreate, CaseSplit, CaseStatus, Page

router = APIRouter(tags=["cases"])

CASE_FIELDS = tuple(Case.model_fields)
# What each action does to the case status. None leaves it unchanged. Nothing here touches an account or a payment:
# hold and verification stay recorded recommendations until an authorised workflow approves them.
ACTIONS: dict[str, CaseStatus | None] = {
    "confirm": CaseStatus.requires_investigation,
    "false_positive": CaseStatus.false_positive,
    "request_info": CaseStatus.awaiting_information,
    "escalate": CaseStatus.escalated,
    "recommend_hold": None,
    "recommend_verification": None,
    "reclassify": None,
    "conclude": CaseStatus.closed,
}
RECOMMENDATIONS = {"recommend_hold", "recommend_verification"}


def _case(row: CaseRow) -> Case:
    return Case(**{f: getattr(row, f) for f in CASE_FIELDS})


def _find(session: Session, case_id: str) -> CaseRow:
    row = session.get(CaseRow, case_id)
    if row is None:
        raise HTTPException(404, f"case {case_id} not found")
    return row


def _events(session: Session, case_id: str) -> list[CaseEvent]:
    query = select(CaseEventRow).where(CaseEventRow.case_id == case_id).order_by(CaseEventRow.id)
    return [CaseEvent(id=e.id, type=e.type, detail=e.detail or {}, case_id=e.case_id, at=e.at, actor=e.actor,
                      from_status=e.from_status, to_status=e.to_status, note=e.note) for e in session.scalars(query)]


def _snapshots(session: Session, case_id: str) -> list[Alert]:
    return incident_alerts(session, case_incidents(session, case_id))


def _detail(session: Session, row: CaseRow) -> CaseDetail:
    return CaseDetail(**_case(row).model_dump(), alerts=_snapshots(session, row.case_id),
                      events=_events(session, row.case_id))


def _required(value: str | None, name: str) -> str:
    text = (value or "").strip()
    if not text:
        raise HTTPException(422, f"{name} is required")
    return text


def _log(session: Session, row: CaseRow, kind: str, actor: str, note: str, to_status: str, detail: dict | None = None) -> None:
    session.add(CaseEventRow(case_id=row.case_id, at=now(), actor=actor, from_status=row.status, to_status=to_status,
                             note=note, type=kind, detail=detail or {}))


@router.get("/cases", response_model=Page[Case])
def list_cases(status: str | None = None, band: str | None = None, category: str | None = None,
               customer_id: str | None = None, session: Session = Depends(get_session)):
    query = select(CaseRow).order_by(CaseRow.priority.desc(), CaseRow.score.desc(), CaseRow.case_id)
    for column, value in ((CaseRow.status, status), (CaseRow.band, band), (CaseRow.category, category),
                          (CaseRow.customer_id, customer_id)):
        if value is not None:
            query = query.where(column == value)
    items = [_case(r) for r in session.scalars(query)]
    return Page[Case](items=items, total=len(items))


@router.get("/cases/history")
def history(entity_id: str, session: Session = Depends(get_session)):
    """What earlier reviewers recorded on every case touching this entity."""
    wanted = entity_id.strip().casefold()

    def touches(alert: Alert) -> bool:
        ids = [alert.primary_entity_id, *alert.event_ids, *[e.entity_id for e in alert.entities]]
        return involves_customer(alert, entity_id) or any(i.casefold() == wanted for i in ids)

    items = []
    for row in session.scalars(select(CaseRow).order_by(CaseRow.updated_at.desc())):
        if any(touches(a) for a in _snapshots(session, row.case_id)):
            events = [e.model_dump(mode="json") for e in _events(session, row.case_id) if e.type != "system"]
            items.append({"case_id": row.case_id, "status": row.status, "band": row.band, "events": events})
    return {"items": items, "total": len(items)}


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, session: Session = Depends(get_session)):
    return _detail(session, _find(session, case_id))


@router.post("/cases/{case_id}/decision", response_model=CaseDetail)
def decide(case_id: str, decision: CaseDecision, session: Session = Depends(get_session)):
    row = _find(session, case_id)
    note = _required(decision.note, "note")
    actor = _required(decision.actor, "actor")
    _log(session, row, "decision", actor, note, decision.status.value)
    row.status, row.updated_at, row.notes = decision.status.value, now(), note
    session.commit()
    return _detail(session, row)


@router.post("/cases/{case_id}/actions", response_model=CaseDetail)
def act(case_id: str, body: CaseAction, session: Session = Depends(get_session)):
    row = _find(session, case_id)
    note = _required(body.note, "note")
    actor = _required(body.actor, "actor")
    status = ACTIONS[body.action]
    detail: dict = {"action": body.action}
    if body.action == "conclude" and body.outcome:
        status = CaseStatus(body.outcome)
    if body.action in RECOMMENDATIONS:
        detail.update(recommendation=True, executed=False)
    if body.action == "reclassify":
        if body.band is None:
            raise HTTPException(422, "band is required to reclassify")
        detail.update(from_band=row.band, to_band=body.band.value, system_band=row.system_band)
        row.analyst_band, row.band = body.band.value, body.band.value
    to_status = status.value if status else row.status
    _log(session, row, "correction" if body.action == "reclassify" else "action", actor, note, to_status, detail)
    row.status, row.updated_at, row.notes = to_status, now(), note
    session.commit()
    return _detail(session, row)


@router.post("/cases/{case_id}/split", response_model=CaseDetail)
def split(case_id: str, body: CaseSplit, session: Session = Depends(get_session)):
    """Move alerts to a new case. Pinned incidents stay there on every later detection run."""
    row = _find(session, case_id)
    reason = _required(body.reason, "reason")
    actor = _required(body.actor, "actor")
    held = {a.alert_id: incident_key(a) for a in _snapshots(session, case_id)}
    unknown = sorted(set(body.alert_ids) - set(held))
    if unknown or not body.alert_ids:
        raise HTTPException(422, f"alerts not in this case: {', '.join(unknown) or 'none given'}")
    moving = sorted({held[i] for i in body.alert_ids})
    if set(moving) == set(held.values()):
        raise HTTPException(422, "a split must leave at least one alert in the original case")

    new_id = "CASE-" + sha256(f"split|{case_id}|{','.join(moving)}".encode()).hexdigest()[:10]
    stamp = now()
    new = CaseRow(case_id=new_id, alert_ids=[], category=row.category, score=0, band=row.band, status=CaseStatus.new.value,
                  created_at=stamp, updated_at=stamp, grouping_reason=f"Split from {case_id}: {reason}", priority_factors=[])
    session.add(new)
    session.flush()
    for key in moving:
        placed = session.get(CaseIncidentRow, key)
        placed.case_id, placed.pinned = new_id, True
    moved = sorted(body.alert_ids)
    _log(session, row, "action", actor, reason, row.status, {"action": "split", "alert_ids": moved, "new_case_id": new_id})
    session.add(CaseEventRow(case_id=new_id, at=stamp, actor=actor, to_status=CaseStatus.new.value, note=reason, type="action",
                             detail={"action": "split", "alert_ids": moved, "from_case_id": case_id}))
    session.flush()
    refresh_case(session, row)
    refresh_case(session, new)
    session.commit()
    return _detail(session, new)


@router.post("/cases/{case_id}/events", response_model=CaseDetail)
def add_event(case_id: str, body: CaseEventCreate, session: Session = Depends(get_session)):
    """Notes, AI assessments and corrections to them. Past events are never edited."""
    row = _find(session, case_id)
    note = _required(body.note, "note")
    actor = _required(body.actor, "actor")
    detail = {**body.detail, "ai_generated": True} if body.type == "ai_assessment" else body.detail
    _log(session, row, body.type, actor, note, row.status, detail)
    session.commit()
    return _detail(session, row)


def _report(session: Session, row: CaseRow) -> dict:
    case = _detail(session, row).model_dump(mode="json")
    alerts = case.pop("alerts")
    events = case.pop("events")
    return {
        "report_generated_at": now().isoformat() + "Z", "case": case,
        "indicators": sorted({t for a in alerts for t in a["detection_types"]}),
        "original_alerts": alerts,
        "ai_assessments": [e for e in events if e["type"] == "ai_assessment"],
        "corrections": [e for e in events if e["type"] == "correction"],
        "decisions_and_actions": [e for e in events if e["type"] in ("decision", "action", "note", "system")],
        "note": "Recommendations are not executed. Scores rank prototype risk on synthetic data and are not fraud probabilities.",
    }


def _markdown(report: dict) -> str:
    case = report["case"]
    lines = [f"# Case report {case['case_id']}", "",
             f"- Status: {case['status']}", f"- Risk: {case['band']} (system {case['system_band']}), score {case['score']}",
             f"- Category: {case['category']}", f"- Customer: {case['customer_id'] or 'linked entities'}",
             f"- Priority: {case['priority']}", f"- Grouped because: {case['grouping_reason']}",
             f"- Indicators: {', '.join(report['indicators'])}", "", "## Original alerts", ""]
    for alert in report["original_alerts"]:
        lines.append(f"- {alert['alert_id']} ({alert['primary_entity_id']}): {alert['score']} {alert['band']}, "
                     f"run {alert['detection_run_id']}. {alert['narrative']}")
    for title, key in (("AI assessments", "ai_assessments"), ("Corrections", "corrections"),
                       ("Decisions and actions", "decisions_and_actions")):
        lines += ["", f"## {title}", ""]
        lines += [f"- {e['at']} {e['actor']} [{e['type']}] {e['from_status'] or 'Created'} -> {e['to_status']}: {e['note']}"
                  for e in report[key]] or ["- None recorded"]
    return "\n".join([*lines, "", report["note"], ""])


@router.get("/cases/{case_id}/report")
def report(case_id: str, format: str = "json", session: Session = Depends(get_session)):
    if format not in ("json", "markdown"):
        raise HTTPException(422, "format must be json or markdown")
    data = _report(session, _find(session, case_id))
    markdown = format == "markdown"
    body = _markdown(data) if markdown else json.dumps(data, indent=2)
    media = "text/markdown" if markdown else "application/json"
    suffix = "md" if markdown else "json"
    return PlainTextResponse(body, media_type=media,
                             headers={"Content-Disposition": f'attachment; filename="{case_id}-report.{suffix}"'})
