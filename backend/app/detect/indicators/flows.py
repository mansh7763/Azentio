"""Rolling-flow indicators for frauds that stay under per-payment rules (issue #6, F09/F10 and structuring):
TX-06 cumulative outflow, TX-07 structuring, TX-08 dormant account awakening.
Every check uses only the customer's strictly earlier events (by seq), like the rest of the engine."""

import numpy as np
import pandas as pd

from app.detect.config import RulesConfig
from app.detect.dataset import Dataset, is_inbound
from app.detect.indicators.transfers import hv_threshold, money
from app.features.profiles import is_successful
from app.schemas import Category, Signal


def _signal(cfg, indicator_id, t, reason, evidence, strength=1.0) -> Signal:
    return Signal(indicator_id=indicator_id, entity_id=t["txn_id"], customer_id=t["customer_id"],
                  event_ids=[t["txn_id"]], event_time=t["timestamp"].to_pydatetime(), strength=strength,
                  weight=cfg.weight(indicator_id), category=Category.suspicious_transfer, reason=reason,
                  evidence_ids=evidence)


def _outbound(txns: pd.DataFrame) -> pd.DataFrame:
    kinds = txns["type"] if "type" in txns else pd.Series([None] * len(txns), index=txns.index)
    status = txns["status"] if "status" in txns else pd.Series([None] * len(txns), index=txns.index)
    keep = pd.Series([not is_inbound(k) and is_successful(s) for k, s in zip(kinds, status)], index=txns.index)
    return txns[keep & txns["customer_id"].notna()].sort_values("seq")


def _established(profiles: pd.DataFrame, txn_id: str, min_prior: int) -> bool:
    return int(profiles.loc[txn_id, "prior_same_payee_similar"]) >= min_prior


def cumulative_signals(ds: Dataset, cfg: RulesConfig, profiles: pd.DataFrame) -> list[Signal]:
    """TX-06: the rolling total over a window is at least `min_ratio` times the customer's own `quantile` of earlier
    same-length windows (a bare p95 is exceeded by ~5% of normal windows by construction, hence the margin).
    Needs >= 2 payments in the window (one payment is TX-01's job) and at least one to a payee that is not
    established, so regular bills cannot trip it on their own."""
    if not cfg.enabled("TX-06"):
        return []
    p = cfg.params("TX-06")
    min_prior = cfg.params("MT-PAYEE")["min_prior"]
    out: list[Signal] = []
    for _, g in _outbound(ds.get("transactions")).groupby("customer_id", sort=True):
        rows = list(g.itertuples(index=False))
        earlier: dict[float, list[tuple]] = {h: [] for h in p["windows_hours"]}  # (window end, total)
        for i, t in enumerate(rows):
            best = None
            for hours in p["windows_hours"]:
                start = t.timestamp - pd.Timedelta(hours=hours)
                window = [r for r in rows[:i + 1] if r.timestamp > start]
                total = sum(float(r.amount) for r in window)
                # Only windows that ended before this one starts: the episode under test must not become its
                # own baseline (otherwise a burst's early payments make its later ones look normal).
                base = [tot for end, tot in earlier[hours] if end <= start]
                if len(base) >= p["min_windows"] and len(window) >= 2:
                    ref = float(np.quantile(base, p["quantile"]))
                    unestablished = [r for r in window if not _established(profiles, r.txn_id, min_prior)]
                    # A drain is many modest payments: the total must clear the margin even without its largest
                    # payment, so one big transfer (TX-01's job) is never re-flagged on the payments after it.
                    spread = total - max(float(r.amount) for r in window)
                    if ref > 0 and spread >= p["min_ratio"] * ref and unestablished:
                        ratio = total / ref
                        if best is None or ratio > best[0]:
                            best = (ratio, hours, total, ref, window)
                earlier[hours].append((t.timestamp, total))
            if best:
                ratio, hours, total, ref, window = best
                cur = getattr(t, "currency", None)
                span = f"{int(hours)}h" if hours < 48 else f"{int(hours // 24)} days"
                out.append(_signal(cfg, "TX-06", t._asdict(),
                                   f"{money(total, cur)} sent in {len(window)} payments within {span}, "
                                   f"{ratio:.1f}× the customer's usual {span} total ({money(ref, cur)})",
                                   [r.txn_id for r in window], strength=min(1.0, 0.5 + (ratio - p["min_ratio"]) / (2 * p["min_ratio"]))))
    return out


