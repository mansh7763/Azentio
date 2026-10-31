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


def _money_groups(txns: pd.DataFrame):
    """Compare amounts only within a known currency; never invent an FX conversion."""
    out = _outbound(txns).copy()
    currency = out.get("currency", pd.Series(index=out.index, dtype=object))
    out["_currency"] = currency.fillna("").astype(str).str.strip().str.upper()
    return out[out["_currency"] != ""].groupby(["customer_id", "_currency"], sort=True)


def cumulative_signals(ds: Dataset, cfg: RulesConfig, profiles: pd.DataFrame) -> list[Signal]:
    """TX-06: money sent within a window to payees first paid inside that window is at least `min_ratio` times the
    customer's own `quantile` of earlier same-length window totals (F10: new-payee concentration). A bare p95 is
    exceeded by ~5% of normal windows by construction, hence the margin.
    Needs >= 2 payments in the window (one payment is TX-01's job) and at least one to a payee that is not
    established, so regular bills cannot trip it on their own."""
    if not cfg.enabled("TX-06"):
        return []
    p = cfg.params("TX-06")
    first = profiles["is_first_payment"].to_dict()
    out: list[Signal] = []
    for _, g in _money_groups(ds.get("transactions")):
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
                new_payees = {r.beneficiary_account for r in window if first[r.txn_id] is True}
                to_new = [r for r in window if r.beneficiary_account in new_payees]
                if len(base) >= p["min_windows"] and len(to_new) >= 2:
                    ref = float(np.quantile(base, p["quantile"]))
                    # A drain is many modest payments: the total must clear the margin even without its largest
                    # payment, so one big transfer (TX-01's job) is never re-flagged on the payments after it.
                    amounts = [float(r.amount) for r in to_new]
                    spread = sum(amounts) - max(amounts)
                    if ref > 0 and spread >= p["min_ratio"] * ref:
                        ratio = sum(amounts) / ref
                        if best is None or ratio > best[0]:
                            best = (ratio, hours, sum(amounts), ref, to_new, len(new_payees))
                earlier[hours].append((t.timestamp, total))
            if best:
                ratio, hours, total, ref, window, payees = best
                cur = getattr(t, "currency", None)
                span = f"{int(hours)}h" if hours < 48 else f"{int(hours // 24)} days"
                out.append(_signal(cfg, "TX-06", t._asdict(),
                                   f"{money(total, cur)} sent to {payees} new payees in {len(window)} payments within "
                                   f"{span}, {ratio:.1f}× the customer's usual {span} total ({money(ref, cur)})",
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
    for _, g in _money_groups(ds.get("transactions")):
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


def passthrough_signals(ds: Dataset, cfg: RulesConfig, profiles: pd.DataFrame) -> list[Signal]:
    """TX-09: >= `share` of an incoming credit leaves within `hours` to >= `min_payees` payees paid for the first
    time: the mule pass-through signature. Needs no history, so it covers brand-new accounts where baselines cannot
    (evaluation D2, cold start). Signals attach to the payment that crosses the share."""
    if not cfg.enabled("TX-09"):
        return []
    p = cfg.params("TX-09")
    span = pd.Timedelta(hours=p["hours"])
    txns = ds.get("transactions")
    kinds = txns["type"] if "type" in txns else pd.Series([None] * len(txns), index=txns.index)
    inbound = pd.Series([is_inbound(k) for k in kinds], index=txns.index)
    credits = txns[inbound & txns["customer_id"].notna()]
    first = profiles["is_first_payment"].to_dict()
    outbound = {cid: list(g.itertuples(index=False)) for cid, g in _outbound(txns).groupby("customer_id")}
    out: list[Signal] = []
    for c in credits.sort_values("seq").itertuples(index=False):
        currency = str(getattr(c, "currency", "") or "").strip().upper()
        if not currency or not is_successful(getattr(c, "status", None)) or float(c.amount) <= 0:
            continue
        amount, moved, used, payees = float(c.amount), 0.0, [], set()
        for t in outbound.get(c.customer_id, []):
            if str(getattr(t, "currency", "") or "").strip().upper() != currency:
                continue
            if t.seq <= c.seq or t.timestamp > c.timestamp + span or first[t.txn_id] is not True:
                continue
            moved += float(t.amount)
            used.append(t.txn_id)
            payees.add(t.beneficiary_account)
            if moved >= p["share"] * amount and len(payees) >= p["min_payees"]:
                hours = (t.timestamp - c.timestamp).total_seconds() / 3600
                cur = getattr(c, "currency", None)
                out.append(_signal(cfg, "TX-09", t._asdict(),
                                   f"{moved / amount:.0%} of an incoming {money(amount, cur)} ({c.txn_id}) left to "
                                   f"{len(payees)} new payees within {hours:.0f}h", [c.txn_id, *used]))
                break
    return out


def flow_signals(ds: Dataset, cfg: RulesConfig, profiles: pd.DataFrame) -> list[Signal]:
    if not ds.has("transactions"):
        return []
    return (cumulative_signals(ds, cfg, profiles) + structuring_signals(ds, cfg, profiles)
            + dormancy_signals(ds, cfg, profiles) + passthrough_signals(ds, cfg, profiles))
