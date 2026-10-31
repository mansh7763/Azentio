"""Relationship graph (Level 2, L2-1/L2-2): every edge comes from matching identifiers in the stored records and
carries those record IDs. Nothing here is inferred by an AI model."""

import re
from collections import defaultdict

import networkx as nx
import pandas as pd

from app.detect.dataset import Dataset
from app.schemas import Alert, Band

MAX_EVIDENCE = 20
HUB_CAP = 25           # an identifier shared by more customers than this (office IP, big merchant) is a hub
GROUP_VIAS = {"device", "phone", "email", "payout"}  # IPs and beneficiaries are shown, but never group customers
ORDER = {Band.low: 0, Band.medium: 1, Band.high: 2}


def _s(v) -> str | None:
    return v.strip() if isinstance(v, str) and v.strip() else None


def _phone(v) -> str | None:
    digits = re.sub(r"\D", "", v) if isinstance(v, str) else ""
    return digits[-10:] or None


def _link(g: nx.Graph, a: str, a_type: str, b: str, b_type: str, via: str, evidence: str) -> None:
    g.add_node(a, type=a_type)
    g.add_node(b, type=b_type)
    if g.has_edge(a, b):
        ev = g.edges[a, b]["evidence_ids"]
        if evidence not in ev and len(ev) < MAX_EVIDENCE:
            ev.append(evidence)
    else:
        g.add_edge(a, b, via=via, evidence_ids=[evidence])


def build_graph(ds: Dataset) -> nx.Graph:
    g = nx.Graph()
    for _, c in ds.get("customers").iterrows():
        cid = c["customer_id"]
        g.add_node(cid, type="customer")
        if p := _phone(c.get("phone")):
            _link(g, cid, "customer", p, "phone", "phone", cid)
        if e := _s(c.get("email")):
            _link(g, cid, "customer", e.lower(), "email", "email", cid)
    for _, a in ds.get("accounts").iterrows():
        _link(g, a["customer_id"], "customer", a["account_id"], "account", "owns", a["account_id"])
    for _, lg in ds.get("logins").iterrows():
        if d := _s(lg.get("device_id")):
            _link(g, lg["customer_id"], "customer", d, "device", "device", lg["event_id"])
        if ip := _s(lg.get("ip")):
            _link(g, lg["customer_id"], "customer", ip, "ip", "ip", lg["event_id"])
    for _, ap in ds.get("applications").iterrows():
        aid, cid = ap["application_id"], ap["customer_id"]
        _link(g, cid, "customer", aid, "application", "applied", aid)
        if d := _s(ap.get("device_id")):
            _link(g, aid, "application", d, "device", "device", aid)
        if p := _phone(ap.get("phone")):
            _link(g, aid, "application", p, "phone", "phone", aid)
        if e := _s(ap.get("email")):
            _link(g, aid, "application", e.lower(), "email", "email", aid)
        if acc := _s(ap.get("disbursement_account")):
            _link(g, aid, "application", acc, "account", "payout", aid)
    for _, t in ds.get("transactions").iterrows():
        _link(g, t["sender_account"], "account", t["beneficiary_account"], "account", "paid", t["txn_id"])
    for _, cl in ds.get("claims").iterrows():
        _link(g, cl["customer_id"], "customer", cl["claim_id"], "claim", "claimed", cl["claim_id"])
        _link(g, cl["claim_id"], "claim", cl["policy_id"], "policy", "policy", cl["claim_id"])
        if acc := _s(cl.get("payout_account")):
            _link(g, cl["claim_id"], "claim", acc, "account", "payout", cl["claim_id"])
    return g


def _customers_of(g: nx.Graph, node: str) -> dict[str, list[str]]:
    """Customers attached to an identifier directly or through one of their applications, with the record IDs."""
    out: dict[str, list[str]] = defaultdict(list)
    for nb in g.neighbors(node):
        kind = g.nodes[nb].get("type")
        if kind == "customer":
            out[nb] += g.edges[node, nb]["evidence_ids"]
        elif kind in ("application", "claim"):
            for cust in g.neighbors(nb):
                if g.nodes[cust].get("type") == "customer":
                    out[cust] += g.edges[node, nb]["evidence_ids"]
        elif kind == "account" and g.edges[node, nb]["via"] == "owns":
            pass
    if g.nodes[node].get("type") == "account":  # a payout account: owner + applicants who named it
        for nb in g.neighbors(node):
            if g.nodes[nb].get("type") == "customer" and g.edges[node, nb]["via"] == "owns":
                out[nb] += g.edges[node, nb]["evidence_ids"]
    return out


