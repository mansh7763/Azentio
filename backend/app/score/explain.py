"""Additive explanation: integer contribution lines that sum exactly to the score."""

import math

from app.schemas import Contribution, Signal
from app.score.scoring import ChainMatch, ScoreBreakdown, applied_mitigations, effect


def _log_share(signal: Signal) -> float:
    return -math.log(1 - effect(signal))


def contributions(risk: list[Signal], mitigating: list[Signal], chain: ChainMatch | None,
                  breakdown: ScoreBreakdown) -> list[Contribution]:
    lines: list[tuple[float, Contribution]] = []

    active = [s for s in risk if effect(s) > 0]
    total = sum(_log_share(s) for s in active)
    for s in active:
        raw = breakdown.undamped * _log_share(s) / total
        lines.append((raw, Contribution(indicator_id=s.indicator_id, kind="risk", points=0, reason=s.reason,
                                        evidence_ids=s.evidence_ids or s.event_ids)))

    mits = applied_mitigations(mitigating, breakdown.mitigation_suspended)
    gap = breakdown.damped - breakdown.undamped
    mtotal = sum(_log_share(m) for m in mits)
    if mits and gap < 0:
        for m in mits:
            raw = gap * _log_share(m) / mtotal
            lines.append((raw, Contribution(indicator_id=m.indicator_id, kind="mitigation", points=0, reason=m.reason,
                                            evidence_ids=m.evidence_ids or m.event_ids)))

    lift = breakdown.final - breakdown.damped
    if chain and lift > 0:
        lines.append((lift, Contribution(indicator_id=f"CHAIN:{chain.name}", kind="floor", points=0,
                                         reason=chain.reason, evidence_ids=chain.evidence_ids)))

    if not lines:
        return []
    ints = [round(raw) for raw, _ in lines]
    largest = max(range(len(lines)), key=lambda i: abs(lines[i][0]))
    ints[largest] += breakdown.score - sum(ints)
    return [c.model_copy(update={"points": p}) for (_, c), p in zip(lines, ints)]
