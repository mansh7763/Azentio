"""Builds the golden dataset: hand-specified customers, one per evaluation case (Docs/EVALUATION.md).

Deterministic (no randomness). Run:  python tests/golden/build_golden.py
Writes customers/accounts/transactions/logins/applications CSVs and expected.yaml next to this file.
"""

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

OUT = Path(__file__).resolve().parent
BASE = datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc)

customers, accounts, txns, logins, apps = [], [], [], [], []


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def customer(cid, name, address, city, phone=None):
    customers.append({"customer_id": cid, "name": name, "address": address, "city": city,
                      "phone": phone or f"98{cid[1:]:0>8}", "email": f"{cid.lower()}@example.com",
                      "onboarding_date": "2024-01-15", "segment": "retail"})
    accounts.append({"account_id": f"A-{cid}", "customer_id": cid, "product": "savings",
                     "open_date": "2024-01-15", "status": "active", "balance": "5000000"})


def txn(tid, cid, when, amount, payee):
    txns.append({"txn_id": tid, "sender_account": f"A-{cid}", "timestamp": iso(when), "amount": str(amount),
                 "currency": "INR", "type": "transfer", "channel": "mobile", "beneficiary_account": payee,
                 "beneficiary_name": payee, "status": "success"})


def login(eid, cid, when, device, outcome="success", event_type="login", city=None):
    logins.append({"event_id": eid, "customer_id": cid, "timestamp": iso(when), "device_id": device,
                   "ip": f"10.0.{len(logins) % 250}.1", "city": city or "", "outcome": outcome,
                   "event_type": event_type})


def history_logins(cid, device, n=8, start=BASE):
    for i in range(n):
        login(f"L-{cid}-H{i}", cid, start + timedelta(days=20 * i, hours=1), device)


def monthly(cid, payee, amount, n=6, start=BASE, prefix="M"):
    for i in range(n):
        txn(f"T-{cid}-{prefix}{i}", cid, start + timedelta(days=30 * i), amount, payee)


def small_history(cid, payees, amounts, start=BASE):
    for i, amount in enumerate(amounts):
        txn(f"T-{cid}-S{i}", cid, start + timedelta(days=15 * i, hours=2), amount, payees[i % len(payees)])


D = datetime(2026, 10, 1, tzinfo=timezone.utc)  # "today" for the cases
expected = []

# LK-T1 / LK-T5 — regular high-value payer: same supplier, similar amount -> Low or no alert
customer("C001", "Arjun Mehta", "12 MG Road", "Bengaluru")
history_logins("C001", "DEV-C001")
monthly("C001", "SUP-1", 200000)
login("L-C001-NOW", "C001", D + timedelta(hours=9, minutes=50), "DEV-C001")
txn("T-C001-NEW", "C001", D + timedelta(hours=10), 210000, "SUP-1")
expected.append({"id": "LK-T5", "unit_type": "transaction", "entity": "T-C001-NEW", "max_band": "Low"})
# LK-T7 — the same payer's first months (thin history, compared with other customers) must not be Medium
for i in range(5):
    expected.append({"id": f"LK-T7-M{i}", "unit_type": "transaction", "entity": f"T-C001-M{i}", "max_band": "Low"})

# LK-T6 / LG-T1 — same profile, then account takeover: failures -> new device -> high-value transfer -> High
customer("C002", "Priya Nair", "4 Park Street", "Kolkata")
history_logins("C002", "DEV-C002")
monthly("C002", "SUP-1", 200000)
for i in range(6):
    login(f"L-C002-F{i}", "C002", D + timedelta(hours=2, minutes=i), "DEV-X", outcome="fail")
login("L-C002-OK", "C002", D + timedelta(hours=2, minutes=6), "DEV-X")
txn("T-C002-ATO", "C002", D + timedelta(hours=2, minutes=15), 210000, "SUP-1")
expected.append({"id": "LK-T6", "unit_type": "transaction", "entity": "T-C002-ATO", "band": "High",
                 "category": "account_takeover"})

# LG-T6 — forgot password: failures -> reset -> login from new phone, no money moved -> at most Medium
customer("C003", "Ravi Kumar", "9 Lake View", "Chennai")
history_logins("C003", "DEV-C003")
small_history("C003", ["BEN-3A"], [3000, 3200, 2900, 3100, 3000, 3050])
for i in range(6):
    login(f"L-C003-F{i}", "C003", D + timedelta(days=1, hours=8, minutes=i), "DEV-C003", outcome="fail")
login("L-C003-RESET", "C003", D + timedelta(days=1, hours=8, minutes=6), "DEV-C003", event_type="password_reset")
login("L-C003-OK", "C003", D + timedelta(days=1, hours=8, minutes=10), "DEV-C003-NEW")
expected.append({"id": "LG-T6", "unit_type": "login_burst", "customer": "C003", "max_band": "Medium",
                 "category": "account_takeover"})

# LG-T7 — large transfer BEFORE the failed logins -> no takeover chain on the transfer
customer("C004", "Sneha Iyer", "77 Hill Road", "Mumbai")
history_logins("C004", "DEV-C004")
small_history("C004", ["BEN-4A", "BEN-4B"], [3000, 5000, 4000, 4500, 3500, 3800])
txn("T-C004-BIG", "C004", D + timedelta(days=2, hours=10), 150000, "BEN-4A")
for i in range(6):
    login(f"L-C004-F{i}", "C004", D + timedelta(days=2, hours=10, minutes=30 + i), "DEV-Y", outcome="fail")
