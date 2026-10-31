"""Fraud prioritisation (Level 2, L2-6): risk, financial exposure, related events and confidence. Cases with
insufficient evidence are marked for further review instead of being given the top priority."""

import math

from app.schemas import Alert, Band

REVIEW_CAP = 60


def _exposure(a: Alert) -> float:
    total = 0.0
    for row in a.evidence.get("transactions", []):
        if row.get("txn_id") in a.event_ids and row.get("amount"):
            total += float(row["amount"])
    for row in a.evidence.get("applications", []):
        if row.get("application_id") in a.event_ids and row.get("amount"):
            total += float(row["amount"])
    return total


def prioritise(alerts: list[Alert]) -> list[dict]:
    out = []
    for a in alerts:
        facts = [c for c in a.contributions if c.kind == "risk" and c.points > 0]
        chain = any(c.kind == "floor" and (c.indicator_id or "").startswith("CHAIN:") for c in a.contributions)
        exposure = _exposure(a)
        related = len({e for c in a.contributions for e in c.evidence_ids})
        confidence = "high" if chain or len(facts) >= 3 else "medium" if len(facts) == 2 else "low"
        needs_review = a.band != Band.low and not chain and len(facts) < 2
        priority = 0.6 * a.score + 25 * min(1.0, math.log10(1 + exposure) / 6) + 1.5 * min(related, 10)
        factors = [f"risk {a.score} ({a.band.value})", f"exposure {exposure:,.0f}", f"{related} related records",
                   f"confidence {confidence}" + (" (attack chain)" if chain else "")]
        if needs_review:
            priority = min(priority, REVIEW_CAP)
            factors.append("only one independent fact: needs further review, not top priority")
        out.append({"alert_id": a.alert_id, "entity": a.primary_entity_id, "customer_id": a.customer_id,
                    "band": a.band.value, "score": a.score, "priority": round(priority), "exposure": exposure,
                    "related_events": related, "confidence": confidence, "needs_review": needs_review,
                    "factors": factors})
    return sorted(out, key=lambda p: (-p["priority"], p["alert_id"]))
