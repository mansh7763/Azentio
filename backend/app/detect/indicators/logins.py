"""Login indicators: failed-login bursts (LG-01..03) and new-device logins (DV-03)."""

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from app.detect.config import RulesConfig
from app.detect.dataset import Dataset
from app.schemas import Category, Signal

SENSITIVE = {"password_reset", "beneficiary_add", "profile_change", "device_change"}


@dataclass
class Burst:
    burst_id: str
    customer_id: str
    failure_ids: list[str]
    start: datetime
    end: datetime
    success_id: str | None = None
    success_time: datetime | None = None
    success_device: str | None = None
    new_device: bool | None = None
    after_actions: list[tuple[str, str, datetime]] = field(default_factory=list)


def _is(value, *options) -> bool:
    return isinstance(value, str) and value.lower() in options


def _event_type(row) -> str:
    value = row.get("event_type")
    return value.lower() if isinstance(value, str) and value else "login"


def new_device_flags(ds: Dataset, cfg: RulesConfig) -> dict[str, bool | None]:
    """For each successful login: True if its device was never seen in the customer's earlier successful logins.
    None when the device is unknown or the customer has fewer than `min_history` earlier logins."""
    logins = ds.get("logins")
    flags: dict[str, bool | None] = {}
    if logins.empty:
        return flags
    for _, g in logins.sort_values("seq").groupby("customer_id", sort=False):
        known: set[str] = set()
        count = 0
        for _, row in g.iterrows():
            if not _is(row["outcome"], "success", "successful", "ok"):
                continue
            device = row.get("device_id")
            has_device = isinstance(device, str) and device != ""
            flags[row["event_id"]] = (device not in known) if has_device and count >= cfg.min_history else None
            if has_device:
                known.add(device)
            count += 1
    return flags


def login_bursts(ds: Dataset, cfg: RulesConfig) -> list[Burst]:
    logins = ds.get("logins")
    if logins.empty:
        return []
    min_failures = cfg.params("LG-01").get("failures", 5)
    burst_window = pd.Timedelta(minutes=cfg.windows.burst_minutes)
    success_window = pd.Timedelta(minutes=cfg.windows.success_after_burst_minutes)
    chain_window = pd.Timedelta(hours=cfg.windows.chain_hours)
    new_flags = new_device_flags(ds, cfg)

    bursts: list[Burst] = []
    for cid, g in logins.sort_values("seq").groupby("customer_id", sort=False):
        g = g.reset_index(drop=True)
        fails = g[g["outcome"].map(lambda o: _is(o, "fail", "failed", "failure", "denied"))]
        groups: list[list[int]] = []
        for i in fails.index:
            if groups and g.loc[i, "timestamp"] - g.loc[groups[-1][0], "timestamp"] <= burst_window:
                groups[-1].append(i)
            else:
                groups.append([i])
        for idx in groups:
            if len(idx) < min_failures:
                continue
            start, end = g.loc[idx[0], "timestamp"], g.loc[idx[-1], "timestamp"]
            burst = Burst(burst_id=f"BURST-{cid}-{g.loc[idx[0], 'event_id']}", customer_id=cid,
                          failure_ids=list(g.loc[idx, "event_id"]), start=start.to_pydatetime(), end=end.to_pydatetime())
            later = g[(g.index > idx[-1])]
            ok = later[later["outcome"].map(lambda o: _is(o, "success", "successful", "ok"))
                       & later.apply(lambda r: _event_type(r) == "login", axis=1)
                       & (later["timestamp"] - end <= success_window)]
            if not ok.empty:
                s = ok.iloc[0]
                burst.success_id = s["event_id"]
                burst.success_time = s["timestamp"].to_pydatetime()
                burst.success_device = s.get("device_id") if isinstance(s.get("device_id"), str) else None
                burst.new_device = new_flags.get(s["event_id"])
            actions = g[(g["timestamp"] >= start) & (g["timestamp"] <= end + chain_window)]
            burst.after_actions = [(_event_type(r), r["event_id"], r["timestamp"].to_pydatetime())
                                   for _, r in actions.iterrows() if _event_type(r) in SENSITIVE]
            bursts.append(burst)
    return bursts


def _signal(cfg, indicator_id, burst_or_event, customer_id, event_ids, when, reason) -> Signal:
    return Signal(indicator_id=indicator_id, entity_id=burst_or_event, customer_id=customer_id, event_ids=event_ids,
                  event_time=when, weight=cfg.weight(indicator_id), category=Category.account_takeover,
                  reason=reason, evidence_ids=event_ids)


def login_signals(ds: Dataset, cfg: RulesConfig, bursts: list[Burst]) -> list[Signal]:
    out: list[Signal] = []
    for b in bursts:
        minutes = max(1, round((b.end - b.start).total_seconds() / 60))
        if cfg.enabled("LG-01"):
            out.append(_signal(cfg, "LG-01", b.burst_id, b.customer_id, b.failure_ids, b.end,
                               f"{len(b.failure_ids)} failed logins in {minutes} min"))
        if b.success_id and cfg.enabled("LG-02"):
            gap = round((b.success_time - b.end).total_seconds() / 60)
            out.append(_signal(cfg, "LG-02", b.burst_id, b.customer_id, b.failure_ids + [b.success_id], b.success_time,
                               f"Successful login {gap} min after {len(b.failure_ids)} failed attempts"))
        if cfg.enabled("LG-03"):
            for kind, event_id, when in b.after_actions:
                out.append(_signal(cfg, "LG-03", b.burst_id, b.customer_id, [event_id], when,
                                   f"Sensitive action after failed logins: {kind.replace('_', ' ')}"))

    if cfg.enabled("DV-03"):
        logins = ds.get("logins")
        flags = new_device_flags(ds, cfg)
        if not logins.empty:
            rows = logins.set_index("event_id")
            for event_id, is_new in flags.items():
                if is_new:
                    r = rows.loc[event_id]
                    out.append(Signal(indicator_id="DV-03", entity_id=event_id, customer_id=r["customer_id"],
                                      event_ids=[event_id], event_time=r["timestamp"].to_pydatetime(),
                                      weight=cfg.weight("DV-03"), category=Category.account_takeover,
                                      reason=f"Login from a device never used before: {r['device_id']}",
                                      evidence_ids=[event_id]))
    return out
