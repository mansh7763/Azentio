"""Alert list and detail, from the latest completed detection run (alerts are immutable)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.alert_store import filter_alerts, latest_alerts
from app.db import get_session
from app.schemas import Alert, Band, Page

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=Page[Alert])
def list_alerts(customer_id: str | None = None, band: str | None = None, category: str | None = None,
                detection_type: str | None = None, product: str | None = None, txn_id: str | None = None,
                date_from: date | None = None, date_to: date | None = None, include_low: bool = False,
                session: Session = Depends(get_session)):
    items = filter_alerts(latest_alerts(session), customer_id, band, category, detection_type, product, txn_id,
                          date_from, date_to)
    if not include_low and band is None:
        items = [a for a in items if a.band != Band.low]
    items.sort(key=lambda a: (-a.score, a.event_time, a.alert_id))
    return Page[Alert](items=items, total=len(items))


@router.get("/alerts/{alert_id}", response_model=Alert)
def get_alert(alert_id: str, session: Session = Depends(get_session)):
    for alert in latest_alerts(session):
        if alert.alert_id == alert_id:
            return alert
    raise HTTPException(404, f"alert {alert_id} not found")
