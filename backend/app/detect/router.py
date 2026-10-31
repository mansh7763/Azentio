"""Detection API (workstream B): run detection and read/edit rule settings."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.alert_store import save_run
from app.db import SessionLocal
from app.detect.config import load_rules
from app.detect.dataset import Dataset
from app.detect.engine import run_detection
from app.ingest.store import load_frames
from app.models import RuleOverrideRow
from app.schemas import DetectionResponse

router = APIRouter(tags=["detection"])



class RunRequest(BaseModel):
    rules: dict | None = None


class RuleUpdate(BaseModel):
    weight: float | None = None
    enabled: bool | None = None
    params: dict | None = None


def _overrides() -> dict:
    with SessionLocal() as session:
        row = session.get(RuleOverrideRow, 1)
        return dict(row.payload) if row else {}


def _save_overrides(overrides: dict) -> None:
    with SessionLocal() as session:
        session.merge(RuleOverrideRow(id=1, payload=overrides))
        session.commit()


def _merged(extra: dict | None) -> dict:
    out = _overrides()
    for section, items in (extra or {}).items():
        out[section] = {**out.get(section, {}), **items} if isinstance(items, dict) else items
    return out


def load_dataset() -> Dataset:
    with SessionLocal() as session:
        return Dataset.from_frames(**load_frames(session))


@router.post("/detect/run", response_model=DetectionResponse)
def run(body: RunRequest | None = None):
    trial = bool(body and body.rules)  # one-off rules are a what-if: shown, never saved
    result = run_detection(load_dataset(), overrides=_merged(body.rules if body else None))
    if not trial and result.run.records_processed:
        with SessionLocal() as session:
            result = save_run(session, result)
    return DetectionResponse(run=result.run, alerts=result.alerts)


@router.get("/rules")
def get_rules():
    cfg = load_rules(_overrides())
    return {**cfg.model_dump(), "version": cfg.version}


@router.put("/rules/{indicator_id}")
def update_rule(indicator_id: str, update: RuleUpdate):
    overrides = _overrides()
    cfg = load_rules(overrides)
    section = "indicators" if indicator_id in cfg.indicators else "mitigations" if indicator_id in cfg.mitigations else None
    if section is None:
        raise HTTPException(404, f"unknown indicator {indicator_id}")
    change = update.model_dump(exclude_none=True)
    current = overrides.setdefault(section, {}).setdefault(indicator_id, {})
    if "params" in change:
        current["params"] = {**current.get("params", {}), **change.pop("params")}
    current.update(change)
    load_rules(overrides)  # validate before accepting
    _save_overrides(overrides)
    return get_rules()


@router.post("/rules/reset")
def reset_rules():
    _save_overrides({})
    return get_rules()