def structuring_signals(ds: Dataset, cfg: RulesConfig, profiles: pd.DataFrame) -> list[Signal]:
    """TX-07: `count`+ payments within `hours`, each between `low` and `high` of the amount that would flag a single
    payment for this customer (TX-01's trigger from their own baseline, or the HV-01 threshold), to payees that are
    not established. Splitting one large transfer to stay under the line is itself the signal.
    Each payment must also be unusually high for the customer (z >= `min_z`): a steady payer whose normal amount
    happens to sit near their own trigger (e.g. equal monthly payroll) is not structuring."""
    if not cfg.enabled("TX-07"):
        return []
    p = cfg.params("TX-07")
    z_min = cfg.params("TX-01")["z_min"]
    min_prior = cfg.params("MT-PAYEE")["min_prior"]
    hv = hv_threshold(ds, cfg)
    source, median = profiles["baseline_source"].to_dict(), profiles["prior_median"].to_dict()
    denom = profiles["denom"].to_dict()
    established = (profiles["prior_same_payee_similar"].astype(int) >= min_prior).to_dict()

    def trigger(txn_id) -> float | None:
        refs = []
        if source[txn_id] == "customer":
            refs.append(float(median[txn_id]) + z_min * float(denom[txn_id]))
        if hv.get(txn_id):
            refs.append(float(hv[txn_id]))
        return min(refs) if refs else None

    out: list[Signal] = []
    span = pd.Timedelta(hours=p["hours"])
    for _, g in _outbound(ds.get("transactions")).groupby("customer_id", sort=True):
        rows = list(g.itertuples(index=False))
        for i, t in enumerate(rows):
            window = [r for r in rows[:i + 1] if r.timestamp >= t.timestamp - span]
            # The bar as it stood before this window: payments being judged must not raise their own threshold
            # (structured payments enter the baseline and would otherwise hide the later ones).
            ref = window[0].txn_id
            level = trigger(ref)
            if level is None:
                continue

            def near(r) -> bool:
                amount = float(r.amount)
                unusual = source[ref] != "customer" or (amount - float(median[ref])) / float(denom[ref]) >= p["min_z"]
                return p["low"] * level <= amount < p["high"] * level and unusual and not established[r.txn_id]

            hits = [r for r in window if near(r)]
            if len(hits) >= p["count"] and hits[-1] is t:
                cur = getattr(t, "currency", None)
                lo, hi = min(float(r.amount) for r in hits), max(float(r.amount) for r in hits)
                out.append(_signal(cfg, "TX-07", t._asdict(),
                                   f"{len(hits)} payments of {money(lo, cur)}–{money(hi, cur)} within {p['hours']}h, "
                                   f"each just below the {money(level, cur)} that would flag one payment for this "
                                   f"customer", [r.txn_id for r in hits]))
    return out


def dormancy_signals(ds: Dataset, cfg: RulesConfig, profiles: pd.DataFrame) -> list[Signal]:
    """TX-08: after >= `dormant_days` with no outgoing payment, following >= `observed_days` of history, payments to
    first-time payees within `follow_days` of the reawakening. A short file cannot establish dormancy, so customers
    without enough observed history are never flagged here."""
    if not cfg.enabled("TX-08"):
        return []
    p = cfg.params("TX-08")
    dormant, observed = pd.Timedelta(days=p["dormant_days"]), pd.Timedelta(days=p["observed_days"])
    follow = pd.Timedelta(days=p["follow_days"])
    txns = ds.get("transactions")
    first_seen = txns.groupby("customer_id")["timestamp"].min().to_dict()
    out: list[Signal] = []
    for cid, g in _outbound(txns).groupby("customer_id", sort=True):
        rows = list(g.itertuples(index=False))
        woke, quiet = None, None
        for prev, t in zip([None] + rows[:-1], rows):
            if prev is not None and t.timestamp - prev.timestamp >= dormant \
                    and t.timestamp - first_seen[cid] >= observed:
                woke, quiet = t.timestamp, (t.timestamp - prev.timestamp).days
            if woke is not None and t.timestamp - woke <= follow and profiles.loc[t.txn_id, "is_first_payment"] is True:
                out.append(_signal(cfg, "TX-08", t._asdict(),
                                   f"First payment to {t.beneficiary_account} shortly after {quiet} days with no "
                                   f"outgoing payments (account reawakened {woke:%d %b %Y})", [t.txn_id]))
    return out


def flow_signals(ds: Dataset, cfg: RulesConfig, profiles: pd.DataFrame) -> list[Signal]:
    if not ds.has("transactions"):
        return []
    return (cumulative_signals(ds, cfg, profiles) + structuring_signals(ds, cfg, profiles)
            + dormancy_signals(ds, cfg, profiles))
