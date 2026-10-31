"""C-owned projection of the latest stored detection run (workstream A's alert store).

Reading never runs detection: only POST /detect/run creates a run, so the dashboard, alerts and cases share one run_id.
"""
from collections import Counter, defaultdict
from datetime import date
from types import SimpleNamespace
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.alert_store import filter_alerts, latest_alerts, latest_run
from app.db import get_session
from app.models import ENTITY_MODELS

router = APIRouter(tags=["dashboard"])
NO_RUN = SimpleNamespace(run_id=None, rules_version=None, records_processed={}, indicators_skipped={}, coverage={})


@router.get("/dashboard/summary")
def summary(customer_id: str | None = None, band: str | None = None, category: str | None = None,
            detection_type: str | None = None, product: str | None = None, txn_id: str | None = None,
            date_from: date | None = None, date_to: date | None = None, session: Session = Depends(get_session)):
    run = latest_run(session)
    result = SimpleNamespace(run=run or NO_RUN, alerts=latest_alerts(session) if run else [])
    out = project(result, customer_id, band, category, detection_type, product, txn_id, date_from, date_to)
    stored = stored_counts(session)
    out["records_stored"] = stored
    out["run_stale"] = run is not None and nonzero(run.records_processed) != nonzero(stored)
    out["source_note"] = source_note(out["run_id"], out["records_processed"], stored, out["run_stale"])
    return out


def stored_counts(session: Session) -> dict[str, int]:
    return {entity: session.scalar(select(func.count()).select_from(model)) or 0 for entity, model in ENTITY_MODELS.items()}


def nonzero(counts: dict) -> dict:
    return {k: v for k, v in counts.items() if v}


def project(result, customer_id=None, band=None, category=None, detection_type=None,
            product=None, txn_id=None, date_from=None, date_to=None):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Start date must precede end date")
    # A's filter, so the dashboard and GET /alerts always select the same alerts.
    items = filter_alerts(result.alerts, customer_id or None, band or None, category or None, detection_type or None,
                          product or None, txn_id or None, date_from, date_to)
    bands = Counter(a.band.value for a in items)
    days = defaultdict(Counter)
    for a in items: days[a.event_time.date().isoformat()][a.band.value] += 1
    return {
        "run_id": result.run.run_id, "rules_version": result.run.rules_version,
        "records_processed": result.run.records_processed, "alerts_total": len(items),
        "flagged_total": sum(a.band.value != "Low" for a in items),
        "counts_by_band": {b: bands[b] for b in ("Low", "Medium", "High")},
        "counts_by_category": dict(Counter(a.category.value for a in items)),
        "counts_by_detection_type": dict(Counter(t for a in items for t in set(a.detection_types))),
        "over_time": [{"date": d, **{b: days[d][b] for b in ("Low", "Medium", "High")}} for d in sorted(days)],
        "indicators_skipped": result.run.indicators_skipped, "coverage": result.run.coverage,
        "alerts": [a.model_dump(mode="json") for a in items],
        "source_note": source_note(result.run.run_id, result.run.records_processed, result.run.records_processed, False),
    }


def _tables(counts: dict) -> str:
    return ", ".join(f"{n:,} {t}" for t, n in sorted(counts.items()) if n)


def source_note(run_id, processed: dict, stored: dict, stale: bool) -> str:
    if not run_id:
        if not any(stored.values()):
            return "No records are stored yet. Upload source files or load the demo dataset, then run detection."
        return f"{sum(stored.values()):,} records are stored ({_tables(stored)}) but not scored yet. Run detection to create the first run."
    note = f"Showing stored detection run {run_id} over {_tables(processed)}. Alerts and cases are read from the same stored run."
    if stale:
        note += f" Stored records have changed since this run (now {_tables(stored)}); run detection to include them."
    return note
