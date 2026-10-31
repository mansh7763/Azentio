"""Transfer indicators: TX-01..05 and the high-value flag HV-01."""

from bisect import bisect_left

import numpy as np
import pandas as pd

from app.detect.config import RulesConfig
from app.detect.dataset import Dataset, is_inbound
from app.features.profiles import baseline_rows
from app.schemas import Category, Signal

SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "AED": "AED ", "SAR": "SAR "}


def money(amount: float, currency: str | None = None) -> str:
    return f"{SYMBOLS.get(str(currency or '').upper(), '')}{amount:,.0f}"


def hv_threshold(ds: Dataset, cfg: RulesConfig) -> dict[str, float | None]:
    """High-value threshold per transaction: a configured value, or the p90 of EARLIER successful outbound
    transfers in the same currency. None when there are fewer than `min_samples` (HV-01 then cannot fire)."""
    params = cfg.params("HV-01")
    txns = ds.get("transactions")
    if txns.empty:
        return {}
    if params.get("threshold") is not None:
        return {tid: float(params["threshold"]) for tid in txns["txn_id"]}
    quantile, min_samples = params.get("quantile", 0.9), params.get("min_samples", 20)
    usable = baseline_rows(txns)
    ordered = txns.sort_values("seq")
    currencies = ordered["currency"].map(lambda c: str(c or "").upper()) if "currency" in ordered         else pd.Series([""] * len(ordered), index=ordered.index)
    # One growing array per currency; np.percentile with "linear" is exactly what Series.quantile computes,
    # without building a new Series for every transaction (that was quadratic on large uploads).
    seen: dict[str, np.ndarray] = {}
    count: dict[str, int] = {}
    out: dict[str, float | None] = {}
    for idx, tid, amount, currency in zip(ordered.index, ordered["txn_id"], ordered["amount"], currencies):
        n = count.get(currency, 0)
        prior = seen.setdefault(currency, np.empty(len(ordered)))
        out[tid] = float(np.percentile(prior[:n], quantile * 100, method="linear")) if n >= min_samples else None
        if usable[idx]:
            prior[n] = float(amount)
            count[currency] = n + 1
    return out


def _signal(cfg, indicator_id, t, reason, strength=1.0, event_ids=None) -> Signal:
    return Signal(
        indicator_id=indicator_id, entity_id=t["txn_id"], customer_id=t["customer_id"],
        event_ids=event_ids or [t["txn_id"]], event_time=t["timestamp"].to_pydatetime(),
        strength=strength, weight=cfg.weight(indicator_id), category=Category.suspicious_transfer,
        reason=reason, evidence_ids=event_ids or [t["txn_id"]],
    )


def transfer_signals(ds: Dataset, cfg: RulesConfig, profiles: pd.DataFrame) -> list[Signal]:
    txns = ds.get("transactions")
    if txns.empty:
        return []
    out: list[Signal] = []
    p1, p2 = cfg.params("TX-01"), cfg.params("TX-02")
    p4, p5 = cfg.params("TX-04"), cfg.params("TX-05")
    thresholds = hv_threshold(ds, cfg)
    # No balance-share check: the accounts file holds a snapshot balance of unknown timing, and a share of it
    # would need the balance immediately before the payment (revision 4).

    window = pd.Timedelta(minutes=p4["minutes"])
    fan_window = pd.Timedelta(hours=p5.get("hours", 24))
    kinds = txns["type"] if "type" in txns else pd.Series([None] * len(txns), index=txns.index)
    outbound = txns[[not is_inbound(k) for k in kinds]]
    # Per customer, in seq order (which is time order after prepare): a window ending at a transaction is a
    # contiguous slice found by binary search, instead of filtering the customer's frame for every transaction.
    first_flag = profiles["is_first_payment"].to_dict()
    by_customer = {}
    for cid, g in outbound.groupby("customer_id"):
        g = g.sort_values("seq")
        by_customer[cid] = (list(g["timestamp"]), list(g["txn_id"]), list(g["beneficiary_account"]),
                            {tid: i for i, tid in enumerate(g["txn_id"])})

    for _, t in outbound.sort_values("seq").iterrows():  # incoming credits are never scored as outgoing risk
        prof = profiles.loc[t["txn_id"]]
        amount, cur = float(t["amount"]), t.get("currency")
        median = prof["prior_median"]

        if cfg.enabled("TX-01") and prof["baseline_source"] != "none" and prof["z"] >= p1.get("z_min", 3.0):
            ratio = amount / median if median else float("inf")
            strength = min(1.0, max(0.5, prof["z"] / (2 * p1.get("z_min", 3.0))))
            if prof["baseline_source"] != "customer":
                strength *= 0.5  # other customers' spending is weaker evidence than the customer's own history
            whose = "the customer's" if prof["baseline_source"] == "customer" else f"the {prof['baseline_source']}"
            out.append(_signal(cfg, "TX-01", t, f"{money(amount, cur)} is {ratio:,.0f}× {whose} usual {money(median, cur)}", strength))

        if (cfg.enabled("TX-02") and prof["baseline_source"] == "customer"
                and amount > prof["prior_p95"] and amount > p2.get("median_multiple", 2.0) * median):
            out.append(_signal(cfg, "TX-02", t, f"{money(amount, cur)} is above the customer's previous maximum pattern (95th percentile {money(prof['prior_p95'], cur)})"))

        if cfg.enabled("TX-03") and prof["is_new_payee"] is True:
            out.append(_signal(cfg, "TX-03", t, f"First payment to beneficiary {t['beneficiary_account']}"))

        own = by_customer.get(t["customer_id"])
        if own is None:  # unresolved customer: the transaction is its own history
            own = ([t["timestamp"]], [t["txn_id"]], [t["beneficiary_account"]], {t["txn_id"]: 0})
        times, tids, payees_of, position = own
        end = position[t["txn_id"]] + 1
        recent = tids[bisect_left(times, t["timestamp"] - window, 0, end):end]
        if cfg.enabled("TX-04") and len(recent) >= p4.get("count", 5):
            mins = int(window.total_seconds() // 60)
            out.append(_signal(cfg, "TX-04", t, f"{len(recent)} transfers within {mins} minutes", event_ids=recent))

        if cfg.enabled("TX-05"):
            start = bisect_left(times, t["timestamp"] - fan_window, 0, end)
            first = [i for i in range(start, end) if first_flag[tids[i]] is True]
            payees = len({payees_of[i] for i in first})
            if payees >= p5.get("new_payees", 4):
                hours = int(fan_window.total_seconds() // 3600)
                out.append(_signal(cfg, "TX-05", t, f"Money sent to {payees} new beneficiaries within {hours} hours", event_ids=[tids[i] for i in first]))

        threshold = thresholds.get(t["txn_id"])
        if cfg.enabled("HV-01") and threshold is not None and amount >= threshold:
            out.append(_signal(cfg, "HV-01", t, f"High-value transfer: {money(amount, cur)} "
                                                f"(threshold {money(threshold, cur)} from earlier transfers)"))
    return out
