from datetime import datetime, timezone

import pandas as pd
import pytest

from app.detect.dataset import Dataset, prepare
from app.detect.indicators.applications import application_signals
from app.detect.indicators.devices import device_signals
from app.detect.indicators.logins import login_bursts, login_signals
from app.detect.indicators.mitigation import mitigation_signals
from app.detect.indicators.transfers import transfer_signals
from app.detect.units import build_units
from app.features.profiles import transaction_profiles
from app.schemas import Direction, Signal, UnitType
from app.score.chains import match_chain
from app.score.scoring import score, should_suspend


@pytest.fixture(scope="module")
def world(golden, cfg):
    profiles = transaction_profiles(golden, cfg)
    bursts = login_bursts(golden, cfg)
    signals = (transfer_signals(golden, cfg, profiles) + login_signals(golden, cfg, bursts)
               + device_signals(golden, cfg) + application_signals(golden, cfg)
               + mitigation_signals(golden, cfg, profiles, bursts))
    return bursts, build_units(golden, signals, bursts, cfg), signals


def units_of(units, unit_type, entity):
    return [u for u in units if u.unit_type == unit_type and u.primary_entity_id == entity]


def unit_score(unit, bursts, cfg):
    sig = unit.signals + unit.context
    risk = [s for s in sig if s.direction == Direction.risk]
    mits = [s for s in sig if s.direction == Direction.mitigating]
    return score(risk, mits, match_chain(unit, bursts, cfg), should_suspend(sig), cfg, cap=unit.cap)


def test_household_device_low(world, cfg):
    bursts, units, _ = world
    unit = units_of(units, UnitType.device_cluster, "DEV-HOME")[0]
    assert "MT-HOUSE" in {s.indicator_id for s in unit.signals}
    assert unit_score(unit, bursts, cfg).score < 40


def test_ring_device_high_one_alert(world, cfg):
    bursts, units, _ = world
    ring = units_of(units, UnitType.device_cluster, "DEV-RING")
    assert len(ring) == 1
    assert unit_score(ring[0], bursts, cfg).score >= 70


@pytest.mark.parametrize("cid", ["C011", "C012"])  # 3rd and 4th by time; earlier ones are judged without later apps
def test_ring_applications_high(world, cfg, cid):
    bursts, units, _ = world
    unit = units_of(units, UnitType.application, f"APP-{cid}")[0]
    assert "AP-01" in {s.indicator_id for s in unit.signals}
    assert unit_score(unit, bursts, cfg).score >= 70


def test_no_names_relationship_unavailable(cfg):
    logins = pd.DataFrame([{"event_id": f"E{c}{i}", "customer_id": c, "timestamp": f"2026-09-0{i + 1}T1{n}:00:00Z",
                            "device_id": "DEVZ", "outcome": "success"}
                           for n, c in enumerate(["C1", "C2", "C3"]) for i in range(2)])
    customers = pd.DataFrame([{"customer_id": c} for c in ["C1", "C2", "C3"]])
    ds = prepare(Dataset.from_frames(customers=customers, logins=logins), cfg)
    sig = device_signals(ds, cfg)
    ids = {s.indicator_id for s in sig}
    assert "DV-01" in ids and "DV-02" not in ids and "MT-HOUSE" not in ids
    assert "unavailable" in [s for s in sig if s.indicator_id == "DV-01"][0].reason


def test_regular_payer_low(world, cfg):
    bursts, units, _ = world
    unit = units_of(units, UnitType.transaction, "T-C001-NEW")[0]
    assert "MT-PAYEE" in {s.indicator_id for s in unit.signals}
    assert unit_score(unit, bursts, cfg).score < 40


def test_mitigation_suspended_by_login_signal(world, cfg):
    bursts, units, _ = world
    unit = units_of(units, UnitType.transaction, "T-C002-ATO")[0]
    assert "MT-PAYEE" in {s.indicator_id for s in unit.signals}
    b = unit_score(unit, bursts, cfg)
    assert b.mitigation_suspended and b.score >= 85


def test_new_device_alone_does_not_suspend():
    t = datetime(2026, 10, 1, tzinfo=timezone.utc)
    dv = Signal(indicator_id="DV-03", entity_id="E", event_time=t, weight=0.25, reason="new device")
    lg = Signal(indicator_id="LG-02", entity_id="E", event_time=t, weight=0.35, reason="login")
    assert not should_suspend([dv])
    assert should_suspend([dv, lg])


def test_emi_payer_gets_recurring_mitigation(world):
    _, units, _ = world
    unit = units_of(units, UnitType.transaction, "T-C007-EMI")
    ids = {s.indicator_id for s in unit[0].signals} if unit else set()
    assert "MT-RECUR" in ids


def test_identity_conflict_on_ring_application(world):
    _, units, _ = world
    unit = units_of(units, UnitType.application, "APP-C011")[0]
    id01 = [s for s in unit.signals if s.indicator_id == "ID-01"]
    assert id01 and "9000000001" in id01[0].reason


def test_own_phone_on_application_is_not_a_conflict(world):
    _, _, signals = world
    assert not [s for s in signals if s.indicator_id == "ID-01" and s.entity_id == "APP-C016"]


def test_office_ip_alone_is_not_ap01(world):
    _, _, signals = world
    assert not [s for s in signals if s.indicator_id == "AP-01" and s.entity_id in ("APP-C016", "APP-C017", "APP-C018")]


def test_early_ring_application_not_judged_on_later_ones(world):
    _, _, signals = world
    assert not [s for s in signals if s.indicator_id == "AP-01" and s.entity_id in ("APP-C010", "APP-C013")]


def test_household_is_only_possible(world):
    _, units, _ = world
    unit = units_of(units, UnitType.device_cluster, "DEV-HOME")[0]
    assert "Possible household" in [s for s in unit.signals if s.indicator_id == "MT-HOUSE"][0].reason


def _device_logins(customers):
    return pd.DataFrame([{"event_id": f"E{c}{i}", "customer_id": c, "timestamp": f"2026-09-0{i + 1}T1{n}:00:00Z",
                          "device_id": "DEVX", "outcome": "success"}
                         for n, c in enumerate(customers) for i in range(3)])


def test_two_unrelated_customers_on_one_device_not_flagged(cfg):
    """DV-T3: below the 3-customer threshold -> no shared-device signal."""
    customers = pd.DataFrame([{"customer_id": "C1", "name": "A Rao", "address": "1 X St"},
                              {"customer_id": "C2", "name": "B Das", "address": "2 Y St"}])
    ds = prepare(Dataset.from_frames(customers=customers, logins=_device_logins(["C1", "C2"])), cfg)
    assert device_signals(ds, cfg) == []


def test_single_user_device_no_signal(cfg):
    """DV-T4"""
    ds = prepare(Dataset.from_frames(logins=_device_logins(["C1"])), cfg)
    assert device_signals(ds, cfg) == []
