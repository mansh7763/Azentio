"""Labelled synthetic bank for evaluation (issue #5 Part 2, Docs/EVALUATION.md D2/D3).

A normal population plus planted incidents. Every incident is labelled `fraud` or `lookalike` (legitimate behaviour
that resembles fraud) and records exactly which entities it created, so each alert can be attributed. Fraud strength
is drawn from realistic ranges, including values on the wrong side of a rule's threshold, so recall below 100% is
expected and informative. Seeds: 2 = D2 (tuning), 3 = D3 (held out; report only).

    python evals/generate.py --seed 3 --out evals/data/d3     # optional: write CSVs + labels.json
"""

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
FIRST = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Isha", "Vivaan", "Anaya", "Arjun", "Saanvi", "Reyansh", "Myra",
         "Vihaan", "Kiara", "Aditya", "Zara", "Krishna", "Riya", "Ishaan", "Tara", "Neel", "Pari", "Dev", "Avni"]
LAST = ["Sharma", "Iyer", "Khan", "Das", "Reddy", "Patel", "Nair", "Gupta", "Bose", "Menon", "Singh", "Rao",
        "Joshi", "Chopra", "Kapoor", "Pillai", "Verma", "Mehta", "Banerjee", "Kulkarni", "Fernandes", "Ghosh"]
CITIES = ["Mumbai", "Pune", "Delhi", "Bengaluru", "Chennai", "Kochi", "Jaipur", "Kolkata", "Hyderabad", "Surat"]


@dataclass
class Incident:
    id: str
    scenario: str
    kind: str                      # "fraud" | "lookalike"
    customers: list[str]
    planted: set[str] = field(default_factory=set)   # ids the incident is judged on
    setup: set[str] = field(default_factory=set)     # ids it needed as history (e.g. earlier rent); never background
    start: datetime | None = None
    end: datetime | None = None
    new_customer: bool = False


