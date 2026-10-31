# PLACEHOLDER - owner A replaces
"""Alert list and detail (alerts are immutable)."""

from fastapi import APIRouter, HTTPException

from app.api import sample_data
from app.schemas import Alert, Page

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=Page[Alert])
def list_alerts(customer_id: str | None = None, band: str | None = None, category: str | None = None,
                detection_type: str | None = None, product: str | None = None, txn_id: str | None = None,
                date_from: str | None = None, date_to: str | None = None, include_low: bool = False):
    items = [a for a in sample_data.ALERTS if include_low or a.band.value != "Low"]
    return Page[Alert](items=items, total=len(items))


@router.get("/alerts/{alert_id}", response_model=Alert)
def get_alert(alert_id: str):
    for a in sample_data.ALERTS:
        if a.alert_id == alert_id:
            return a
    raise HTTPException(404, f"alert {alert_id} not found")
