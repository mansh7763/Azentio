# PLACEHOLDER - owner A replaces
"""Case queue, case detail and decisions (append-only log)."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.api import sample_data
from app.schemas import Case, CaseDecision, CaseDetail, Page

router = APIRouter(tags=["cases"])


def _find(case_id: str) -> Case:
    for c in sample_data.CASES:
        if c.case_id == case_id:
            return c
    raise HTTPException(404, f"case {case_id} not found")


@router.get("/cases", response_model=Page[Case])
def list_cases(status: str | None = None, band: str | None = None, category: str | None = None):
    return Page[Case](items=sample_data.CASES, total=len(sample_data.CASES))


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: str):
    return sample_data.case_detail(_find(case_id))


@router.post("/cases/{case_id}/decision", response_model=CaseDetail)
def decide(case_id: str, decision: CaseDecision):
    case = _find(case_id).model_copy(update={"status": decision.status, "updated_at": datetime.now(timezone.utc)})
    return sample_data.case_detail(case)
