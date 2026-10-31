"""Persist detection runs. Alerts are immutable snapshots; a case follows one incident across runs."""

import hashlib
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.detect.engine import DetectionResult
from app.graph.consolidate import consolidate
from app.graph.priority import case_priority
from app.models import AlertRow, CaseEventRow, CaseIncidentRow, CaseRow, DetectionRunRow
from app.schemas import Alert, Band, CaseStatus, DetectionRun

ACTIONABLE = {Band.medium, Band.high}


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def incident_key(alert: Alert) -> str:
    """Stable across runs even when an incident's evidence grows, so a re-run reuses its case."""
    return hashlib.sha256(f"{alert.unit_type.value}|{alert.primary_entity_id}".encode()).hexdigest()[:16]


def _next_sequence(session: Session) -> int:
    return (session.scalar(select(func.max(DetectionRunRow.sequence))) or 0) + 1


def _affected_customer(alert: Alert) -> str | None:
    if alert.customer_id:
        return alert.customer_id
    return next((e.entity_id for e in alert.entities if e.entity_type == "customer"), None)


def _account(alert: Alert) -> str | None:
    rows = alert.evidence.get("transactions") or []
    return rows[0].get("sender_account") if rows else None


def _open_case(session: Session, case_id: str, reason: str, note: str) -> CaseRow:
    stamp = now()
    case = CaseRow(case_id=case_id, alert_ids=[], category="", score=0, band="", status=CaseStatus.new.value,
                   created_at=stamp, updated_at=stamp, grouping_reason=reason, priority_factors=[])
    session.add(case)
    session.flush()
    session.add(CaseEventRow(case_id=case_id, at=stamp, actor="system", to_status=CaseStatus.new.value, note=note,
                             type="system", detail={}))
    return case


def case_incidents(session: Session, case_id: str) -> list[str]:
    return list(session.scalars(select(CaseIncidentRow.incident_key).where(CaseIncidentRow.case_id == case_id)))


def refresh_case(session: Session, case: CaseRow) -> None:
    """Case fields follow the latest snapshot of its incidents. An analyst's band and the status are never overwritten."""
    snapshots = incident_alerts(session, case_incidents(session, case.case_id))
    latest = list({incident_key(a): a for a in snapshots}.values())
    if not latest:
        return
    top = max(latest, key=lambda a: a.score)
    rank = case_priority(latest)
    case.alert_ids = list(dict.fromkeys(a.alert_id for a in snapshots))
    case.category, case.score, case.system_band = top.category.value, top.score, top.band.value
    case.band = case.analyst_band or top.band.value
    case.customer_id = _affected_customer(top)
    case.account_id = next((x for x in map(_account, sorted(latest, key=lambda a: -a.score)) if x), None)
    case.priority, case.exposure_by_currency = rank["priority"], rank["exposure_by_currency"]
    case.evidence_strength, case.needs_review = rank["evidence_strength"], rank["needs_review"]
    case.priority_factors = [*rank["factors"], f"{len(latest)} related alert(s) in this case"]
    case.updated_at = now()


def _sync_cases(session: Session, alerts: list[Alert], groups: list[dict]) -> None:
    placed = {r.incident_key: r for r in session.scalars(select(CaseIncidentRow))}
    touched = {placed[incident_key(a)].case_id for a in alerts if incident_key(a) in placed}
    actionable = [a for a in alerts if a.band in ACTIONABLE]
    by_id = {a.alert_id: a for a in actionable}
    for group in consolidate(actionable, groups):
        keys = sorted({incident_key(by_id[i]) for i in group["alert_ids"]})
        free = [k for k in keys if not (k in placed and placed[k].pinned)]
        if not free:
            continue
        current = sorted({placed[k].case_id for k in free if k in placed})
        case_id = current[0] if current else f"CASE-{free[0][:10]}"
        case = session.get(CaseRow, case_id)
        if case is None:
            case = _open_case(session, case_id, group["reason"], f"Opened from {len(free)} incident(s): {group['reason']}")
        elif len(free) > 1:
            case.grouping_reason = group["reason"]
        for key in free:
            if key not in placed:
                placed[key] = CaseIncidentRow(incident_key=key, case_id=case_id, pinned=False)
                session.add(placed[key])
        touched.add(case_id)
    session.flush()
    for case_id in touched:
        refresh_case(session, session.get(CaseRow, case_id))


def save_run(session: Session, result: DetectionResult, groups: list[dict] | None = None) -> DetectionResult:
    """Same data and rules: reuse the completed run and make it current again, with no new rows."""
    existing = session.get(DetectionRunRow, result.run.run_id)
    if existing is not None:
        existing.sequence = _next_sequence(session)
        session.commit()
        return DetectionResult(DetectionRun(**existing.payload), run_alerts(session, existing.run_id))

    session.add(DetectionRunRow(run_id=result.run.run_id, sequence=_next_sequence(session),
                                payload=result.run.model_dump(mode="json")))
    session.flush()
    for alert in result.alerts:
        session.add(AlertRow(detection_run_id=result.run.run_id, alert_id=alert.alert_id,
                             incident_key=incident_key(alert), payload=alert.model_dump(mode="json")))
    session.flush()
    _sync_cases(session, result.alerts, groups or [])
    session.commit()
    return result


def run_alerts(session: Session, run_id: str) -> list[Alert]:
    rows = session.scalars(select(AlertRow).where(AlertRow.detection_run_id == run_id))
    return [Alert(**r.payload) for r in rows]


def latest_run(session: Session) -> DetectionRun | None:
    row = session.scalar(select(DetectionRunRow).order_by(DetectionRunRow.sequence.desc()).limit(1))
    return DetectionRun(**row.payload) if row else None


def latest_alerts(session: Session) -> list[Alert]:
    run = latest_run(session)
    return run_alerts(session, run.run_id) if run else []


def incident_alerts(session: Session, keys: list[str]) -> list[Alert]:
    """Every snapshot of these incidents, oldest run first."""
    query = (select(AlertRow).join(DetectionRunRow, AlertRow.detection_run_id == DetectionRunRow.run_id)
             .where(AlertRow.incident_key.in_(keys)).order_by(DetectionRunRow.sequence, AlertRow.alert_id))
    return [Alert(**r.payload) for r in session.scalars(query)]


def _same(value: str | None, wanted: str) -> bool:
    """Filter text is typed by people: ignore case and stray spaces, but match the whole value."""
    return (value or "").strip().casefold() == wanted.strip().casefold()


def involves_customer(alert: Alert, customer_id: str) -> bool:
    return _same(alert.customer_id, customer_id) or any(
        e.entity_type == "customer" and _same(e.entity_id, customer_id) for e in alert.entities)


def filter_alerts(alerts: list[Alert], customer_id: str | None = None, band: str | None = None,
                  category: str | None = None, detection_type: str | None = None, product: str | None = None,
                  txn_id: str | None = None, date_from: date | None = None, date_to: date | None = None) -> list[Alert]:
    """The brief's six filters. Dates compare event_time, when the activity happened."""
    def keep(a: Alert) -> bool:
        day = a.event_time.date()
        return ((customer_id is None or involves_customer(a, customer_id))
                and (band is None or _same(a.band.value, band))
                and (category is None or _same(a.category.value, category))
                and (detection_type is None or any(_same(t, detection_type) for t in a.detection_types))
                and (product is None or _same(a.product, product))
                and (txn_id is None or any(_same(e, txn_id) for e in [a.primary_entity_id, *a.event_ids]))
                and (date_from is None or day >= date_from)
                and (date_to is None or day <= date_to))

    return [a for a in alerts if keep(a)]
