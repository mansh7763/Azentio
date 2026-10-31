"""Detection API (workstream B). Placeholder responses until run_detection lands in Task 7."""

from fastapi import APIRouter

from app.api import sample_data
from app.schemas import DetectionResponse

router = APIRouter(tags=["detection"])


@router.post("/detect/run", response_model=DetectionResponse)
def run():
    return DetectionResponse(run=sample_data.DETECTION_RUN, alerts=sample_data.ALERTS)


@router.get("/rules")
def get_rules():
    return {}
