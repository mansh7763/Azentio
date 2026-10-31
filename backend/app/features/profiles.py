"""Point-in-time behavioural baselines: every feature for an event uses only strictly earlier events."""

from collections import defaultdict

import numpy as np
import pandas as pd

from app.detect.config import RulesConfig
from app.detect.dataset import Dataset

SUCCESS = {"success", "successful", "completed", "complete", "posted", "ok", "settled"}
INBOUND = {"credit", "inbound", "deposit", "incoming", "refund", "salary_credit"}
PROFILE_COLUMNS = ["customer_id", "prior_n", "prior_median", "prior_mad", "prior_p95", "prior_max", "denom", "z",
                   "is_new_payee", "is_first_payment", "prior_same_payee_similar", "prior_same_payee_times",
                   "baseline_source"]


def denominator(median: float, mad: float, floor_amount: float) -> float:
    """Robust-z denominator; never zero, even for fixed payments (MAD = 0)."""
    return max(1.4826 * mad, 0.1 * median, floor_amount)


def is_successful(status) -> bool:
    return status is None or (isinstance(status, float) and np.isnan(status)) or str(status).lower() in SUCCESS


def is_outbound(kind) -> bool:
    return kind is None or (isinstance(kind, float) and np.isnan(kind)) or str(kind).lower() not in INBOUND


def baseline_rows(txns: pd.DataFrame) -> pd.Series:
    """Rows that may form a baseline: successful and outbound."""
    status = txns["status"] if "status" in txns else pd.Series([None] * len(txns), index=txns.index)
    kind = txns["type"] if "type" in txns else pd.Series([None] * len(txns), index=txns.index)
    return pd.Series([is_successful(s) and is_outbound(k) for s, k in zip(status, kind)], index=txns.index)


def _stats(values: list[float]) -> tuple[float, float, float, float]:
    arr = np.asarray(values, dtype=float)
    median = float(np.median(arr))
    return median, float(np.median(np.abs(arr - median))), float(np.percentile(arr, 95)), float(arr.max())


def transaction_profiles(ds: Dataset, cfg: RulesConfig) -> pd.DataFrame:
    """One row per transaction (indexed by txn_id), computed from strictly earlier rows (by seq)."""
    txns = ds.get("transactions")
    if txns.empty:
        return pd.DataFrame(columns=PROFILE_COLUMNS)
    customers = ds.get("customers")
    segment_of = dict(zip(customers["customer_id"], customers["segment"])) if "segment" in customers else {}
    usable = baseline_rows(txns)
    tolerance = cfg.params("MT-PAYEE").get("tolerance", 0.25)

    # Baselines are per currency: INR history says nothing about a USD payment, and no FX is guessed.
    by_customer: dict[tuple, list[float]] = defaultdict(list)
    by_segment: dict[tuple, list[float]] = defaultdict(list)
    by_currency: dict[str, list[float]] = defaultdict(list)
    payees: dict[str, dict[str, list[tuple[float, object]]]] = defaultdict(lambda: defaultdict(list))

    rows = []
    for idx, t in txns.sort_values("seq").iterrows():
        cid, amount, payee = t["customer_id"], float(t["amount"]), t["beneficiary_account"]
        currency = str(t.get("currency") or "").upper()
        segment = segment_of.get(cid)
        own = by_customer[(cid, currency)]
        global_amounts = by_currency[currency]
        if len(own) >= cfg.min_history:
            source, base = "customer", own
        elif segment and len(by_segment[(segment, currency)]) >= cfg.min_history:
            source, base = "segment", by_segment[(segment, currency)]
        elif global_amounts:
            source, base = "global", global_amounts
        else:
            source, base = "none", []

        if base:
            median, mad, p95, mx = _stats(base)
            denom = denominator(median, mad, cfg.floor_amount)
            z = (amount - median) / denom
        else:
            median = mad = p95 = mx = float("nan")
            denom, z = cfg.floor_amount, 0.0

        history = payees[cid]
        is_first = payee not in history
        is_new = None if len(own) < cfg.min_history else is_first
        same = history.get(payee, [])
        similar = sum(1 for a, _ in same if abs(a - amount) <= tolerance * max(a, amount))
        rows.append({
            "txn_id": t["txn_id"], "customer_id": cid, "prior_n": len(own), "prior_median": median,
            "prior_mad": mad, "prior_p95": p95, "prior_max": mx, "denom": denom, "z": z,
            "is_new_payee": is_new, "is_first_payment": is_first, "prior_same_payee_similar": similar,
            "prior_same_payee_times": [ts for _, ts in same], "baseline_source": source,
        })

        if usable[idx]:
            own.append(amount)
            if segment:
                by_segment[(segment, currency)].append(amount)
            global_amounts.append(amount)
            history[payee].append((amount, t["timestamp"]))

    out = pd.DataFrame(rows).set_index("txn_id")
    out["is_new_payee"] = out["is_new_payee"].astype(object)
    out["is_first_payment"] = out["is_first_payment"].astype(object)
    return out
