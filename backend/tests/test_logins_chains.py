import pandas as pd
import pytest

from app.detect.dataset import Dataset, prepare
from app.detect.indicators.logins import login_bursts, login_signals
from app.detect.indicators.transfers import transfer_signals
from app.detect.units import build_units
from app.features.profiles import transaction_profiles
from app.schemas import Direction, UnitType
from app.score.chains import match_chain
from app.score.scoring import score


@pytest.fixture(scope="module")
def world(golden, cfg):
    profiles = transaction_profiles(golden, cfg)
    bursts = login_bursts(golden, cfg)
    signals = transfer_signals(golden, cfg, profiles) + login_signals(golden, cfg, bursts)
    units = build_units(golden, signals, bursts, cfg)
    return bursts, units


def unit_for(units, unit_type, entity=None, customer=None):
    found = [u for u in units if u.unit_type == unit_type
             and (entity is None or u.primary_entity_id == entity)
             and (customer is None or u.customer_id == customer)]
    return found


def scored(unit, bursts, cfg):
    signals = unit.signals + unit.context
    risk = [s for s in signals if s.direction == Direction.risk]
    mits = [s for s in signals if s.direction == Direction.mitigating]
    chain = match_chain(unit, bursts, cfg)
    suspend = any(s.indicator_id.startswith("LG-") for s in signals)
    return chain, score(risk, mits, chain, suspend, cfg, cap=unit.cap)


def test_one_burst_one_unit(world):
    _, units = world
    assert len(unit_for(units, UnitType.login_burst, customer="C014")) == 1


def test_burst_without_success_not_high(world, cfg):
    bursts, units = world
    _, b = scored(unit_for(units, UnitType.login_burst, customer="C014")[0], bursts, cfg)
    assert b.score < 70


def test_burst_followed_by_transfer_is_context_not_unit(world):
    _, units = world
    assert not unit_for(units, UnitType.login_burst, customer="C002")
    txn = unit_for(units, UnitType.transaction, entity="T-C002-ATO")[0]
    assert {"LG-01", "LG-02", "DV-03"} <= {s.indicator_id for s in txn.context}


def test_ato_full_chain_high(world, cfg):
    bursts, units = world
    chain, b = scored(unit_for(units, UnitType.transaction, entity="T-C002-ATO")[0], bursts, cfg)
    assert chain is not None and chain.name == "ato_full"
    assert b.score >= 85


def test_forgot_password_medium_max(world, cfg):
    bursts, units = world
    chain, b = scored(unit_for(units, UnitType.login_burst, customer="C003")[0], bursts, cfg)
    assert chain is not None and chain.name == "ato_partial"
    assert 40 <= b.score < 70


def test_transfer_before_login_no_chain(world, cfg):
    bursts, units = world
    unit = unit_for(units, UnitType.transaction, entity="T-C004-BIG")[0]
    assert match_chain(unit, bursts, cfg) is None
    assert not [s for s in unit.context if s.indicator_id.startswith("LG-")]


def test_regular_payer_usual_login_no_context(world):
    _, units = world
    txn = unit_for(units, UnitType.transaction, entity="T-C001-NEW")[0]
    assert not txn.context


def test_logins_without_device_skipped(cfg):
    rows = [{"event_id": f"E{i}", "customer_id": "C1", "timestamp": f"2026-09-{i + 1:02d}T10:00:00Z",
             "device_id": None, "outcome": "success"} for i in range(7)]
    rows += [{"event_id": f"F{i}", "customer_id": "C1", "timestamp": f"2026-09-20T10:0{i}:00Z",
              "device_id": None, "outcome": "fail"} for i in range(6)]
    rows.append({"event_id": "OK", "customer_id": "C1", "timestamp": "2026-09-20T10:08:00Z",
                 "device_id": None, "outcome": "success"})
    ds = prepare(Dataset.from_frames(logins=pd.DataFrame(rows)), cfg)
    bursts = login_bursts(ds, cfg)
    ids = {s.indicator_id for s in login_signals(ds, cfg, bursts)}
    assert "DV-03" not in ids and {"LG-01", "LG-02"} <= ids


def _logins(rows):
    return pd.DataFrame([{"event_id": e, "customer_id": "C1", "timestamp": t, "device_id": "D1", "outcome": o}
                         for e, t, o in rows])


def test_single_typo_is_not_a_burst(cfg):
    """LG-T3: one failure then a success on the usual device."""
    rows = [(f"H{i}", f"2026-09-0{i + 1}T10:00:00Z", "success") for i in range(6)]
    rows += [("F1", "2026-09-20T10:00:00Z", "fail"), ("OK", "2026-09-20T10:01:00Z", "success")]
    ds = prepare(Dataset.from_frames(logins=_logins(rows)), cfg)
    assert login_bursts(ds, cfg) == []


def test_failures_spread_over_days_are_not_a_burst(cfg):
    """LG-T5: six failures across three days."""
    rows = [(f"F{i}", f"2026-09-{10 + i // 2:02d}T{8 + 6 * (i % 2):02d}:00:00Z", "fail") for i in range(6)]
    ds = prepare(Dataset.from_frames(logins=_logins(rows)), cfg)
    assert login_bursts(ds, cfg) == []
