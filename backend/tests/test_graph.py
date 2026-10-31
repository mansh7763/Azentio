import pytest
from fastapi.testclient import TestClient

from app.detect.engine import run_detection
from app.graph.builder import build_graph, linked_groups, subgraph
from app.graph.priority import prioritise
from app.graph.scout import pattern_scout
from app.main import app


@pytest.fixture(scope="module")
def graph(golden):
    return build_graph(golden)


@pytest.fixture(scope="module")
def alerts(raw_golden):
    return run_detection(raw_golden).alerts


def test_ring_group_linked_by_real_identifiers(graph, alerts):
    groups = linked_groups(graph, alerts)
    ring = next(g for g in groups if {"C010", "C011", "C012", "C013"} <= set(g["members"]))
    vias = {link["via"] for link in ring["links"]}
    assert "device" in vias and any(link["value"] == "DEV-RING" for link in ring["links"])
    assert all(link["evidence_ids"] for link in ring["links"])  # every edge backed by record IDs
    assert ring["alert_ids"]


def test_office_ip_does_not_link_colleagues(graph, alerts):
    groups = linked_groups(graph, alerts)
    assert not any({"C016", "C017"} <= set(g["members"]) for g in groups)


def test_subgraph_around_customer(graph, alerts):
    sub = subgraph(graph, "C011", depth=2, alerts=alerts)
    ids = {n["id"] for n in sub["nodes"]}
    assert {"C011", "APP-C011", "DEV-RING"} <= ids
    assert all(e["evidence_ids"] for e in sub["edges"])
    assert next(n for n in sub["nodes"] if n["id"] == "C011")["risk"] == "High"


def test_priority_prefers_takeover_with_money_over_lone_failed_logins(alerts):
    ranked = {p["alert_id"]: p for p in prioritise(alerts)}
    ato = next(a for a in alerts if a.primary_entity_id == "T-C002-ATO")
    burst = next(a for a in alerts if a.customer_id == "C014" and a.unit_type.value == "login_burst")
    assert ranked[ato.alert_id]["priority"] > ranked[burst.alert_id]["priority"]
    assert ranked[ato.alert_id]["exposure"] == 210000


def test_thin_evidence_marked_for_review_not_top(alerts):
    ranked = prioritise(alerts)
    thin = [p for p in ranked if p["needs_review"]]
    assert thin and all(p["priority"] <= 60 for p in thin)
    assert all(p["factors"] for p in ranked)


def test_pattern_scout_suggests_with_real_evidence(golden, alerts):
    out = pattern_scout(golden, alerts, use_llm=False)
    assert out["suggestions"] and out["used_llm"] is False
    known = set(golden.get("customers")["customer_id"]) | set(golden.get("logins")["event_id"]) \
        | set(golden.get("applications")["application_id"]) | set(golden.get("transactions")["txn_id"])
    for s in out["suggestions"]:
        assert s["status"] == "suggested" and s["evidence_ids"]
        assert set(s["evidence_ids"]) <= known


def test_graph_endpoints():
    client = TestClient(app)
    client.post("/api/demo/load")
    client.post("/api/detect/run")
    g = client.get("/api/graph", params={"entity_id": "C011"}).json()
    assert g["nodes"] and g["edges"]
    assert client.get("/api/graph/groups").json()["groups"]
    assert client.get("/api/graph/entity/DEV-RING").json()["records"]
    assert "suggestions" in client.post("/api/agents/pattern-scout").json()
    assert client.get("/api/priority").json()["items"]
