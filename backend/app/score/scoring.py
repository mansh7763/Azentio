"""Risk score: noisy-OR of risk signals, damped by mitigation, lifted by attack-chain floors."""

from dataclasses import dataclass, field

from app.detect.config import RulesConfig
from app.schemas import Band, Category, Signal

MAX_SIGNAL = 0.99  # keeps -ln(1 - w*s) finite
SUSPENDABLE = {"MT-PAYEE", "MT-RECUR", "MT-TENURE"}  # switched off while a login signal is active
SUPPORTING = {"MT-KNOWN", "MT-TENURE"}  # only damp when a strong lookalike factor is also present
# Rules that measure the same fact share a family; only the strongest in a family counts (revision 4).
FAMILY = {
    "TX-01": "amount", "TX-02": "amount", "HV-01": "amount",
    "TX-03": "new_payee", "TX-05": "new_payee",
    "LG-01": "failed_login", "LG-02": "failed_login", "LG-03": "failed_login",
    # Issue #6: rolling totals and structuring measure the same money as the amount rules; ID-02 is ID-01 after
    # normalisation. Only the strongest of each family counts, so they never stack on one fact.
    "TX-06": "amount", "TX-07": "amount", "ID-01": "identity", "ID-02": "identity",
    "AP-01": "coordination", "AP-04": "coordination",  # a shared payout inside a same-device ring is one fact
}


def family_of(indicator_id: str) -> str:
    return FAMILY.get(indicator_id, indicator_id)


def counted(risk: list[Signal]) -> list[Signal]:
    """The strongest signal of each family (ties broken by indicator id, so results are deterministic)."""
    best: dict[str, Signal] = {}
    for s in sorted(risk, key=lambda x: x.indicator_id):
        f = family_of(s.indicator_id)
        if f not in best or effect(s) > effect(best[f]):
            best[f] = s
    return [s for s in risk if best.get(family_of(s.indicator_id)) is s]


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


def should_suspend(signals: list[Signal]) -> bool:
    """Payee/recurrence/tenure mitigation is off only for corroborated access: a successful login after failures
    (LG-02) on a new device (DV-03). Failures alone, or a new device alone, do not count (revision 4)."""
    ids = {s.indicator_id for s in signals}
    return "LG-02" in ids and "DV-03" in ids


def applied_mitigations(mitigating: list[Signal], suspend_mitigation: bool) -> list[Signal]:
    """Mitigations that actually damp the score. A known device or long tenure does not explain a large amount
    or a burst of new payees, so those only count alongside a strong factor (regular payee, recurrence, household)."""
    usable = [m for m in mitigating if not (suspend_mitigation and m.indicator_id in SUSPENDABLE) and effect(m) > 0]
    if not any(m.indicator_id not in SUPPORTING for m in usable):
        return []
    return usable


def band_for(value: int, cfg: RulesConfig) -> Band:
    if value >= cfg.bands.high:
        return Band.high
    if value >= cfg.bands.medium:
        return Band.medium
    return Band.low


def score(risk: list[Signal], mitigating: list[Signal], chain: ChainMatch | None,
          suspend_mitigation: bool, cfg: RulesConfig, cap: int | None = None) -> ScoreBreakdown:
    keep = 1.0
    for s in counted(risk):
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
