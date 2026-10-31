"""Mitigating factors for transfers (the 'legitimate lookalike' defence)."""

import pandas as pd

from app.detect.config import RulesConfig
from app.detect.dataset import Dataset
from app.detect.indicators.logins import Burst
from app.schemas import Direction, Signal


def _mit(cfg, indicator_id, t, reason, evidence) -> Signal:
    return Signal(indicator_id=indicator_id, entity_id=t["txn_id"], customer_id=t["customer_id"],
                  event_ids=[t["txn_id"]], event_time=t["timestamp"].to_pydatetime(),
                  weight=cfg.weight(indicator_id), direction=Direction.mitigating, reason=reason,
                  evidence_ids=evidence)


def _is_monthly(times: list, now, cadence: float, slack: float) -> bool:
    stamps = [pd.Timestamp(x) for x in times] + [pd.Timestamp(now)]
    gaps = [(b - a).total_seconds() / 86400 for a, b in zip(stamps, stamps[1:])]
    return bool(gaps) and all(abs(g - cadence) <= slack for g in gaps)


def mitigation_signals(ds: Dataset, cfg: RulesConfig, profiles: pd.DataFrame, bursts: list[Burst]) -> list[Signal]:
    txns = ds.get("transactions")
    if txns.empty:
        return []
    payee_p, recur_p, tenure_p = cfg.params("MT-PAYEE"), cfg.params("MT-RECUR"), cfg.params("MT-TENURE")
    logins = ds.get("logins")
    ok_logins = logins[logins["outcome"].astype(str).str.lower() == "success"] if not logins.empty else logins
    customers = ds.get("customers")
    onboarded = dict(zip(customers["customer_id"], customers["onboarding_date"])) if "onboarding_date" in customers else {}

    out: list[Signal] = []
    for _, t in txns.sort_values("seq").iterrows():
        prof = profiles.loc[t["txn_id"]]
        same = int(prof["prior_same_payee_similar"])
        times = prof["prior_same_payee_times"]

        if cfg.enabled("MT-PAYEE") and same >= payee_p.get("min_prior", 3):
            out.append(_mit(cfg, "MT-PAYEE", t, f"Regular payee: {same} earlier payments of a similar amount to "
                                                f"{t['beneficiary_account']}", [t["txn_id"]]))

        if (cfg.enabled("MT-RECUR") and len(times) >= recur_p.get("min_prior", 3)
                and _is_monthly(times, t["timestamp"], recur_p.get("cadence_days", 30), recur_p.get("slack_days", 3))):
            out.append(_mit(cfg, "MT-RECUR", t, f"Recurring monthly payment to {t['beneficiary_account']} "
                                                f"({len(times)} earlier)", [t["txn_id"]]))

        device = t.get("device_id")
        if cfg.enabled("MT-KNOWN") and isinstance(device, str) and not ok_logins.empty:
            seen = ok_logins[(ok_logins["customer_id"] == t["customer_id"]) & (ok_logins["device_id"] == device)
                             & (ok_logins["timestamp"] < t["timestamp"])]
            if len(seen) >= 2:
                out.append(_mit(cfg, "MT-KNOWN", t, f"Made from the customer's usual device {device}",
                                list(seen["event_id"].tail(3))))

        since = onboarded.get(t["customer_id"])
        days = tenure_p.get("days", 365)
        if cfg.enabled("MT-TENURE") and since is not None and pd.notna(since) and (t["timestamp"] - since).days >= days:
            out.append(_mit(cfg, "MT-TENURE", t, f"Customer since {since:%b %Y}", [t["customer_id"]]))
    return out
