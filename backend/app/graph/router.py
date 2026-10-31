"""Level 2 API (workstream B): relationship graph, linked groups, prioritisation and the Pattern Scout agent."""

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.alert_store import latest_alerts
from app.db import SessionLocal
from app.detect.dataset import prepare
from app.detect.config import load_rules
from app.detect.engine import run_detection
from app.detect.router import load_dataset
from app.graph.builder import build_graph, entity_records, linked_groups, subgraph
from app.graph.consolidate import consolidate
from app.graph.priority import case_priority, prioritise
from app.graph.scout import pattern_scout
from app.graph.store import decide, list_suggestions, save_suggestions

router = APIRouter(tags=["graph"])


def _context():
    raw = load_dataset()
    with SessionLocal() as session:
        alerts = latest_alerts(session)
    if not alerts and raw.frames:
        alerts = run_detection(raw).alerts  # not saved: only so the graph shows risk before the first run
    return prepare(raw, load_rules()), alerts


@router.get("/graph")
def graph(entity_id: str, depth: int = 2):
    ds, alerts = _context()
    return subgraph(build_graph(ds), entity_id, min(max(depth, 1), 3), alerts)


@router.get("/graph/groups")
def groups():
    ds, alerts = _context()
    return {"groups": linked_groups(build_graph(ds), alerts)}


@router.get("/graph/entity/{entity_id}")
def entity(entity_id: str):
    ds, _ = _context()
    return {"entity_id": entity_id, "records": entity_records(ds, entity_id)}


@router.get("/priority")
def priority():
    _, alerts = _context()
    return {"items": prioritise(alerts)}


@router.get("/incidents")
def incidents():
    """Consolidated investigations: alerts grouped by linked group or same customer within 72h, with the reason
    and a per-incident priority. A (cases) stores these and applies analyst splits on top."""
    ds, alerts = _context()
    by_id = {a.alert_id: a for a in alerts}
    out = []
    for inc in consolidate(alerts, linked_groups(build_graph(ds), alerts)):
        out.append({**inc, "priority": case_priority([by_id[i] for i in inc["alert_ids"]])})
    return {"items": sorted(out, key=lambda i: -i["priority"]["priority"])}


@router.post("/agents/pattern-scout")
def scout():
    ds, alerts = _context()
    result = pattern_scout(ds, alerts)
    with SessionLocal() as session:
        saved = {s["id"]: s for s in save_suggestions(session, result["suggestions"])}
    result["suggestions"] = [{**s, "status": saved[s["id"]]["status"], "decided_by": saved[s["id"]]["decided_by"]}
                             for s in result["suggestions"]]
    return result


@router.get("/agents/suggestions")
def suggestions():
    with SessionLocal() as session:
        return {"items": list_suggestions(session)}


class SuggestionDecision(BaseModel):
    decision: Literal["approve", "dismiss"]
    actor: str = Field(min_length=1)
    note: str | None = None


@router.post("/agents/suggestions/{suggestion_id}/decision")
def decide_suggestion(suggestion_id: str, body: SuggestionDecision):
    """Records the analyst's verdict only; approving never changes rules or scores."""
    with SessionLocal() as session:
        row = decide(session, suggestion_id, body.decision, body.actor, body.note)
    if row is None:
        raise HTTPException(404, f"unknown suggestion {suggestion_id}")
    return row
