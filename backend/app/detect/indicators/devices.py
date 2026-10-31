"""Shared-device indicators: DV-01 (many customers on one device), DV-02 (relationship), MT-HOUSE (household)."""

import pandas as pd

from app.detect.config import RulesConfig
from app.detect.dataset import Dataset
from app.schemas import Category, Direction, Signal


def _surname(name) -> str | None:
    return name.strip().split()[-1].lower() if isinstance(name, str) and name.strip() else None


def _clean(value) -> str | None:
    return value.strip().lower() if isinstance(value, str) and value.strip() else None


def device_signals(ds: Dataset, cfg: RulesConfig) -> list[Signal]:
    logins = ds.get("logins")
    if logins.empty or "device_id" not in logins:
        return []
    logins = logins[logins["device_id"].map(lambda d: isinstance(d, str) and d != "")]
    customers = ds.get("customers")
    info = customers.set_index("customer_id") if not customers.empty else pd.DataFrame()
    apps, txns = ds.get("applications"), ds.get("transactions")
    min_customers = cfg.params("DV-01").get("min_customers", 3)

    out: list[Signal] = []
    for device, g in logins.groupby("device_id", sort=True):
        members = sorted(g["customer_id"].dropna().unique())
        if len(members) < min_customers:
            continue
        event_ids = list(g.sort_values("seq")["event_id"])
        when = g["timestamp"].max().to_pydatetime()

        def lookup(cid, col):
            return info.loc[cid, col] if col in info and cid in info.index else None

        surnames = [_surname(lookup(c, "name")) for c in members]
        addresses = [_clean(lookup(c, "address")) for c in members]
        cities = sorted({_clean(lookup(c, "city")) for c in members} - {None})
        assessable = all(surnames) and all(addresses)

        reason = f"Device {device} used by {len(members)} customers ({', '.join(members)})"
        if not assessable:
            reason += "; relationship assessment unavailable (no name or address in the data)"
        if cfg.enabled("DV-01"):
            out.append(Signal(indicator_id="DV-01", entity_id=device, event_ids=event_ids, event_time=when,
                              weight=cfg.weight("DV-01"), category=Category.shared_device, reason=reason,
                              evidence_ids=event_ids))
        if not assessable:
            continue

        if len(set(surnames)) == 1 and len(set(addresses)) == 1:
            if cfg.enabled("MT-HOUSE"):
                out.append(Signal(indicator_id="MT-HOUSE", entity_id=device, event_ids=event_ids, event_time=when,
                                  weight=cfg.weight("MT-HOUSE"), direction=Direction.mitigating,
                                  reason=f"Possible household: all {len(members)} customers share the surname and address (not verified kinship)",
                                  evidence_ids=members))
            continue

        used_apps = apps[apps["device_id"] == device]["application_id"].tolist() if "device_id" in apps else []
        used_txns = txns[txns["device_id"] == device]["txn_id"].tolist() if "device_id" in txns else []
        strength = 1.0 if used_apps or used_txns else 0.5
        detail = f"; {len(used_apps)} loan applications from this device" if used_apps else ""
        where = f" (cities: {', '.join(c.title() for c in cities)})" if len(cities) > 1 else ""
        if cfg.enabled("DV-02"):
            out.append(Signal(indicator_id="DV-02", entity_id=device, event_ids=event_ids, event_time=when,
                              strength=strength, weight=cfg.weight("DV-02"), category=Category.shared_device,
                              reason=f"Customers on this device share no surname or address{where}{detail}",
                              evidence_ids=members + used_apps + used_txns))
    return out
