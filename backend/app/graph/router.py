"""Level 2 API (workstream B): relationship graph, linked groups, prioritisation and the Pattern Scout agent."""

from fastapi import APIRouter

from app.api.alert_store import latest_alerts
from app.db import SessionLocal
from app.detect.dataset import prepare
from app.detect.config import load_rules
from app.detect.engine import run_detection
from app.detect.router import load_dataset
from app.graph.builder import build_graph, entity_records, linked_groups, subgraph
from app.graph.priority import prioritise
from app.graph.scout import pattern_scout

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


@router.post("/agents/pattern-scout")
def scout():
    ds, alerts = _context()
    return pattern_scout(ds, alerts)
