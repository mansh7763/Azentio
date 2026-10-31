"""Scoring units: the four things that get a score (and at most one alert) each."""

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from app.detect.config import RulesConfig
from app.detect.dataset import Dataset
from app.detect.indicators.logins import Burst
from app.schemas import Signal, UnitType

LOGIN_CONTEXT = ("LG-", "DV-03")
DEVICE_SIGNALS = {"DV-01", "DV-02", "MT-HOUSE"}


@dataclass
class ScoringUnit:
    unit_type: UnitType
    primary_entity_id: str
    customer_id: str | None
    event_ids: list[str]
    event_time: datetime
    product: str | None = None
    signals: list[Signal] = field(default_factory=list)
    context: list[Signal] = field(default_factory=list)
    cap: int | None = None  # highest score allowed (login-only units cannot be High)


def _is_login_signal(s: Signal) -> bool:
    return s.indicator_id.startswith(LOGIN_CONTEXT)


def build_units(ds: Dataset, signals: list[Signal], bursts: list[Burst], cfg: RulesConfig) -> list[ScoringUnit]:
    window = pd.Timedelta(hours=cfg.windows.chain_hours)
    by_entity: dict[str, list[Signal]] = {}
    login_by_customer: dict[str, list[Signal]] = {}
    for s in signals:
        if _is_login_signal(s):
            login_by_customer.setdefault(s.customer_id, []).append(s)
        else:
            by_entity.setdefault(s.entity_id, []).append(s)

    units: list[ScoringUnit] = []
    txns = ds.get("transactions")
    accounts = ds.get("accounts")
    product_of = dict(zip(accounts["account_id"], accounts["product"])) if "product" in accounts else {}

    if not txns.empty:
        for _, t in txns.sort_values("seq").iterrows():
            when = t["timestamp"]
            own = by_entity.get(t["txn_id"], [])
            context = [s for s in login_by_customer.get(t["customer_id"], [])
                       if when - window <= pd.Timestamp(s.event_time) <= when]
            if own or context:
                units.append(ScoringUnit(UnitType.transaction, t["txn_id"], t["customer_id"], [t["txn_id"]],
                                         when.to_pydatetime(), product_of.get(t["sender_account"]), own, context))

    for b in bursts:
        anchor = pd.Timestamp(b.success_time or b.end)
        followed = False
        if not txns.empty:
            mine = txns[txns["customer_id"] == b.customer_id]
            followed = bool(((mine["timestamp"] >= anchor) & (mine["timestamp"] <= anchor + window)).any())
        if followed:
            continue  # the burst is context on that transfer instead
        own = [s for s in login_by_customer.get(b.customer_id, [])
               if s.entity_id == b.burst_id or (s.indicator_id == "DV-03" and s.entity_id == b.success_id)]
        moved_payee = b.new_device is True and any(kind == "beneficiary_add" for kind, _, _ in b.after_actions)
        units.append(ScoringUnit(UnitType.login_burst, b.burst_id, b.customer_id,
                                 b.failure_ids + ([b.success_id] if b.success_id else []),
                                 b.success_time or b.end, None, own, [],
                                 cap=None if moved_payee else cfg.bands.high - 1))

    device_groups: dict[str, list[Signal]] = {}
    for entity, group in by_entity.items():
        if any(s.indicator_id in DEVICE_SIGNALS for s in group):
            device_groups[entity] = [s for s in group if s.indicator_id in DEVICE_SIGNALS]
    for device, group in sorted(device_groups.items()):
        anchor = next((s for s in group if s.indicator_id == "DV-01"), None)
        if anchor is None:
            continue
        units.append(ScoringUnit(UnitType.device_cluster, device, None, list(anchor.event_ids),
                                 anchor.event_time, None, group, []))

    apps = ds.get("applications")
    if not apps.empty:
        for _, a in apps.sort_values("seq").iterrows():
            # Applications have their own detector (AP-*, ID-01), judged at the application's own time.
            # Whole-batch device signals are not borrowed: they would let later logins raise an earlier application.
            own = [s for s in by_entity.get(a["application_id"], []) if s.indicator_id.startswith(("AP-", "ID-"))]
            if own:
                units.append(ScoringUnit(UnitType.application, a["application_id"], a["customer_id"],
                                         [a["application_id"]], a["timestamp"].to_pydatetime(),
                                         a.get("product"), own, []))
    return units
