"""Loan application indicators, each judged at the application's own time (no later applications):
AP-01 coordinated applicants (same device + shared contact/payout), AP-02 velocity, AP-04 shared payout account,
ID-01 contact conflict, ID-02 normalised identity reuse."""

import re

import pandas as pd

from app.detect.config import RulesConfig
from app.detect.dataset import Dataset
from app.schemas import Category, Signal

CONTACTS = ("phone", "email", "disbursement_account")


def _norm(attr: str, value) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    if attr == "phone":
        digits = re.sub(r"\D", "", value)
        return digits[-10:] or None  # "+91 90000 00001" and "9000000001" are one fact
    return value.strip().lower()


def _email(value) -> str | None:
    """Mailbox identity: case-insensitive; for Gmail, dots and '+tags' in the local part reach the same inbox."""
    if not isinstance(value, str) or "@" not in value:
        return None
    local, domain = value.strip().lower().rsplit("@", 1)
    if domain in ("gmail.com", "googlemail.com"):
        local, domain = local.split("+", 1)[0].replace(".", ""), "gmail.com"
    return f"{local}@{domain}" if local else None


def _person(c) -> dict:
    name = c.get("name") if isinstance(c.get("name"), str) else ""
    return {"phone": _norm("phone", c.get("phone")), "email": _email(c.get("email")), "name": name.strip().lower(),
            "surname": name.split()[-1].lower() if name.split() else None,
            "address": _norm("address", c.get("address")), "since": c.get("onboarding_date")}


def _signal(cfg, indicator_id, a, reason, evidence) -> Signal:
    return Signal(indicator_id=indicator_id, entity_id=a["application_id"], customer_id=a["customer_id"],
                  event_ids=[a["application_id"]], event_time=a["timestamp"].to_pydatetime(),
                  weight=cfg.weight(indicator_id), category=Category.loan_application_fraud,
                  reason=reason, evidence_ids=evidence)


def application_signals(ds: Dataset, cfg: RulesConfig) -> list[Signal]:
    apps = ds.get("applications")
    if apps.empty:
        return []
    p1, p2 = cfg.params("AP-01"), cfg.params("AP-02")
    min_applicants = p1.get("min_applicants", 3)
    cluster_window = pd.Timedelta(hours=p1.get("window_hours", 72))
    velocity_window = pd.Timedelta(days=p2.get("days", 7))
    p4 = cfg.params("AP-04")
    payout_window = pd.Timedelta(days=p4["days"]) if p4 else None
    apps = apps.sort_values("seq").copy()
    for attr in CONTACTS:
        apps[f"_{attr}"] = apps[attr].map(lambda v, a=attr: _norm(a, v)) if attr in apps else None

    profile, people = {}, {}
    customers = ds.get("customers")
    if not customers.empty:
        for _, c in customers.iterrows():
            profile[c["customer_id"]] = {a: _norm(a, c.get(a)) for a in ("phone", "email")}
            people[c["customer_id"]] = _person(c)

    out: list[Signal] = []
    for _, a in apps.iterrows():
        prior = apps[apps["seq"] <= a["seq"]]

        # AP-01: >= min applicants on the same device within the window, who also share a contact or payout account.
        device = a.get("device_id")
        if cfg.enabled("AP-01") and isinstance(device, str) and device:
            cluster = prior[(prior["device_id"] == device) & (prior["timestamp"] >= a["timestamp"] - cluster_window)]
            shared = [attr for attr in CONTACTS
                      if a[f"_{attr}"] and cluster[cluster[f"_{attr}"] == a[f"_{attr}"]]["customer_id"].nunique() >= 2]
            applicants = cluster["customer_id"].nunique()
            if applicants >= min_applicants and shared:
                hours = int(cluster_window.total_seconds() // 3600)
                what = ", ".join(s.replace("disbursement_account", "payout account") for s in shared)
                out.append(_signal(cfg, "AP-01", a, f"{applicants} applicants on device {device} within {hours}h, "
                                                    f"sharing {what}", list(cluster["application_id"])))

        # AP-04: one payout account named by >= min_applicants distinct applicants within `days`, whatever devices
        # they used: a swarm that spreads across devices to evade AP-01 (issue #6 B3). One household is excluded.
        payout = a.get("_disbursement_account")
        if cfg.enabled("AP-04") and isinstance(payout, str) and payout:
            same = prior[(prior["_disbursement_account"] == payout) & (prior["timestamp"] >= a["timestamp"] - payout_window)]
            applicants = sorted(same["customer_id"].dropna().unique())
            family = {(people.get(c, {}).get("surname"), people.get(c, {}).get("address")) for c in applicants}
            household = len(family) == 1 and None not in next(iter(family))
            if len(applicants) >= p4["min_applicants"] and not household:
                out.append(_signal(cfg, "AP-04", a, f"{len(applicants)} applicants ({', '.join(applicants)}) named the "
                                                    f"same payout account {a['disbursement_account']} within "
                                                    f"{payout_window.days} days", list(same["application_id"]) + applicants))

        # AP-02: velocity from one customer or one device.
        if cfg.enabled("AP-02"):
            recent = prior[prior["timestamp"] >= a["timestamp"] - velocity_window]
            for attr, label in (("customer_id", "customer"), ("device_id", "device")):
                if attr in apps and isinstance(a.get(attr), str):
                    same = recent[recent[attr] == a[attr]]
                    if len(same) >= p2.get("count", 3):
                        out.append(_signal(cfg, "AP-02", a, f"{len(same)} applications from one {label} within "
                                                            f"{velocity_window.days} days", list(same["application_id"])))
                        break

        # ID-01: the application's phone/email differs from the applicant's profile AND is already used by others.
        if cfg.enabled("ID-01"):
            mine = profile.get(a["customer_id"], {})
            for attr in ("phone", "email"):
                value = a[f"_{attr}"]
                if not value or not mine.get(attr) or value == mine[attr]:
                    continue
                others_apps = prior[(prior[f"_{attr}"] == value) & (prior["customer_id"] != a["customer_id"])]
                others_profiles = [cid for cid, p in profile.items() if p.get(attr) == value and cid != a["customer_id"]]
                others = sorted(set(others_apps["customer_id"]) | set(others_profiles))
                if others:
                    out.append(_signal(cfg, "ID-01", a, f"Application {attr} {a[attr]} differs from the customer's "
                                                        f"profile and is also used by {', '.join(others)}",
                                       [a["application_id"], *others_apps["application_id"], *others]))
                    break

        # ID-02: the applicant's own profile shares a phone or mailbox with another customer under a different name,
        # after normalising formatting (+91/spaces, Gmail dots/+tags): identity stitching (F01). A shared surname and
        # address is treated as family. Only customers on file by the application's time are compared.
        me = people.get(a["customer_id"])
        if cfg.enabled("ID-02") and me:
            for attr in ("phone", "email"):
                if not me[attr]:
                    continue
                others = sorted(
                    cid for cid, o in people.items()
                    if cid != a["customer_id"] and o[attr] == me[attr] and o["name"] != me["name"]
                    and not (me["address"] and o["surname"] == me["surname"] and o["address"] == me["address"])
                    and (o["since"] is None or pd.isna(o["since"]) or o["since"] <= a["timestamp"]))
                if others:
                    out.append(_signal(cfg, "ID-02", a, f"The applicant's {attr} also belongs to {', '.join(others)} "
                                                        f"under a different name (after normalising its format)",
                                       [a["application_id"], a["customer_id"], *others]))
                    break
    return out
