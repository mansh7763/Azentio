"""Risk score: noisy-OR of risk signals, damped by mitigation, lifted by attack-chain floors."""

from dataclasses import dataclass, field

from app.detect.config import RulesConfig
from app.schemas import Band, Category, Signal

MAX_SIGNAL = 0.99  # keeps -ln(1 - w*s) finite
SUSPENDABLE = {"MT-PAYEE", "MT-RECUR", "MT-TENURE"}  # switched off while a login signal is active


@dataclass
class ChainMatch:
    name: str
    floor: int
    evidence_ids: list[str] = field(default_factory=list)
    reason: str = ""
    category: Category = Category.account_takeover


@dataclass
class ScoreBreakdown:
    undamped: float
    damped: float
    final: float
    score: int
    band: Band
    mitigation_suspended: bool = False


def effect(signal: Signal) -> float:
    return min(signal.weight * signal.strength, MAX_SIGNAL)


def applied_mitigations(mitigating: list[Signal], suspend_mitigation: bool) -> list[Signal]:
    return [m for m in mitigating if not (suspend_mitigation and m.indicator_id in SUSPENDABLE) and effect(m) > 0]


def band_for(value: int, cfg: RulesConfig) -> Band:
    if value >= cfg.bands.high:
        return Band.high
    if value >= cfg.bands.medium:
        return Band.medium
    return Band.low


def score(risk: list[Signal], mitigating: list[Signal], chain: ChainMatch | None,
          suspend_mitigation: bool, cfg: RulesConfig, cap: int | None = None) -> ScoreBreakdown:
    keep = 1.0
    for s in risk:
        keep *= 1 - effect(s)
    undamped = 100 * (1 - keep)

    damped = undamped
    for m in applied_mitigations(mitigating, suspend_mitigation):
        damped *= 1 - effect(m)

    final = max(damped, float(chain.floor)) if chain else damped
    if cap is not None:
        final = min(final, float(cap))
    value = int(round(final))
    suspended = suspend_mitigation and any(m.indicator_id in SUSPENDABLE for m in mitigating)
    return ScoreBreakdown(undamped, damped, final, value, band_for(value, cfg), suspended)
