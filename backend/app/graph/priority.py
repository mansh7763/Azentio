"""Fraud prioritisation (Level 2, L2-6): risk, financial exposure, related events and evidence strength. Cases with
insufficient evidence are marked for further review instead of being given the top priority.

Evidence strength describes how many independent facts support a result; it is not a probability of fraud.
Exposure is kept per currency and never summed across currencies."""

import math
from collections import defaultdict

from app.schemas import Alert, Band

REVIEW_CAP = 60


def _exposure(a: Alert) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for table, key in (("transactions", "txn_id"), ("applications", "application_id")):
        for row in a.evidence.get(table, []):
            if row.get(key) in a.event_ids and row.get("amount"):
                out[str(row.get("currency") or "unspecified").upper()] += float(row["amount"])
    return dict(out)


def _facts(a: Alert) -> tuple[int, bool]:
    facts = sum(1 for c in a.contributions if c.kind == "risk" and c.points > 0)
    chain = any(c.kind == "floor" and (c.indicator_id or "").startswith("CHAIN:") for c in a.contributions)
    return facts, chain


def _strength(facts: int, chain: bool) -> str:
    return "strong" if chain or facts >= 3 else "moderate" if facts == 2 else "weak"


def _score(risk: int, exposure: dict[str, float], related: int) -> float:
    biggest = max(exposure.values(), default=0.0)  # largest single-currency exposure, never a cross-currency sum
    return 0.6 * risk + 25 * min(1.0, math.log10(1 + biggest) / 6) + 1.5 * min(related, 10)


def _factors(risk: int, band: Band, exposure: dict[str, float], related: int, strength: str, chain: bool,
             needs_review: bool) -> list[str]:
    money = ", ".join(f"{cur} {amt:,.0f}" for cur, amt in sorted(exposure.items())) or "none"
    out = [f"risk {risk} ({band.value})", f"exposure {money}", f"{related} related records",
           f"evidence {strength}" + (" (attack chain)" if chain else "")]
    if needs_review:
        out.append("only one independent fact: needs further review, not top priority")
    return out


def prioritise(alerts: list[Alert]) -> list[dict]:
    out = []
    for a in alerts:
        facts, chain = _facts(a)
        exposure = _exposure(a)
        related = len({e for c in a.contributions for e in c.evidence_ids})
        strength = _strength(facts, chain)
        needs_review = a.band != Band.low and not chain and facts < 2
        priority = _score(a.score, exposure, related)
        if needs_review:
            priority = min(priority, REVIEW_CAP)
        out.append({"alert_id": a.alert_id, "entity": a.primary_entity_id, "customer_id": a.customer_id,
                    "band": a.band.value, "score": a.score, "priority": round(priority),
                    "exposure_by_currency": exposure, "related_events": related, "evidence_strength": strength,
                    "needs_review": needs_review,
                    "factors": _factors(a.score, a.band, exposure, related, strength, chain, needs_review)})
    return sorted(out, key=lambda p: (-p["priority"], p["alert_id"]))


def case_priority(alerts: list[Alert]) -> dict:
    """One priority for a case that holds several alerts: highest risk, combined evidence and exposure."""
    if not alerts:
        return {"priority": 0, "score": 0, "band": None, "alert_count": 0, "related_events": 0,
                "exposure_by_currency": {}, "evidence_strength": "weak", "needs_review": True, "factors": []}
    top = max(alerts, key=lambda a: (a.score, a.alert_id))
    exposure: dict[str, float] = defaultdict(float)
    for a in alerts:
        for cur, amt in _exposure(a).items():
            exposure[cur] += amt
    related = len({e for a in alerts for c in a.contributions for e in c.evidence_ids})
    facts = len({c.indicator_id for a in alerts for c in a.contributions if c.kind == "risk" and c.points > 0})
    chain = any(_facts(a)[1] for a in alerts)
    strength = _strength(facts, chain)
    needs_review = top.band != Band.low and not chain and facts < 2
    priority = _score(top.score, dict(exposure), related)
    if needs_review:
        priority = min(priority, REVIEW_CAP)
    return {"priority": round(priority), "score": top.score, "band": top.band.value, "alert_count": len(alerts),
            "related_events": related, "exposure_by_currency": dict(exposure), "evidence_strength": strength,
            "needs_review": needs_review,
            "factors": _factors(top.score, top.band, dict(exposure), related, strength, chain, needs_review)}