class Bank:
    def __init__(self, seed: int):
        self.rng = np.random.default_rng(seed)
        self.seed = seed
        self.customers, self.accounts, self.txns, self.logins, self.apps = [], [], [], [], []
        self.incidents: list[Incident] = []
        self.n = {"c": 0, "t": 0, "l": 0, "a": 0}
        self.profile: dict[str, dict] = {}

    # --- primitives --------------------------------------------------------------------------------------------
    def _id(self, kind, prefix):
        self.n[kind] += 1
        return f"{prefix}{self.seed}-{self.n[kind]:05d}"

    def day(self, d, hours=0.0):
        return BASE + timedelta(days=float(d), hours=float(hours))

    def customer(self, segment="retail", surname=None, address=None, phone=None, onboard_day=-400, name=None):
        cid = self._id("c", "C")
        first, last = self.rng.choice(FIRST), surname or self.rng.choice(LAST)
        address = address or f"{int(self.rng.integers(1, 300))} {self.rng.choice(['MG Road', 'Park St', 'Lake View', 'Hill Rd', 'Station Rd'])}"
        phone = phone or f"9{int(self.rng.integers(100000000, 999999999))}"
        self.customers.append({"customer_id": cid, "name": name or f"{first} {last}", "dob": "1990-01-01",
                               "phone": phone, "email": f"{cid.lower()}@example.com", "address": address,
                               "city": str(self.rng.choice(CITIES)), "segment": segment,
                               "onboarding_date": self.day(onboard_day).isoformat()})
        self.accounts.append({"account_id": f"A-{cid}", "customer_id": cid, "product": "current" if segment == "business" else "savings",
                              "open_date": self.day(onboard_day).isoformat(), "status": "active", "balance": "500000"})
        self.profile[cid] = {"device": f"D-{cid}", "payees": [], "median": 0.0, "spread": 0.0}
        return cid

    def txn(self, cid, when, amount, payee, kind="transfer", status="success", sender=None, **extra):
        tid = self._id("t", "T")
        self.txns.append({"txn_id": tid, "sender_account": sender or f"A-{cid}", "timestamp": when.isoformat(),
                          "amount": f"{amount:.2f}", "currency": "INR", "type": kind, "channel": "mobile",
                          "beneficiary_account": payee, "beneficiary_name": payee, "status": status, **extra})
        return tid

    def login(self, cid, when, device=None, outcome="success", event_type="login", ip=None):
        lid = self._id("l", "L")
        self.logins.append({"event_id": lid, "customer_id": cid, "timestamp": when.isoformat(),
                            "device_id": device or self.profile[cid]["device"], "ip": ip or f"10.{self.seed}.{len(self.logins) % 250}.1",
                            "city": "", "outcome": outcome, "event_type": event_type})
        return lid

    def application(self, cid, when, device=None, phone=None, payout=None, amount=300000, ip=None):
        aid = self._id("a", "APP")
        me = next(c for c in self.customers if c["customer_id"] == cid)
        self.apps.append({"application_id": aid, "customer_id": cid, "product": "personal_loan", "amount": str(amount),
                          "timestamp": when.isoformat(), "device_id": device or self.profile[cid]["device"],
                          "ip": ip or f"10.{self.seed}.200.{int(self.rng.integers(1, 250))}", "phone": phone or me["phone"],
                          "email": me["email"], "status": "submitted", "disbursement_account": payout or f"A-{cid}"})
        return aid

    def incident(self, scenario, kind, customers, new_customer=False):
        inc = Incident(f"{scenario}-{len(self.incidents)}", scenario, kind, list(customers), new_customer=new_customer)
        self.incidents.append(inc)
        return inc

    # --- normal life ---------------------------------------------------------------------------------------------
    def life(self, cid, start=0, end=270, business=False):
        """Monthly bills and salary, weekly shopping with noise, logins before payments on the usual device."""
        p = self.profile[cid]
        median = float(self.rng.lognormal(8.3, 0.5))           # typical payment ~4,000 with wide spread
        p["median"], p["spread"] = median, median * 0.35
        bills = [f"BILL-{cid}-{i}" for i in range(int(self.rng.integers(2, 4)))]
        shops = [f"SHOP-{int(self.rng.integers(1, 40))}" for _ in range(int(self.rng.integers(3, 6)))]
        p["payees"] = bills + shops
        for m in range(int(start // 30), int(end // 30)):
            self.txn(cid, self.day(30 * m + 1, 10), median * 8, f"A-{cid}", kind="salary_credit", sender="EMPLOYER")
            for i, b in enumerate(bills):
                self.txn(cid, self.day(30 * m + 3 + i, 9), median * (1.5 + 0.2 * i), b)
        d = start + float(self.rng.uniform(0, 5))
        while d < end:
            when = self.day(d, float(self.rng.uniform(8, 21)))
            self.login(cid, when - timedelta(minutes=2))
            if self.rng.random() < 0.03:
                self.login(cid, when - timedelta(minutes=4), outcome="fail")   # an ordinary typo
            amount = max(100.0, float(self.rng.normal(median, p["spread"])))
            self.txn(cid, when, amount, str(self.rng.choice(shops)))
            d += float(self.rng.exponential(5 if not business else 2))

    # --- fraud scenarios -----------------------------------------------------------------------------------------
    def burst(self, cid, when, device, n=None, spread=None):
        n = n or int(self.rng.integers(5, 9))
        spread = spread if spread is not None else float(self.rng.uniform(2, 9))
        return [self.login(cid, when + timedelta(minutes=spread * i / (n - 1)), device, outcome="fail") for i in range(n)]

    def ato(self, cid, d):
        inc = self.incident("account_takeover", "fraud", [cid])
        start = self.day(d, 2)
        ids = self.burst(cid, start, "D-ATTACKER")
        ok = start + timedelta(minutes=12)
        ids.append(self.login(cid, ok, "D-ATTACKER"))
        delay = float(self.rng.uniform(3, 45))           # past 30 min the chain no longer applies
        amount = self.profile[cid]["median"] * float(self.rng.uniform(4, 15))
        ids.append(self.txn(cid, ok + timedelta(minutes=delay), amount, f"MULE-{inc.id}"))
        inc.planted, inc.start, inc.end = set(ids), start, ok + timedelta(minutes=delay)

    def ato_no_money(self, cid, d):
        inc = self.incident("takeover_attempt", "fraud", [cid])
        start = self.day(d, 3)
        ids = self.burst(cid, start, "D-ATTACKER2")
        ok = start + timedelta(minutes=10)
        ids += [self.login(cid, ok, "D-ATTACKER2"), self.login(cid, ok + timedelta(minutes=3), "D-ATTACKER2", event_type="beneficiary_add")]
        inc.planted, inc.start, inc.end = set(ids), start, ok

    def scam(self, cid, d):
        inc = self.incident("scam_payment", "fraud", [cid])
        when = self.day(d, 15)
        self.login(cid, when - timedelta(minutes=3))
        tid = self.txn(cid, when, self.profile[cid]["median"] * float(self.rng.uniform(2.5, 20)), f"SCAM-{inc.id}")
        inc.planted, inc.start, inc.end = {tid}, when, when

    def dispersal(self, cid, d, new=False):
        inc = self.incident("mule_dispersal", "fraud", [cid], new_customer=new)
        when = self.day(d, 11)
        total = float(self.rng.uniform(150000, 600000))
        ids = [self.txn(cid, when, total, f"A-{cid}", kind="credit", sender=f"VICTIM-{inc.id}")]
        n = int(self.rng.integers(5, 9))
        gap = float(self.rng.uniform(2, 9))
        ids += [self.txn(cid, when + timedelta(minutes=10 + gap * i), total / n * 0.97, f"OUT-{inc.id}-{i}") for i in range(n)]
        inc.planted, inc.start, inc.end = set(ids), when, when + timedelta(minutes=10 + gap * n)

    def structuring(self, cid, d):
        inc = self.incident("structuring", "fraud", [cid])
        p = self.profile[cid]
        z = float(self.rng.uniform(1.2, 3.0))
        ids = [self.txn(cid, self.day(d, 9 + 3 * i), p["median"] + z * max(1.4826 * p["spread"] * 0.67, 0.1 * p["median"]),
                        f"SPLIT-{inc.id}-{i}") for i in range(int(self.rng.integers(3, 5)))]
        inc.planted, inc.start, inc.end = set(ids), self.day(d, 9), self.day(d, 21)

    def drain(self, cid, d):
        inc = self.incident("slow_drain", "fraud", [cid])
        n, days = int(self.rng.integers(5, 10)), float(self.rng.uniform(2, 6))
        ids = [self.txn(cid, self.day(d + days * i / n, 13), self.profile[cid]["median"] * float(self.rng.uniform(1.0, 1.8)),
                        f"DRAIN-{inc.id}-{i % 3}") for i in range(n)]
        inc.planted, inc.start, inc.end = set(ids), self.day(d), self.day(d + days)

    def dormant(self):
        cid = self.customer()
        self.life(cid, 0, 110)
        inc = self.incident("dormant_awakening", "fraud", [cid])
        d = 110 + float(self.rng.uniform(95, 140))
        ids = [self.txn(cid, self.day(d, 10 + 2 * i), self.profile[cid]["median"] * float(self.rng.uniform(1, 6)), f"WAKE-{inc.id}-{i}")
               for i in range(int(self.rng.integers(1, 4)))]
        inc.planted, inc.start, inc.end = set(ids), self.day(d), self.day(d, 16)

    def device_ring(self, d, new=True):
        members = [self.customer(onboard_day=d - 20 if new else -400) for _ in range(int(self.rng.integers(3, 6)))]
        inc = self.incident("device_ring", "fraud", members, new_customer=new)
        device, phone = f"D-RING-{len(self.incidents)}", f"9{int(self.rng.integers(100000000, 999999999))}"
        ids = {device}
        for i, cid in enumerate(members):
            when = self.day(d + float(self.rng.uniform(0, 2)), 10 + i)
            ids.add(self.login(cid, when, device))
            ids.add(self.application(cid, when + timedelta(minutes=30), device=device, phone=phone))
        inc.planted, inc.start, inc.end = ids, self.day(d), self.day(d + 3)

    def payout_swarm(self, d):
        members = [self.customer(onboard_day=d - 30) for _ in range(int(self.rng.integers(3, 5)))]
        inc = self.incident("payout_swarm", "fraud", members, new_customer=True)
        payout = f"MULE-PAYOUT-{len(self.incidents)}"
        ids = {self.application(cid, self.day(d + float(self.rng.uniform(0, 5)), 10), payout=payout) for cid in members}
        inc.planted, inc.start, inc.end = ids, self.day(d), self.day(d + 6)

    def loan_mule(self, cid, d):
        inc = self.incident("loan_to_mule", "fraud", [cid])
        amount = float(self.rng.uniform(100000, 500000))
        aid = self.application(cid, self.day(d, 10), amount=amount)
        disb = self.txn(cid, self.day(d + 2, 10), amount, f"A-{cid}", kind="loan_disbursement", sender="BANK-LOANS", application_id=aid)
        share, hours = float(self.rng.uniform(0.6, 0.95)), float(self.rng.uniform(2, 60))   # some under 70% or past 48h
        n = int(self.rng.integers(2, 5))
        ids = {aid, disb} | {self.txn(cid, self.day(d + 2, 10 + hours * (i + 1) / n), amount * share / n, f"CASHOUT-{inc.id}-{i}")
                             for i in range(n)}
        inc.planted, inc.start, inc.end = ids, self.day(d), self.day(d + 2, 10 + hours)

    def convergence(self, payers, d):
        inc = self.incident("recipient_convergence", "fraud", payers)
        mule, hours = f"MULE-CONV-{len(self.incidents)}", float(self.rng.uniform(4, 70))
        ids = {self.txn(cid, self.day(d, 9 + hours * i / len(payers)), float(self.rng.uniform(20000, 90000)), mule)
               for i, cid in enumerate(payers)}
        inc.planted, inc.start, inc.end = ids, self.day(d), self.day(d, 9 + hours)

    def circular(self, members, d):
        inc = self.incident("circular_flow", "fraud", members)
        amount, hours = float(self.rng.uniform(50000, 300000)), float(self.rng.uniform(3, 60))
        ids = set()
        for i, cid in enumerate(members):
            nxt = members[(i + 1) % len(members)]
            ids.add(self.txn(cid, self.day(d, 8 + hours * i / len(members)), amount * (1 - 0.02 * i), f"A-{nxt}"))
        inc.planted, inc.start, inc.end = ids, self.day(d), self.day(d, 8 + hours)

    def identity_reuse(self, victim, d):
        phone = next(c["phone"] for c in self.customers if c["customer_id"] == victim)
        cid = self.customer(phone=f"+91 {phone[:5]} {phone[5:]}", onboard_day=d - 10)
        inc = self.incident("identity_reuse", "fraud", [cid], new_customer=True)
        inc.planted, inc.start, inc.end = {self.application(cid, self.day(d, 12))}, self.day(d), self.day(d)

    # --- legitimate lookalikes -----------------------------------------------------------------------------------
    def big_regular(self, cid, d):
        inc = self.incident("regular_large_payment", "lookalike", [cid])
        rent = self.profile[cid]["median"] * float(self.rng.uniform(6, 15))
        inc.setup = {self.txn(cid, self.day(d - 30 * k, 9), rent, f"LANDLORD-{cid}") for k in range(6, 0, -1)}
        last = self.txn(cid, self.day(d, 9), rent, f"LANDLORD-{cid}")
        inc.planted, inc.start, inc.end = {last}, self.day(d), self.day(d)

    def payroll(self, d0=0):
        cid = self.customer(segment="business")
        self.life(cid, 0, 270, business=True)
        inc = self.incident("business_payroll", "lookalike", [cid])
        staff = [f"EMP-{cid}-{i}" for i in range(int(self.rng.integers(5, 11)))]
        months = {}
        for m in range(int(d0 // 30), 9):
            months[m] = {self.txn(cid, self.day(30 * m + 28, 10) + timedelta(minutes=2 * i), float(self.rng.uniform(25000, 40000)), e)
                         for i, e in enumerate(staff)}
        # Judged once established (month 4 on). The first months are the payroll's own cold start: setup here,
        # measured separately as cold start rather than counted as a lookalike failure.
        inc.planted = set().union(*(v for m, v in months.items() if m >= 3))
        inc.setup = set().union(*(v for m, v in months.items() if m < 3))
        inc.start, inc.end = self.day(90), self.day(270)

    def household(self, d):
        surname, address = self.rng.choice(LAST), "55 Rose Lane"
        members = [self.customer(surname=surname, address=address) for _ in range(3)]
        for cid in members:
            self.life(cid, 0, 270)
        inc = self.incident("household_device", "lookalike", members)
        device = f"D-HOME-{len(self.incidents)}"
        ids = {device} | {self.login(cid, self.day(d + i, 20), device) for i, cid in enumerate(members)}
        inc.planted, inc.start, inc.end = ids, self.day(d), self.day(d + 3)

    def forgot_password(self, cid, d):
        inc = self.incident("forgot_password", "lookalike", [cid])
        start = self.day(d, 8)
        ids = self.burst(cid, start, self.profile[cid]["device"])
        ok = start + timedelta(minutes=10)
        ids.append(self.login(cid, ok))
        ids.append(self.txn(cid, ok + timedelta(minutes=5), self.profile[cid]["median"], self.profile[cid]["payees"][-1]))
        inc.planted, inc.start, inc.end = set(ids), start, ok

    def new_phone(self, cid, d):
        inc = self.incident("new_phone", "lookalike", [cid])
        when = self.day(d, 18)
        ids = {self.login(cid, when, f"D-{cid}-NEW"), self.txn(cid, when + timedelta(minutes=4), self.profile[cid]["median"], self.profile[cid]["payees"][0])}
        self.profile[cid]["device"] = f"D-{cid}-NEW"
        inc.planted, inc.start, inc.end = ids, when, when

    def shopping_spree(self, cid, d):
        inc = self.incident("shopping_spree", "lookalike", [cid])
        when = self.day(d, 17)
        shops = self.profile[cid]["payees"][-3:]
        ids = {self.txn(cid, when + timedelta(minutes=3 * i), self.profile[cid]["median"] * float(self.rng.uniform(0.5, 1.5)), shops[i % len(shops)])
               for i in range(int(self.rng.integers(4, 7)))}
        inc.planted, inc.start, inc.end = ids, when, when + timedelta(minutes=20)

    def merchant(self, d):
        merchant = f"MERCHANT-{len(self.incidents)}"
        regulars = [c["customer_id"] for c in self.rng.choice(self.customers[:60], 8, replace=False)]
        setup = {self.txn(cid, self.day(10 + 12 * i, 12), float(self.rng.uniform(500, 3000)), merchant) for i, cid in enumerate(regulars)}
        newcomers = [c["customer_id"] for c in self.rng.choice(self.customers[60:120], 3, replace=False)]
        inc = self.incident("merchant_collection", "lookalike", newcomers)
        inc.setup = setup
        ids = {self.txn(cid, self.day(d, 10 + 5 * i), float(self.rng.uniform(800, 4000)), merchant) for i, cid in enumerate(newcomers)}
        inc.planted, inc.start, inc.end = ids, self.day(d), self.day(d, 25)

    def own_sweep(self, d):
        cid = self.customer(segment="business")
        self.life(cid, 0, 270, business=True)
        extra = [f"A-{cid}-B", f"A-{cid}-C"]
        self.accounts += [{"account_id": a, "customer_id": cid, "product": "current", "open_date": "2025-01-01",
                           "status": "active", "balance": "0"} for a in extra]
        inc = self.incident("own_account_sweep", "lookalike", [cid])
        chain = [f"A-{cid}"] + extra + [f"A-{cid}"]
        ids = {self.txn(cid, self.day(d, 9 + 2 * i), 200000, chain[i + 1], sender=chain[i]) for i in range(3)}
        inc.planted, inc.start, inc.end = ids, self.day(d), self.day(d, 15)

    def family_landline(self, d):
        # Each independent household owns its own landline. Reusing one literal phone across
        # all planted households accidentally creates the identity-reuse pattern under test.
        surname, address, phone = self.rng.choice(LAST), "8 Temple Rd", f"9800{len(self.incidents):06d}"
        members = [self.customer(surname=surname, address=address, phone=phone) for _ in range(2)]
        inc = self.incident("family_landline", "lookalike", members)
        inc.planted, inc.start, inc.end = {self.application(members[1], self.day(d, 11))}, self.day(d), self.day(d)

    def colleagues(self, d):
        members = [self.customer() for _ in range(3)]
        inc = self.incident("office_colleagues", "lookalike", members)
        ids = {self.application(cid, self.day(d, 10 + i), ip="10.50.0.1") for i, cid in enumerate(members)}
        inc.planted, inc.start, inc.end = ids, self.day(d), self.day(d, 13)

    def seasonal(self):
        cid = self.customer()
        self.life(cid, 0, 110)
        inc = self.incident("seasonal_return", "lookalike", [cid])
        d = 110 + float(self.rng.uniform(95, 140))
        ids = {self.txn(cid, self.day(d, 10), self.profile[cid]["median"], self.profile[cid]["payees"][0])}
        inc.planted, inc.start, inc.end = ids, self.day(d), self.day(d)

    def loan_supplier(self, cid, d):
        inc = self.incident("loan_paid_to_supplier", "lookalike", [cid])
        supplier = f"SUPPLIER-{cid}"
        inc.setup = {self.txn(cid, self.day(d - 60 + 12 * k, 11), 20000, supplier) for k in range(4)}
        amount = 200000.0
        aid = self.application(cid, self.day(d, 10), amount=amount)
        disb = self.txn(cid, self.day(d + 2, 10), amount, f"A-{cid}", kind="loan_disbursement", sender="BANK-LOANS", application_id=aid)
        pay = self.txn(cid, self.day(d + 2, 15), amount * 0.85, supplier)
        inc.planted, inc.start, inc.end = {aid, disb, pay}, self.day(d), self.day(d + 2, 15)

    # --- assemble -----------------------------------------------------------------------------------------------
    def build(self, population=160, per_scenario=4):
        normal = [self.customer() for _ in range(population)]
        for cid in normal:
            self.life(cid)
        pick = iter(self.rng.permutation(normal))
        late = lambda: float(self.rng.uniform(190, 255))  # noqa: E731
        for _ in range(per_scenario):
            self.ato(next(pick), late()); self.ato_no_money(next(pick), late()); self.scam(next(pick), late())
            self.dispersal(next(pick), late()); self.structuring(next(pick), late()); self.drain(next(pick), late())
            self.dormant(); self.device_ring(late()); self.payout_swarm(late()); self.loan_mule(next(pick), late())
            self.convergence([next(pick) for _ in range(int(self.rng.integers(3, 6)))], late())
            self.circular([next(pick) for _ in range(int(self.rng.integers(3, 5)))], late())
            self.identity_reuse(next(pick), late())
            fresh = self.customer(onboard_day=200)                   # cold start: fraud on a brand-new account
            self.dispersal(fresh, late(), new=True)
            self.big_regular(next(pick), late()); self.payroll(); self.household(late())
            self.forgot_password(next(pick), late()); self.new_phone(next(pick), late())
            self.shopping_spree(next(pick), late()); self.merchant(late()); self.own_sweep(late())
            self.family_landline(late()); self.colleagues(late()); self.seasonal(); self.loan_supplier(next(pick), late())
        return self

    def frames(self) -> dict[str, pd.DataFrame]:
        return {"customers": pd.DataFrame(self.customers), "accounts": pd.DataFrame(self.accounts),
                "transactions": pd.DataFrame(self.txns), "logins": pd.DataFrame(self.logins),
                "applications": pd.DataFrame(self.apps)}


def generate(seed: int, population: int = 160, per_scenario: int = 4) -> Bank:
    return Bank(seed).build(population, per_scenario)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    bank = generate(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, df in bank.frames().items():
        df.to_csv(args.out / f"{name}.csv", index=False)
    (args.out / "labels.json").write_text(json.dumps([{**i.__dict__, "planted": sorted(i.planted),
                                                       "start": i.start.isoformat() if i.start else None,
                                                       "end": i.end.isoformat() if i.end else None}
                                                      for i in bank.incidents], indent=1), encoding="utf-8")
    print(f"seed {args.seed}: {sum(len(df) for df in bank.frames().values())} rows, {len(bank.incidents)} incidents")
