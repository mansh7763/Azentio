"""Loan application indicators: AP-01 (identity attributes shared across applicants), AP-02 (velocity)."""

import pandas as pd

from app.detect.config import RulesConfig
from app.detect.dataset import Dataset
from app.schemas import Category, Signal

SHARED_ATTRIBUTES = ("device_id", "ip", "phone", "email")


def application_signals(ds: Dataset, cfg: RulesConfig) -> list[Signal]:
    apps = ds.get("applications")
    if apps.empty:
        return []
    p1, p2 = cfg.params("AP-01"), cfg.params("AP-02")
    min_applicants = p1.get("min_applicants", 3)
    window = pd.Timedelta(days=p2.get("days", 7))
    out: list[Signal] = []

    # AP-01 looks at the whole batch: once a ring is visible, its earlier members are flagged too.
    shared: dict[tuple[str, str], pd.DataFrame] = {}
    for attr in SHARED_ATTRIBUTES:
        if attr in apps:
            for value, g in apps[apps[attr].map(lambda v: isinstance(v, str) and v != "")].groupby(attr):
                if g["customer_id"].nunique() >= min_applicants:
                    shared[(attr, value)] = g

    for _, a in apps.sort_values("seq").iterrows():
        when = a["timestamp"].to_pydatetime()
        hits = [(attr, value, g) for (attr, value), g in shared.items() if a.get(attr) == value]
        if hits and cfg.enabled("AP-01"):
            parts = [f"{attr.replace('_id', '')} {value} shared by {g['customer_id'].nunique()} applicants"
                     for attr, value, g in hits]
            ids = sorted({i for _, _, g in hits for i in g["application_id"]})
            out.append(Signal(indicator_id="AP-01", entity_id=a["application_id"], customer_id=a["customer_id"],
                              event_ids=[a["application_id"]], event_time=when, weight=cfg.weight("AP-01"),
                              category=Category.loan_application_fraud, reason="; ".join(parts), evidence_ids=ids))

        if cfg.enabled("AP-02"):
            prior = apps[(apps["seq"] <= a["seq"]) & (apps["timestamp"] >= a["timestamp"] - window)]
            for attr, label in (("customer_id", "customer"), ("device_id", "device")):
                if attr in apps and isinstance(a.get(attr), str):
                    same = prior[prior[attr] == a[attr]]
                    if len(same) >= p2.get("count", 3):
                        out.append(Signal(indicator_id="AP-02", entity_id=a["application_id"],
                                          customer_id=a["customer_id"], event_ids=[a["application_id"]],
                                          event_time=when, weight=cfg.weight("AP-02"),
                                          category=Category.loan_application_fraud,
                                          reason=f"{len(same)} applications from one {label} within {window.days} days",
                                          evidence_ids=list(same["application_id"])))
                        break
    return out
