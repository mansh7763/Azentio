"""Cross-customer money-flow indicators (issue #6, F05/F11): NW-01 recipient convergence, NW-02 circular flow.
Each signal attaches to the transaction that completes the pattern, using only that transaction and earlier ones."""

import pandas as pd

from app.detect.config import RulesConfig
from app.detect.dataset import Dataset
from app.detect.indicators.flows import _outbound
from app.detect.indicators.transfers import money
from app.schemas import Category, Signal

DISBURSEMENT_TYPES = {"loan_disbursement", "disbursement"}
FUNDED_WITHIN = pd.Timedelta(days=7)


def _signal(cfg, indicator_id, t, reason, evidence, strength=1.0, category=Category.suspicious_transfer) -> Signal:
    return Signal(indicator_id=indicator_id, entity_id=t["txn_id"], customer_id=t["customer_id"],
                  event_ids=[t["txn_id"]], event_time=t["timestamp"].to_pydatetime(), strength=strength,
                  weight=cfg.weight(indicator_id), category=category, reason=reason, evidence_ids=evidence)


def _household(customers: pd.DataFrame, members: list[str]) -> bool:
    """Same surname and address for every member: possibly one family paying, e.g., a new landlord."""
    if customers.empty or not {"name", "address"} <= set(customers.columns):
        return False
    info = customers.set_index("customer_id")
    rows = [info.loc[c] for c in members if c in info.index]
    if len(rows) != len(members):
        return False
    surnames = {str(r["name"]).split()[-1].lower() if isinstance(r["name"], str) and r["name"].strip() else None for r in rows}
    addresses = {str(r["address"]).strip().lower() if isinstance(r["address"], str) else None for r in rows}
    return None not in surnames and None not in addresses and len(surnames) == 1 and len(addresses) == 1


def convergence_signals(ds: Dataset, cfg: RulesConfig, profiles: pd.DataFrame) -> list[Signal]:
    """NW-01: `min_payers`+ distinct customers make a FIRST payment to the same beneficiary within `hours`.
    A beneficiary already paid by `established_payers`+ customers before the window is a merchant or collection
    account and does not fire. Stronger when a payer had just received a loan disbursement (mule funnel)."""
    if not cfg.enabled("NW-01"):
        return []
    p = cfg.params("NW-01")
    window = pd.Timedelta(hours=p["hours"])
    txns = ds.get("transactions")
    out_ok = _outbound(txns)
    kinds = txns["type"].astype(str).str.lower() if "type" in txns else pd.Series([""] * len(txns), index=txns.index)
    funded = txns[kinds.isin(DISBURSEMENT_TYPES) & txns["customer_id"].notna()]
    customers = ds.get("customers")

    out: list[Signal] = []
    for payee, g in out_ok.groupby("beneficiary_account", sort=True):
        firsts = [t for t in g.itertuples(index=False) if profiles.loc[t.txn_id, "is_first_payment"] is True]
        for t in firsts:
            start = t.timestamp - window
            recent = [r for r in firsts if start <= r.timestamp and r.seq <= t.seq]
            payers = sorted({r.customer_id for r in recent})
            if len(payers) < p["min_payers"]:
                continue
            before = g[(g["timestamp"] < start)]["customer_id"].nunique()
            if before >= p["established_payers"] or _household(customers, payers):
                continue
            loans = [f.txn_id for r in recent for f in funded[funded["customer_id"] == r.customer_id].itertuples(index=False)
                     if r.timestamp - FUNDED_WITHIN <= f.timestamp <= r.timestamp]
            reason = (f"{len(payers)} unrelated customers ({', '.join(payers)}) made a first payment to {payee} "
                      f"within {p['hours']}h")
            if loans:
                reason += f"; {len(loans)} of them had just received a loan disbursement"
            out.append(_signal(cfg, "NW-01", t._asdict(), reason, [r.txn_id for r in recent] + loans + payers,
                               strength=1.0 if loans else 0.7,
                               category=Category.loan_application_fraud if loans else Category.suspicious_transfer))
    return out


def _close(a: float, b: float, tolerance: float) -> bool:
    return abs(a - b) <= tolerance * max(a, b)


def circular_signals(ds: Dataset, cfg: RulesConfig) -> list[Signal]:
    """NW-02: money returns to where it started through 3..`max_hops` accounts within `hours`, each hop within
    `tolerance` of the previous amount, same currency. A sweep between one customer's own accounts is excluded;
    a two-hop return (A -> B -> A) is a refund, not a cycle."""
    if not cfg.enabled("NW-02"):
        return []
    p = cfg.params("NW-02")
    window, tol, max_hops = pd.Timedelta(hours=p["hours"]), p["tolerance"], p["max_hops"]
    txns = ds.get("transactions")
    edges = _outbound(txns.assign(customer_id=txns["customer_id"].fillna("?")))
    accounts = ds.get("accounts")
    owner = dict(zip(accounts["account_id"], accounts["customer_id"])) if not accounts.empty else {}
    by_sender = {a: list(g.itertuples(index=False)) for a, g in edges.groupby("sender_account")}

    out: list[Signal] = []
    for t in edges.itertuples(index=False):
        start, cur = t.timestamp - window, getattr(t, "currency", None)

        def walk(node, path):
            for e in by_sender.get(node, []):
                last = path[-1] if path else None
                if e.seq >= t.seq or e.timestamp < start or getattr(e, "currency", None) != cur:
                    continue
                if last is not None and (e.seq <= last.seq or not _close(float(last.amount), float(e.amount), tol)):
                    continue
                visited = {x.sender_account for x in path}
                if e.beneficiary_account == t.sender_account:
                    hops = path + [e]
                    if len(hops) + 1 >= 3 and _close(float(e.amount), float(t.amount), tol):
                        return hops
                elif len(path) + 2 < max_hops and e.beneficiary_account not in visited | {node}:
                    found = walk(e.beneficiary_account, path + [e])
                    if found:
                        return found
            return None

        hops = walk(t.beneficiary_account, [])
        if not hops:
            continue
        cycle = [h.sender_account for h in hops] + [t.sender_account, t.beneficiary_account]
        owners = {owner.get(a) for a in cycle[:-1]}
        if len(owners) == 1 and None not in owners:
            continue  # one customer moving money between their own accounts
        hours = (t.timestamp - hops[0].timestamp).total_seconds() / 3600
        out.append(_signal(cfg, "NW-02", t._asdict() | {"customer_id": None if t.customer_id == "?" else t.customer_id},
                           f"Money returned to {cycle[0]} through {' → '.join(cycle[1:-1])} in {hours:.0f}h "
                           f"({len(cycle) - 1} hops of about {money(float(t.amount), cur)}, each within {tol:.0%})",
                           [h.txn_id for h in hops] + [t.txn_id]))
    return out


def network_signals(ds: Dataset, cfg: RulesConfig, profiles: pd.DataFrame) -> list[Signal]:
    if not ds.has("transactions"):
        return []
    return convergence_signals(ds, cfg, profiles) + circular_signals(ds, cfg)