def _risk_by_entity(alerts: list[Alert]) -> dict[str, Band]:
    risk: dict[str, Band] = {}
    for a in alerts:
        for eid in {a.primary_entity_id, a.customer_id, *(e.entity_id for e in a.entities)} - {None}:
            if eid not in risk or ORDER[a.band] > ORDER[risk[eid]]:
                risk[eid] = a.band
    return risk


def linked_groups(g: nx.Graph, alerts: list[Alert]) -> list[dict]:
    """Customers connected through shared devices, phones, emails or payout accounts (hubs excluded)."""
    links: list[dict] = []
    parent: dict[str, str] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for node, data in g.nodes(data=True):
        kind = data.get("type")
        if kind not in ("device", "phone", "email", "account"):
            continue
        via = "payout" if kind == "account" else kind
        if kind == "account" and not any(g.edges[node, nb]["via"] == "payout" for nb in g.neighbors(node)):
            continue
        members = _customers_of(g, node)
        if not 2 <= len(members) <= HUB_CAP or via not in GROUP_VIAS:
            continue
        ids = sorted(members)
        for other in ids[1:]:
            parent[find(other)] = find(ids[0])
        links.append({"via": via, "value": node, "members": ids,
                      "evidence_ids": sorted({e for ev in members.values() for e in ev})[:MAX_EVIDENCE]})

    comps: dict[str, set] = defaultdict(set)
    for link in links:
        comps[find(link["members"][0])].update(link["members"])
    groups = []
    for root, members in sorted(comps.items(), key=lambda kv: sorted(kv[1])):
        mine = [lk for lk in links if find(lk["members"][0]) == root]
        alert_ids = sorted({a.alert_id for a in alerts if a.customer_id in members
                            or any(e.entity_id in members for e in a.entities)
                            or a.primary_entity_id in {lk["value"] for lk in mine}})
        risk = _risk_by_entity([a for a in alerts if a.alert_id in alert_ids])
        top = max((risk[m] for m in members if m in risk), key=lambda b: ORDER[b], default=None)
        groups.append({"group_id": "GRP-" + "-".join(sorted(members))[:40], "members": sorted(members),
                       "links": mine, "alert_ids": alert_ids, "highest_band": top.value if top else None,
                       "reason": "; ".join(f"{lk['via']} {lk['value']} shared by {', '.join(lk['members'])}" for lk in mine)})
    return groups


def subgraph(g: nx.Graph, entity_id: str, depth: int, alerts: list[Alert], max_nodes: int = 150) -> dict:
    if entity_id not in g:
        return {"nodes": [], "edges": []}
    hubs = {n for n, d in g.degree() if d > HUB_CAP and n != entity_id}
    view = g.subgraph(set(g.nodes) - hubs)
    nodes = list(nx.single_source_shortest_path_length(view, entity_id, cutoff=depth))[:max_nodes]
    sub = view.subgraph(nodes)
    risk = _risk_by_entity(alerts)
    return {
        "nodes": [{"id": n, "type": d.get("type"), "label": n, "risk": risk[n].value if n in risk else None}
                  for n, d in sub.nodes(data=True)],
        "edges": [{"source": a, "target": b, "type": d["via"], "via": d["via"], "evidence_ids": d["evidence_ids"]}
                  for a, b, d in sub.edges(data=True)],
        "hubs_hidden": sorted(hubs & set(g.neighbors(entity_id))) if entity_id in g else [],
    }


ID_COLUMNS = ("customer_id", "account_id", "event_id", "txn_id", "application_id", "claim_id", "policy_id",
              "device_id", "ip", "sender_account", "beneficiary_account", "disbursement_account", "email")


def entity_records(ds: Dataset, entity_id: str, limit: int = 50) -> dict[str, list[dict]]:
    out = {}
    for name, df in ds.frames.items():
        if df is None or df.empty:
            continue
        mask = pd.Series(False, index=df.index)
        for col in ID_COLUMNS:
            if col in df:
                mask |= df[col].astype(str) == entity_id
        if "phone" in df:
            mask |= df["phone"].map(_phone) == _phone(entity_id)
        rows = df[mask].head(limit)
        if not rows.empty:
            out[name] = [{k: (v.isoformat() if hasattr(v, "isoformat") else (None if pd.isna(v) else v))
                          for k, v in r.items() if k != "seq"} for r in rows.to_dict("records")]
    return out
