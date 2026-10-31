"""Detection API (workstream B): run detection and read/edit rule settings."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.detect.config import load_rules
from app.detect.dataset import Dataset
from app.detect.engine import run_detection
from app.schemas import DetectionResponse

router = APIRouter(tags=["detection"])

GOLDEN = Path(__file__).resolve().parents[2] / "tests" / "golden"
_overrides: dict = {}  # TODO(A): persist in a rule_override table so edits survive restarts


class RunRequest(BaseModel):
    rules: dict | None = None


class RuleUpdate(BaseModel):
    weight: float | None = None
    enabled: bool | None = None
    params: dict | None = None


def _merged(extra: dict | None) -> dict:
    out = {**_overrides}
    for section, items in (extra or {}).items():
        out[section] = {**out.get(section, {}), **items} if isinstance(items, dict) else items
    return out


def load_dataset() -> Dataset:
    # TODO(A): replace with a Dataset built from the database (Dataset.from_frames(...)).
    return Dataset.from_csv_dir(GOLDEN)


@router.post("/detect/run", response_model=DetectionResponse)
def run(body: RunRequest | None = None):
    result = run_detection(load_dataset(), overrides=_merged(body.rules if body else None))
    return DetectionResponse(run=result.run, alerts=result.alerts)


@router.get("/rules")
def get_rules():
    cfg = load_rules(_overrides)
    return {**cfg.model_dump(), "version": cfg.version}


@router.put("/rules/{indicator_id}")
def update_rule(indicator_id: str, update: RuleUpdate):
    cfg = load_rules(_overrides)
    section = "indicators" if indicator_id in cfg.indicators else "mitigations" if indicator_id in cfg.mitigations else None
    if section is None:
        raise HTTPException(404, f"unknown indicator {indicator_id}")
    change = update.model_dump(exclude_none=True)
    current = _overrides.setdefault(section, {}).setdefault(indicator_id, {})
    if "params" in change:
        current["params"] = {**current.get("params", {}), **change.pop("params")}
    current.update(change)
    load_rules(_overrides)  # validate before accepting
    return get_rules()


@router.post("/rules/reset")
def reset_rules():
    _overrides.clear()
    return get_rules()
