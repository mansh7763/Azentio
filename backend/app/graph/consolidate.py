"""Case consolidation helper (Level 2, L2-3): group alerts that belong to one suspected fraud activity, and say why.

Two alerts are grouped when they share a linked group (customers joined by a real device, phone, email or payout
account) or concern the same customer within 72 hours. Every alert stays in exactly one incident; nothing is
dropped. A (cases) stores the result and applies analyst splits on top."""

from datetime import timedelta

from app.schemas import Alert

SAME_CUSTOMER_WINDOW = timedelta(hours=72)


def consolidate(alerts: list[Alert], groups: list[dict]) -> list[dict]:
    parent = {a.alert_id: a.alert_id for a in alerts}
    reasons: dict[str, set[str]] = {a.alert_id: set() for a in alerts}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def join(a_id, b_id, why):
        ra, rb = find(a_id), find(b_id)
        if ra != rb:
            parent[rb] = ra
        reasons[a_id].add(why)
        reasons[b_id].add(why)

    for g in groups:
        ids = [i for i in g["alert_ids"] if i in parent]
        for other in ids[1:]:
            join(ids[0], other, f"linked group: {g['reason']}")

    by_customer: dict[str, list[Alert]] = {}
    for a in alerts:
        if a.customer_id:
            by_customer.setdefault(a.customer_id, []).append(a)
    for cid, items in by_customer.items():
        items.sort(key=lambda a: (a.event_time, a.alert_id))
        for prev, cur in zip(items, items[1:]):
            if cur.event_time - prev.event_time <= SAME_CUSTOMER_WINDOW:
                join(prev.alert_id, cur.alert_id, f"same customer {cid} within 72 hours")

    incidents: dict[str, list[Alert]] = {}
    for a in alerts:
        incidents.setdefault(find(a.alert_id), []).append(a)
    out = []
    for members in incidents.values():
        members.sort(key=lambda a: (a.event_time, a.alert_id))
        why = sorted({r for a in members for r in reasons[a.alert_id]})
        out.append({"incident_id": "INC-" + members[0].alert_id.removeprefix("ALT-"),
                    "alert_ids": [a.alert_id for a in members],
                    "entities": [a.primary_entity_id for a in members],
                    "customers": sorted({a.customer_id for a in members if a.customer_id}),
                    "reason": "; ".join(why) if why else "single alert"})
    return sorted(out, key=lambda i: i["incident_id"])
