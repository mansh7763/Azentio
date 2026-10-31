# PLACEHOLDER - owner A replaces
"""Ingestion, demo data, records, customer 360 and admin reset."""

from fastapi import APIRouter, File, Form, UploadFile

from app.api import sample_data
from app.schemas import IngestReport

router = APIRouter(tags=["records"])


@router.post("/ingest", response_model=IngestReport)
async def ingest(file: UploadFile = File(...), entity_type: str | None = Form(None), mapping: str | None = Form(None)):
    return sample_data.ingest_report(file.filename or "upload")


@router.post("/demo/load")
def load_demo():
    return {"loaded": sample_data.DASHBOARD.records_processed}


@router.get("/records/{entity}")
def list_records(entity: str, limit: int = 50, offset: int = 0):
    return {"items": [], "total": 0, "entity": entity}


@router.get("/customers/{customer_id}/360")
def customer_360(customer_id: str):
    return {"customer": {"customer_id": customer_id}, "accounts": [], "transactions": [], "logins": [],
            "applications": [], "claims": [], "alerts": [a for a in sample_data.ALERTS if a.customer_id == customer_id]}


@router.post("/admin/reset")
def reset(reload_demo: bool = True):
    return {"reset": True, "reloaded_demo": reload_demo}
