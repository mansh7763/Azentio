# PLACEHOLDER - owner C replaces
"""Dashboard summary (latest detection run only, dates by event_time)."""

from fastapi import APIRouter

from app.api import sample_data
from app.schemas import DashboardSummary

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary", response_model=DashboardSummary)
def summary(customer_id: str | None = None, band: str | None = None, category: str | None = None,
            detection_type: str | None = None, product: str | None = None, txn_id: str | None = None,
            date_from: str | None = None, date_to: str | None = None):
    return sample_data.DASHBOARD
