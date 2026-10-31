import itertools
import math
from datetime import datetime, timezone

import pytest

from app.schemas import Band, Direction, Signal
from app.score.explain import contributions
from app.score.scoring import ChainMatch, band_for, score, should_suspend

T = datetime(2026, 10, 1, tzinfo=timezone.utc)


def risk(i, w, s=1.0):
    return Signal(indicator_id=i, entity_id="E", event_time=T, weight=w, strength=s, reason=i, evidence_ids=[f"ev-{i}"])


def mit(i, w, s=1.0):
    return Signal(indicator_id=i, entity_id="E", event_time=T, weight=w, strength=s, direction=Direction.mitigating,
                  reason=i, evidence_ids=[f"ev-{i}"])


CHAIN = ChainMatch(name="ato_full", floor=85, evidence_ids=["L1", "T1"], reason="ATO chain")


def total(risks, mits, chain=None, suspend=False, cfg=None):
    b = score(risks, mits, chain, suspend, cfg)
    return b, contributions(risks, mits, chain, b)


@pytest.mark.parametrize("weights", list(itertools.product([0.0, 0.2, 0.45, 0.6], repeat=3)))
def test_range_and_band(weights, cfg):
    b = score([risk(f"R{i}", w) for i, w in enumerate(weights)], [], None, False, cfg)
    assert 0 <= b.score <= 100
    assert b.band == band_for(b.score, cfg)


def test_band_thresholds(cfg):
    assert band_for(39, cfg) == Band.low
    assert band_for(40, cfg) == Band.medium
    assert band_for(69, cfg) == Band.medium
    assert band_for(70, cfg) == Band.high


@pytest.mark.parametrize("risks,mits,chain", [
    ([risk("A", 0.45), risk("B", 0.3)], [], None),
    ([risk("A", 0.2)], [mit("MT-PAYEE", 0.6)], None),                      # score ~8 after damping
    ([risk("A", 0.3), risk("B", 0.25)], [mit("MT-PAYEE", 0.6), mit("MT-KNOWN", 0.2)], None),
    ([risk("A", 0.3)], [mit("MT-PAYEE", 0.6)], CHAIN),                      # floor lifts a damped score to 85
    ([risk("A", 0.45), risk("B", 0.35), risk("C", 0.25)], [], CHAIN),
    ([], [], None),
])
def test_contributions_sum_exactly(risks, mits, chain, cfg):
    b, lines = total(risks, mits, chain, cfg=cfg)
    assert sum(c.points for c in lines) == b.score
    if mits and not chain:
        assert any(c.kind == "mitigation" and c.points < 0 for c in lines)
    if chain and b.final > b.damped:
        assert [c for c in lines if c.kind == "floor"][0].points > 0


def test_monotonic_add_risk_never_lowers(cfg):
    base = [risk("A", 0.3)]
    for w in (0.05, 0.3, 0.6):
        assert score(base + [risk("B", w)], [], None, False, cfg).final >= score(base, [], None, False, cfg).final


def test_monotonic_add_mitigation_never_raises(cfg):
    base = [risk("A", 0.45), risk("B", 0.3)]
    before = score(base, [], None, False, cfg).final
    for w in (0.1, 0.6):
        assert score(base, [mit("MT-KNOWN", w)], None, False, cfg).final <= before


def test_floor_beats_mitigation(cfg):
    b = score([risk("A", 0.3)], [mit("MT-PAYEE", 0.6), mit("MT-HOUSE", 0.6)], CHAIN, False, cfg)
    assert b.score == 85 and b.band == Band.high


def test_suspension_removes_payee_and_its_supporting_factors(cfg):
    r, m = [risk("A", 0.45)], [mit("MT-PAYEE", 0.6), mit("MT-KNOWN", 0.2), mit("MT-HOUSE", 0.6)]
    suspended = score(r, m, None, True, cfg)
    assert suspended.mitigation_suspended
    assert suspended.final == pytest.approx(45 * 0.4 * 0.8)  # household still applies, and supports known device
    alone = score(r, [mit("MT-PAYEE", 0.6), mit("MT-KNOWN", 0.2)], None, True, cfg)
    assert alone.final == pytest.approx(45)  # payee suspended -> known device has nothing to support


def test_weight_clamped_no_log_zero(cfg):
    b, lines = total([risk("A", 1.0), risk("B", 1.0)], [], None, cfg=cfg)
    assert b.score == 100 and all(math.isfinite(c.points) for c in lines)


def test_single_indicator_never_high(cfg):
    for ind_id, item in cfg.indicators.items():
        assert score([risk(ind_id, item.weight)], [], None, False, cfg).score < 70, ind_id


def test_lines_carry_evidence(cfg):
    _, lines = total([risk("A", 0.45)], [mit("MT-PAYEE", 0.6)], CHAIN, cfg=cfg)
    assert all(c.evidence_ids for c in lines)


def test_cap_keeps_score_below_high_and_lines_sum(cfg):
    risks = [risk("A", 0.45), risk("B", 0.45), risk("C", 0.35)]  # independent families, raw ~80
    b = score(risks, [], None, False, cfg, cap=69)
    lines = contributions(risks, [], None, b)
    assert b.score == 69 and b.band == Band.medium
    assert sum(c.points for c in lines) == 69
    assert [c for c in lines if c.indicator_id == "CAP"][0].points < 0


def test_weak_mitigations_alone_do_not_damp(cfg):
    r = [risk("TX-01", 0.45), risk("TX-03", 0.25)]
    alone = score(r, [mit("MT-KNOWN", 0.2), mit("MT-TENURE", 0.15)], None, False, cfg)
    assert alone.final == pytest.approx(alone.undamped)
    supported = score(r, [mit("MT-PAYEE", 0.6), mit("MT-KNOWN", 0.2)], None, False, cfg)
    assert supported.final == pytest.approx(supported.undamped * 0.4 * 0.8)


def test_correlated_rules_count_once(cfg):
    """Revision 4: rules in the same family (TX-01/TX-02 both measure amount) use the strongest, not the sum."""
    one = score([risk("TX-01", 0.45)], [], None, False, cfg)
    both = score([risk("TX-01", 0.45), risk("TX-02", 0.30)], [], None, False, cfg)
    assert both.final == pytest.approx(one.final)
    lines = contributions([risk("TX-01", 0.45), risk("TX-02", 0.30)], [], None, both)
    assert sum(c.points for c in lines) == both.score


def test_failures_alone_do_not_suspend_mitigation():
    t = datetime(2026, 10, 1, tzinfo=timezone.utc)
    lg1 = Signal(indicator_id="LG-01", entity_id="E", event_time=t, weight=0.3, reason="fails")
    lg2 = Signal(indicator_id="LG-02", entity_id="E", event_time=t, weight=0.35, reason="success")
    dv3 = Signal(indicator_id="DV-03", entity_id="E", event_time=t, weight=0.25, reason="new device")
    assert not should_suspend([lg1])
    assert not should_suspend([lg1, lg2])          # forgot password on the usual device
    assert should_suspend([lg1, lg2, dv3])         # corroborated: success on a new device
