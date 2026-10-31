"""Transfer indicators: TX-01..05 and the high-value flag HV-01."""

import pandas as pd

from app.detect.config import RulesConfig
from app.detect.dataset import Dataset
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
    seen: dict[str, list[float]] = {}
    out: dict[str, float | None] = {}
    for idx, t in txns.sort_values("seq").iterrows():
        currency = str(t.get("currency") or "").upper()
        prior = seen.setdefault(currency, [])
        out[t["txn_id"]] = float(pd.Series(prior).quantile(quantile)) if len(prior) >= min_samples else None
        if usable[idx]:
            prior.append(float(t["amount"]))
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

    window = pd.Timedelta(minutes=p4.get("minutes", 60))
    fan_window = pd.Timedelta(hours=p5.get("hours", 24))
    by_customer = {cid: g.sort_values("seq") for cid, g in txns.groupby("customer_id")}

    for _, t in txns.sort_values("seq").iterrows():
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

        own = by_customer[t["customer_id"]]
        recent = own[(own["seq"] <= t["seq"]) & (own["timestamp"] >= t["timestamp"] - window)]
        if cfg.enabled("TX-04") and len(recent) >= p4.get("count", 5):
            mins = int(window.total_seconds() // 60)
            out.append(_signal(cfg, "TX-04", t, f"{len(recent)} transfers within {mins} minutes", event_ids=list(recent["txn_id"])))

        if cfg.enabled("TX-05"):
            fan = own[(own["seq"] <= t["seq"]) & (own["timestamp"] >= t["timestamp"] - fan_window)]
            first = fan[[profiles.loc[i, "is_first_payment"] is True for i in fan["txn_id"]]]
            payees = first["beneficiary_account"].nunique()
            if payees >= p5.get("new_payees", 4):
                hours = int(fan_window.total_seconds() // 3600)
                out.append(_signal(cfg, "TX-05", t, f"Money sent to {payees} new beneficiaries within {hours} hours", event_ids=list(first["txn_id"])))

        threshold = thresholds.get(t["txn_id"])
        if cfg.enabled("HV-01") and threshold is not None and amount >= threshold:
            out.append(_signal(cfg, "HV-01", t, f"High-value transfer: {money(amount, cur)} "
                                                f"(threshold {money(threshold, cur)} from earlier transfers)"))
    return out