login("L-C004-OK", "C004", D + timedelta(days=2, hours=10, minutes=36), "DEV-Y")
expected.append({"id": "LG-T7", "unit_type": "transaction", "entity": "T-C004-BIG", "max_band": "Medium",
                 "no_chain": True})

# TX-T1 / TX-T5 / TX-T6 — small spender, then a large transfer to a new payee -> High
customer("C005", "Kabir Shah", "3 Ring Road", "Delhi")
history_logins("C005", "DEV-C005")
small_history("C005", ["BEN-5A", "BEN-5B", "BEN-5C"], [2000, 3500, 5000, 2500, 4000, 3000, 4500, 2200])
login("L-C005-NOW", "C005", D + timedelta(days=3, hours=11, minutes=50), "DEV-C005")
txn("T-C005-BIG", "C005", D + timedelta(days=3, hours=12), 150000, "BEN-NEW")
txn("T-C005-LATER", "C005", D + timedelta(days=4, hours=12), 4000, "BEN-NEW")
expected.append({"id": "TX-T1", "unit_type": "transaction", "entity": "T-C005-BIG", "band": "High",
                 "category": "suspicious_transfer"})

# TX-T2 — six transfers in 20 minutes to five new payees -> the last one High
customer("C006", "Meera Joshi", "21 Civil Lines", "Pune")
history_logins("C006", "DEV-C006")
small_history("C006", ["BEN-6A", "BEN-6B"], [2000, 3000, 4000, 2500, 3500, 3000])
for i, payee in enumerate(["BEN-6N1", "BEN-6N2", "BEN-6N3", "BEN-6N4", "BEN-6N5", "BEN-6N5"]):
    txn(f"T-C006-F{i}", "C006", D + timedelta(days=5, hours=14, minutes=4 * i), 20000, payee)
expected.append({"id": "TX-T2", "unit_type": "transaction", "entity": "T-C006-F5", "band": "High",
                 "category": "suspicious_transfer"})

# TX-T4 — fixed EMI (MAD = 0), same amount again -> no alert, no error
customer("C007", "Farhan Ali", "8 Station Road", "Hyderabad")
history_logins("C007", "DEV-C007")
monthly("C007", "BANK-EMI", 12000)
txn("T-C007-EMI", "C007", D + timedelta(hours=8), 12000, "BANK-EMI")
expected.append({"id": "TX-T4", "unit_type": "transaction", "entity": "T-C007-EMI", "no_alert": True})

# DV-T2 — household: three family members share one device -> Low (or no alert)
for cid, first in [("C008", "Rohit"), ("C009", "Anita"), ("C015", "Ishaan")]:
    customer(cid, f"{first} Sharma", "55 Rose Lane", "Jaipur")
    history_logins(cid, f"DEV-{cid}")
    for i in range(3):
        login(f"L-{cid}-HOME{i}", cid, D + timedelta(days=6, hours=8 + i), "DEV-HOME")
expected.append({"id": "DV-T2", "unit_type": "device_cluster", "entity": "DEV-HOME", "max_band": "Low"})

# DV-T1 / DV-T5 / AP-T1 — four unrelated customers on one device, loan applications sharing a phone -> High
ring = [("C010", "Vikram Rao", "1 Beach Road", "Goa"), ("C011", "Neha Gupta", "88 Mall Road", "Shimla"),
        ("C012", "Sanjay Das", "5 Fort Area", "Cuttack"), ("C013", "Lata Pillai", "19 Canal St", "Kochi")]
for n, (cid, name, address, city) in enumerate(ring):
    customer(cid, name, address, city)
    history_logins(cid, f"DEV-{cid}")
    for i in range(10):
        login(f"L-{cid}-RING{i}", cid, D + timedelta(days=7, hours=n, minutes=5 * i), "DEV-RING")
    apps.append({"application_id": f"APP-{cid}", "customer_id": cid, "product": "personal_loan",
                 "amount": "300000", "timestamp": iso(D + timedelta(days=7 + n % 3, hours=n, minutes=55)),
                 "device_id": "DEV-RING", "ip": "10.9.9.9", "phone": "9000000001",
                 "email": f"{cid.lower()}@example.com", "status": "submitted",
                 "disbursement_account": f"A-{cid}"})
    expected.append({"id": f"AP-T1-{cid}", "unit_type": "application", "entity": f"APP-{cid}", "band": "High",
                     "category": "loan_application_fraud"})
expected.append({"id": "DV-T1", "unit_type": "device_cluster", "entity": "DEV-RING", "band": "High",
                 "category": "shared_device", "one_alert_for": True})

# LG-T2 / LG-T8 — six failures, no success -> exactly one burst alert, at most Medium
customer("C014", "Gita Menon", "6 Temple St", "Madurai")
history_logins("C014", "DEV-C014")
for i in range(6):
    login(f"L-C014-F{i}", "C014", D + timedelta(days=8, hours=3, minutes=i), "DEV-C014", outcome="fail")
expected.append({"id": "LG-T8", "unit_type": "login_burst", "customer": "C014", "max_band": "Medium",
                 "one_alert_for": True})


def write(name, rows):
    with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    for name, rows in [("customers", customers), ("accounts", accounts), ("transactions", txns),
                       ("logins", logins), ("applications", apps)]:
        write(name, rows)
    with open(OUT / "expected.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(expected, f, sort_keys=False)
    print(f"golden: {len(customers)} customers, {len(txns)} txns, {len(logins)} logins, "
          f"{len(apps)} applications, {len(expected)} expectations")
