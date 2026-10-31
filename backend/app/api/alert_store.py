"""Persist detection runs. Alerts are immutable snapshots; a case follows one incident across runs."""

import hashlib
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.detect.engine import DetectionResult
from app.models import AlertRow, CaseEventRow, CaseRow, DetectionRunRow
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


def _sync_case(session: Session, alert: Alert, key: str) -> None:
    case = session.scalar(select(CaseRow).where(CaseRow.incident_key == key))
    stamp = now()
    if case is not None:
        if alert.alert_id not in case.alert_ids:
            case.alert_ids = [*case.alert_ids, alert.alert_id]
        case.score, case.band, case.updated_at = alert.score, alert.band.value, stamp
        return
    if alert.band not in ACTIONABLE:
        return
    case_id = f"CASE-{key[:10]}"
    session.add(CaseRow(
        case_id=case_id, incident_key=key, alert_ids=[alert.alert_id], category=alert.category.value,
        customer_id=_affected_customer(alert), account_id=_account(alert), score=alert.score, band=alert.band.value,
        status=CaseStatus.new.value, created_at=stamp, updated_at=stamp,
    ))
    session.flush()
    session.add(CaseEventRow(case_id=case_id, at=stamp, actor="system", to_status=CaseStatus.new.value,
                             note=f"Opened from alert {alert.alert_id}"))


def save_run(session: Session, result: DetectionResult) -> DetectionResult:
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
        key = incident_key(alert)
        session.add(AlertRow(detection_run_id=result.run.run_id, alert_id=alert.alert_id, incident_key=key,
                             payload=alert.model_dump(mode="json")))
        _sync_case(session, alert, key)
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


def incident_alerts(session: Session, key: str) -> list[Alert]:
    """Every snapshot of one incident, oldest run first."""
    query = (select(AlertRow).join(DetectionRunRow, AlertRow.detection_run_id == DetectionRunRow.run_id)
             .where(AlertRow.incident_key == key).order_by(DetectionRunRow.sequence))
    return [Alert(**r.payload) for r in session.scalars(query)]


def involves_customer(alert: Alert, customer_id: str) -> bool:
    return alert.customer_id == customer_id or any(
        e.entity_type == "customer" and e.entity_id == customer_id for e in alert.entities)


def filter_alerts(alerts: list[Alert], customer_id: str | None = None, band: str | None = None,
                  category: str | None = None, detection_type: str | None = None, product: str | None = None,
                  txn_id: str | None = None, date_from: date | None = None, date_to: date | None = None) -> list[Alert]:
    """The brief's six filters. Dates compare event_time, when the activity happened."""
    def keep(a: Alert) -> bool:
        day = a.event_time.date()
        return ((customer_id is None or involves_customer(a, customer_id))
                and (band is None or a.band.value == band)
                and (category is None or a.category.value == category)
                and (detection_type is None or detection_type in a.detection_types)
                and (product is None or a.product == product)
                and (txn_id is None or txn_id == a.primary_entity_id or txn_id in a.event_ids)
                and (date_from is None or day >= date_from)
                and (date_to is None or day <= date_to))

    return [a for a in alerts if keep(a)]
