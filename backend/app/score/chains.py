"""Ordered attack chains. A chain sets a minimum score (floor); events out of order never match."""

from datetime import timedelta

from app.detect.config import RulesConfig
from app.detect.indicators.logins import Burst
from app.detect.units import ScoringUnit
from app.schemas import Category, UnitType
from app.score.scoring import ChainMatch


def _minutes(a, b) -> int:
    return max(0, round((b - a).total_seconds() / 60))


def match_chain(unit: ScoringUnit, bursts: list[Burst], cfg: RulesConfig) -> ChainMatch | None:
    window = timedelta(hours=cfg.windows.chain_hours)
    floors = cfg.floors

    if unit.unit_type == UnitType.transaction:
        cashout = [s for s in unit.signals if s.indicator_id == "AP-03" and s.strength >= 1.0]
        if cashout:  # flagged application -> disbursement -> rapid outflow, in that order (by construction)
            return ChainMatch("loan_mule", floors.loan_mule, cashout[0].evidence_ids,
                              "Loan-to-mule pattern: flagged loan application -> disbursement -> most of it sent to "
                              "new recipients", Category.loan_application_fraud)
        candidates = [b for b in bursts if b.customer_id == unit.customer_id and b.success_time
                      and b.success_time <= unit.event_time <= b.success_time + window]
        if not candidates:
            return None
        b = max(candidates, key=lambda x: x.success_time)
        ids = {s.indicator_id for s in unit.signals + unit.context}
        evidence = b.failure_ids + [b.success_id] + unit.event_ids
        gap = _minutes(b.success_time, unit.event_time)
        if b.new_device and "HV-01" in ids:
            return ChainMatch("ato_full", floors.ato_full, evidence,
                              f"Account-takeover pattern: {len(b.failure_ids)} failed logins → login from new device "
                              f"{b.success_device} → high-value transfer {gap} min later")
        payee_added = [eid for kind, eid, when in b.after_actions
                       if kind == "beneficiary_add" and b.success_time <= when <= unit.event_time]
        # Revision 4: High needs corroborating access context (success on a new device) plus a payee change.
        # An ordinary payment after failed logins from the usual device is not a takeover chain.
        if b.new_device and (payee_added or "TX-03" in ids):
            return ChainMatch("ato_movement", floors.ato_movement, evidence + payee_added,
                              f"Account-takeover pattern: {len(b.failure_ids)} failed logins → login from new device "
                              f"{b.success_device} → payment to a new beneficiary {gap} min later")
        return None

    if unit.unit_type == UnitType.login_burst:
        b = next((x for x in bursts if x.burst_id == unit.primary_entity_id), None)
        if b is None or not b.success_id:
            return None
        kinds = {kind for kind, _, _ in b.after_actions}
        evidence = b.failure_ids + [b.success_id] + [eid for _, eid, _ in b.after_actions]
        if "beneficiary_add" in kinds and b.new_device:
            return ChainMatch("ato_movement", floors.ato_movement, evidence,
                              "Account-takeover pattern: failed logins → successful login → beneficiary added")
        if b.new_device or "password_reset" in kinds:
            what = "new device" if b.new_device else "password reset"
            return ChainMatch("ato_partial", floors.ato_partial, evidence,
                              f"Possible account takeover: failed logins → {what}, no money moved (capped below High)")
    return None
