"""AP-03 loan-to-mule cash-out (plan revision 4, F04): an explicitly linked loan disbursement, then >= 70% of it
leaves the payout account to new recipients within 48 hours. Signals attach to the transfer that crosses the share,
so nothing is judged with hindsight."""

import pandas as pd

from app.detect.config import RulesConfig
from app.detect.dataset import Dataset, is_inbound
from app.detect.indicators.transfers import money
from app.features.profiles import is_successful
from app.schemas import Category, Signal

DISBURSEMENT_TYPES = {"loan_disbursement", "disbursement"}


def _disbursements(txns: pd.DataFrame, apps: pd.DataFrame) -> list[tuple[pd.Series, pd.Series]]:
    """(application, disbursement txn) pairs with an EXPLICIT link: the transaction names the application, or it is
    typed as a disbursement into that application's payout account after the application. Never inferred from a
    plain credit."""
    pairs = []
    by_id = apps.set_index("application_id", drop=False)
    for _, t in txns.iterrows():
        if not is_successful(t.get("status")) or float(t["amount"]) <= 0:
            continue
        kind = str(t.get("type") or "").lower()
        app_ref = t.get("application_id") if "application_id" in txns else None
        if isinstance(app_ref, str) and app_ref in by_id.index:
            app = by_id.loc[app_ref]
            if is_inbound(kind) and app["timestamp"] <= t["timestamp"]:
                pairs.append((app, t))
        elif kind in DISBURSEMENT_TYPES and "disbursement_account" in apps:
            match = apps[(apps["disbursement_account"] == t["beneficiary_account"]) & (apps["timestamp"] <= t["timestamp"])]
            if not match.empty:
                pairs.append((match.sort_values("seq").iloc[-1], t))
    return pairs


def loan_outflow_signals(ds: Dataset, cfg: RulesConfig, profiles: pd.DataFrame, app_signals: list[Signal]) -> list[Signal]:
    txns, apps = ds.get("transactions"), ds.get("applications")
    if txns.empty or apps.empty or not cfg.enabled("AP-03"):
        return []
    params = cfg.params("AP-03")
    share_needed, window = params.get("share", 0.7), pd.Timedelta(hours=params.get("hours", 48))
    flagged = {s.entity_id for s in app_signals if s.indicator_id in ("AP-01", "ID-01")}

    out: list[Signal] = []
    for app, disb in _disbursements(txns, apps):
        amount, account = float(disb["amount"]), disb["beneficiary_account"]
        currency = str(disb.get("currency") or "").strip().upper()
        if not currency:
            continue
        outflows = txns[(txns["sender_account"] == account) & (txns["timestamp"] > disb["timestamp"])
                        & (txns["timestamp"] <= disb["timestamp"] + window)].sort_values("seq")
        total, counted, recipients = 0.0, [], set()
        for _, t in outflows.iterrows():
            if str(t.get("currency") or "").strip().upper() != currency:
                continue
            if is_inbound(t.get("type")) or not is_successful(t.get("status")):
                continue
            if profiles.loc[t["txn_id"], "is_first_payment"] is not True:
                continue  # money to an established payee is ordinary use of the loan
            total += float(t["amount"])
            counted.append(t["txn_id"])
            recipients.add(t["beneficiary_account"])
            if total >= share_needed * amount:
                hours = round((t["timestamp"] - disb["timestamp"]).total_seconds() / 3600)
                cur = disb.get("currency")
                corroborated = app["application_id"] in flagged
                out.append(Signal(
                    indicator_id="AP-03", entity_id=t["txn_id"], customer_id=t["customer_id"],
                    event_ids=[t["txn_id"]], event_time=t["timestamp"].to_pydatetime(),
                    strength=1.0 if corroborated else 0.7, weight=cfg.weight("AP-03"),
                    category=Category.loan_application_fraud,
                    reason=(f"{money(total, cur)} ({total / amount:.0%}) of loan disbursement {disb['txn_id']} "
                            f"({money(amount, cur)}, application {app['application_id']}) sent to "
                            f"{len(recipients)} new recipients within {hours}h"
                            + ("; the application itself was flagged" if corroborated else "")),
                    evidence_ids=[app["application_id"], disb["txn_id"], *counted],
                ))
                break
    return out
