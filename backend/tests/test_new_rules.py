"""Issue #6 Part A: TX-06, TX-07, TX-08, NW-01, NW-02, ID-02. Each rule has a case that fires, a benign twin that
must not, and its boundaries. Small in-memory datasets, so every test states its own facts."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app.detect.config import load_rules
from app.detect.dataset import Dataset, prepare
from app.detect.engine import run_detection
from app.detect.indicators.applications import application_signals
from app.detect.indicators.flows import cumulative_signals, dormancy_signals, structuring_signals
from app.detect.indicators.network import circular_signals, convergence_signals
from app.features.profiles import transaction_profiles
from app.schemas import Category

T0 = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)
CFG = load_rules()


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def person(cid, name=None, address=None, **extra):
    return {"customer_id": cid, "name": name or f"Person {cid}", "address": address or f"{cid} Street",
            "city": "Pune", "segment": "retail", "onboarding_date": "2025-01-01", **extra}


def tx(tid, cid, when, amount, payee, kind="transfer", sender=None):
    return {"txn_id": tid, "sender_account": sender or f"A-{cid}", "timestamp": iso(when), "amount": str(amount),
            "currency": "INR", "type": kind, "status": "success", "beneficiary_account": payee}


def world(people, txns=(), apps=None, accounts=None):
    frames = {"customers": pd.DataFrame(people),
              "accounts": pd.DataFrame(accounts or [{"account_id": f"A-{p['customer_id']}",
                                                     "customer_id": p["customer_id"], "product": "savings"} for p in people])}
    if txns:
        frames["transactions"] = pd.DataFrame(list(txns))
    if apps is not None:
        frames["applications"] = pd.DataFrame(apps)
    ds = prepare(Dataset.from_frames(**frames), CFG)
    return ds, (transaction_profiles(ds, CFG) if txns else None)


def fired(signals, indicator_id):
    return [s for s in signals if s.indicator_id == indicator_id]


HISTORY = [3000, 7000, 4000, 6000, 5000, 3500, 6500, 4500, 5500, 5000]  # median 5000, real spread


def history(cid, payee="SHOP", start=T0):
    return [tx(f"{cid}-H{i}", cid, start + timedelta(days=7 * i), a, f"{payee}-{i % 3}") for i, a in enumerate(HISTORY)]


# --- TX-06 cumulative outflow (F10 slow drain) -----------------------------------------------------------------

def test_tx06_many_modest_payments_add_up():
    when = T0 + timedelta(days=80)
    drain = [tx(f"D{i}", "C1", when + timedelta(hours=3 * i), 6000, f"NEW-{i}") for i in range(4)]
    ds, prof = world([person("C1")], history("C1") + drain)
    sig = fired(cumulative_signals(ds, CFG, prof), "TX-06")
    assert sig and sig[-1].entity_id == "D3"
    assert "4 payments within 24h" in sig[-1].reason and set(sig[-1].evidence_ids) == {"D0", "D1", "D2", "D3"}


def test_tx06_benign_instalments_to_an_established_payee():
    when = T0 + timedelta(days=80)
    school = [tx(f"S{i}", "C1", T0 + timedelta(days=7 * i, hours=1), 6000, "SCHOOL") for i in range(4)]
    fees = [tx(f"F{i}", "C1", when + timedelta(hours=3 * i), 6000, "SCHOOL") for i in range(4)]
    ds, prof = world([person("C1")], history("C1") + school + fees)
    assert fired(cumulative_signals(ds, CFG, prof), "TX-06") == []


def test_tx06_needs_a_clear_margin_and_enough_history():
    when = T0 + timedelta(days=80)
    pair = [tx(f"P{i}", "C1", when + timedelta(hours=i), 4000, f"NEW-{i}") for i in range(2)]  # 8000 < 1.5 x ~6800
    ds, prof = world([person("C1")], history("C1") + pair)
    assert fired(cumulative_signals(ds, CFG, prof), "TX-06") == []
    short = history("C1")[:3] + [tx(f"Q{i}", "C1", when + timedelta(hours=i), 9000, f"NEW-{i}") for i in range(3)]
    ds, prof = world([person("C1")], short)
    assert fired(cumulative_signals(ds, CFG, prof), "TX-06") == []  # < min_windows earlier windows


# --- TX-07 structuring ---------------------------------------------------------------------------------------

def test_tx07_unusually_high_payments_kept_just_below_the_line():
    when = T0 + timedelta(days=80)
    split = [tx(f"S{i}", "C1", when + timedelta(hours=2 * i), 8000, f"NEW-{i}") for i in range(3)]
    ds, prof = world([person("C1")], history("C1") + split)
    assert fired(structuring_signals(ds, CFG, prof), "TX-07")[-1].entity_id == "S2"
    tx01 = [s.entity_id for s in fired(prepare_and_run_tx01(ds, prof), "TX-01")]
    assert not {"S0", "S1", "S2"} & set(tx01)  # each split payment stays under the single-payment rule


def prepare_and_run_tx01(ds, prof):
    from app.detect.indicators.transfers import transfer_signals
    return transfer_signals(ds, CFG, prof)


def test_tx07_steady_payer_near_own_trigger_is_not_structuring():
    """Payroll twin: equal payments sit ~77% of a low-spread customer's trigger, but are not unusual (z = 0)."""
    steady = [tx(f"H{i}", "C1", T0 + timedelta(days=30 * i), 5000, f"EMP-{i % 5}") for i in range(10)]
    month = [tx(f"M{i}", "C1", T0 + timedelta(days=301, minutes=i), 5000, f"NEWEMP-{i}") for i in range(3)]
    ds, prof = world([person("C1")], steady + month)
    assert fired(structuring_signals(ds, CFG, prof), "TX-07") == []


def test_tx07_two_payments_or_a_wider_window_do_not_count():
    when = T0 + timedelta(days=80)
    ds, prof = world([person("C1")], history("C1") + [tx(f"S{i}", "C1", when + timedelta(hours=i), 8000, f"N{i}") for i in range(2)])
    assert fired(structuring_signals(ds, CFG, prof), "TX-07") == []
    spread = [tx(f"W{i}", "C1", when + timedelta(hours=13 * i), 8000, f"N{i}") for i in range(3)]  # 26h apart
    ds, prof = world([person("C1")], history("C1") + spread)
    assert fired(structuring_signals(ds, CFG, prof), "TX-07") == []


# --- TX-08 dormant account awakening (F09) ------------------------------------------------------------------

def _dormant(gap_days, first_payee="NEW-X", start_offset=0):
    early = [tx(f"E{i}", "C1", T0 + timedelta(days=start_offset + 30 * i), 5000, "RENT") for i in range(5)]
    last = T0 + timedelta(days=start_offset + 120)
    wake = [tx("W0", "C1", last + timedelta(days=gap_days), 5000, first_payee),
            tx("W1", "C1", last + timedelta(days=gap_days, hours=5), 9000, "NEW-Y")]
    return world([person("C1")], early + wake)


def test_tx08_dormant_account_pays_new_payees():
    ds, prof = _dormant(100)
    sig = fired(dormancy_signals(ds, CFG, prof), "TX-08")
    assert [s.entity_id for s in sig] == ["W0", "W1"] and "100 days with no outgoing payments" in sig[0].reason


def test_tx08_boundaries_and_benign_twin():
    ds, prof = _dormant(89)
    assert fired(dormancy_signals(ds, CFG, prof), "TX-08") == []           # gap below 90 days
    ds, prof = _dormant(100, first_payee="RENT")
    assert [s.entity_id for s in fired(dormancy_signals(ds, CFG, prof), "TX-08")] == ["W1"]  # known payee: not W0


def test_tx08_short_file_cannot_establish_dormancy():
    txns = [tx("E0", "C1", T0, 5000, "RENT"), tx("W0", "C1", T0 + timedelta(days=100), 5000, "NEW-X")]
    ds, prof = world([person("C1")], txns)
    assert fired(dormancy_signals(ds, CFG, prof), "TX-08") == []           # 100 days observed < 180


# --- NW-01 recipient convergence (F05) ----------------------------------------------------------------------

PAYERS = [person("C1", "Asha Rao", "1 A St"), person("C2", "Ben Das", "2 B St"), person("C3", "Chen Li", "3 C St")]


def _converge(spacing_hours=10, people=PAYERS, earlier=(), extra=()):
    txns = [tx(f"P{i}", p["customer_id"], T0 + timedelta(days=60, hours=spacing_hours * i), 20000, "MULE-1")
            for i, p in enumerate(people)]
    return world(people, list(earlier) + txns + list(extra))


def test_nw01_unrelated_customers_converge_on_a_new_recipient():
    ds, prof = _converge()
    sig = fired(convergence_signals(ds, CFG, prof), "NW-01")
    assert [s.entity_id for s in sig] == ["P2"] and sig[0].strength == 0.7
    assert sig[0].category == Category.suspicious_transfer


def test_nw01_stronger_when_payers_were_just_funded_by_a_loan():
    loan = [tx("LOAN-1", "C2", T0 + timedelta(days=59), 300000, "A-C2", kind="loan_disbursement", sender="BANK")]
    ds, prof = _converge(extra=loan)
    sig = fired(convergence_signals(ds, CFG, prof), "NW-01")[0]
    assert sig.strength == 1.0 and sig.category == Category.loan_application_fraud and "LOAN-1" in sig.evidence_ids


def test_nw01_merchant_household_and_boundaries():
    # Three regular customers paid this account weeks earlier (spread out, so they are not a convergence themselves).
    regulars = [tx(f"R{i}", f"C{i + 4}", T0 + timedelta(days=10 * i), 500, "MULE-1") for i in range(3)]
    shoppers = PAYERS + [person(f"C{i + 4}") for i in range(3)]
    ds, prof = world(shoppers, regulars + [tx(f"P{i}", p["customer_id"], T0 + timedelta(days=60, hours=10 * i), 20000, "MULE-1")
                                           for i, p in enumerate(PAYERS)])
    assert fired(convergence_signals(ds, CFG, prof), "NW-01") == []       # established collection account
    family = [person(f"F{i}", f"Kiran{i} Sharma", "55 Rose Lane") for i in range(3)]
    ds, prof = _converge(people=family)
    assert fired(convergence_signals(ds, CFG, prof), "NW-01") == []       # one household paying, e.g., a landlord
    ds, prof = _converge(people=PAYERS[:2])
    assert fired(convergence_signals(ds, CFG, prof), "NW-01") == []       # two payers
    ds, prof = _converge(spacing_hours=36.001)
    assert fired(convergence_signals(ds, CFG, prof), "NW-01") == []       # third payer just outside 72h


# --- NW-02 circular flow (F11) -------------------------------------------------------------------------------

def _cycle(amounts=(10000, 9800, 9700), hours=(0, 4, 9), owners=("C1", "C2", "C3"), close=True):
    accts = [{"account_id": f"ACC{i}", "customer_id": o, "product": "current"} for i, o in enumerate(owners)]
    people = [person(o) for o in sorted(set(owners))]
    hops = [("ACC0", "ACC1"), ("ACC1", "ACC2"), ("ACC2", "ACC0" if close else "OUTSIDE")]
    txns = [tx(f"H{i}", None, T0 + timedelta(hours=h), a, dst, sender=src)
            for i, ((src, dst), a, h) in enumerate(zip(hops, amounts, hours))]
    return world(people, txns, accounts=accts)


def test_nw02_money_returns_through_three_accounts():
    ds, _ = _cycle()
    sig = fired(circular_signals(ds, CFG), "NW-02")
    assert [s.entity_id for s in sig] == ["H2"] and sig[0].evidence_ids == ["H0", "H1", "H2"]
    assert "ACC0" in sig[0].reason


def test_nw02_benign_and_boundaries():
    assert fired(circular_signals(_cycle(owners=("C1", "C1", "C1"))[0], CFG), "NW-02") == []   # own-account sweep
    assert fired(circular_signals(_cycle(amounts=(10000, 8000, 7900))[0], CFG), "NW-02") == []  # hop drifts 20%
    assert fired(circular_signals(_cycle(hours=(0, 40, 73))[0], CFG), "NW-02") == []          # beyond 72h
    assert fired(circular_signals(_cycle(close=False)[0], CFG), "NW-02") == []                # never returns
    accts = [{"account_id": "ACC0", "customer_id": "C1"}, {"account_id": "ACC1", "customer_id": "C2"}]
    refund = [tx("R0", None, T0, 5000, "ACC1", sender="ACC0"), tx("R1", None, T0 + timedelta(hours=2), 5000, "ACC0", sender="ACC1")]
    ds, _ = world([person("C1"), person("C2")], refund, accounts=accts)
    assert fired(circular_signals(ds, CFG), "NW-02") == []                                     # A -> B -> A is a refund


# --- ID-02 normalised identity reuse (F01) ------------------------------------------------------------------

def _apply(applicant, other):
    app = [{"application_id": "APP-1", "customer_id": applicant["customer_id"], "product": "personal_loan",
            "amount": "100000", "timestamp": iso(T0 + timedelta(days=30))}]
    ds, _ = world([applicant, other], apps=app)
    return fired(application_signals(ds, CFG), "ID-02")


@pytest.mark.parametrize("mine,theirs", [
    ({"phone": "+91 98000 11111"}, {"phone": "9800011111"}),
    ({"email": "Ravi.Kumar+loans@gmail.com"}, {"email": "ravikumar@googlemail.com"}),
])
def test_id02_same_contact_under_another_name_after_normalising(mine, theirs):
    sig = _apply(person("C1", "Ravi Kumar", **mine), person("C9", "Sunil Mehta", **theirs))
    assert sig and "C9" in sig[0].evidence_ids


def test_id02_family_and_point_in_time():
    family = _apply(person("C1", "Ravi Sharma", "55 Rose Lane", phone="9800011111"),
                    person("C2", "Meena Sharma", "55 Rose Lane", phone="9800011111"))
    assert family == []                                                    # shared family landline
    later = _apply(person("C1", "Ravi Kumar", phone="9800011111"),
                   person("C9", "Sunil Mehta", phone="9800011111", onboarding_date="2026-06-01"))
    assert later == []                                                     # not on file at application time


# --- engine contract for every new rule --------------------------------------------------------------------

def test_new_rules_cannot_reach_high_alone_and_cite_existing_evidence():
    when = T0 + timedelta(days=80)
    drain = [tx(f"D{i}", "C1", when + timedelta(hours=3 * i), 6000, f"NEW-{i}") for i in range(4)]
    ds = Dataset.from_frames(customers=pd.DataFrame([person("C1")]),
                             accounts=pd.DataFrame([{"account_id": "A-C1", "customer_id": "C1", "product": "savings"}]),
                             transactions=pd.DataFrame(history("C1") + drain))
    result = run_detection(ds)
    alert = next(a for a in result.alerts if a.primary_entity_id == "D3")
    assert "TX-06" in alert.detection_types and alert.band.value != "High"
    known = {v for rows in alert.evidence.values() for row in rows for v in row.values() if isinstance(v, str)}
    assert all(set(c.evidence_ids) <= known for c in alert.contributions)


def test_tx06_does_not_reflag_one_large_payment_on_the_payments_after_it():
    """Golden C005: a 150,000 transfer is TX-01's alert; the ordinary 4,000 next day must not inherit it."""
    when = T0 + timedelta(days=80)
    after = [tx("BIG", "C1", when, 150000, "NEW-1"), tx("LATER", "C1", when + timedelta(days=1), 4000, "NEW-1")]
    ds, prof = world([person("C1")], history("C1") + after)
    assert fired(cumulative_signals(ds, CFG, prof), "TX-06") == []


def test_tx07_split_payments_cannot_raise_their_own_bar():
    """Structured payments enter the baseline; judged against the level before the window, all three still count."""
    when = T0 + timedelta(days=80)
    split = [tx(f"S{i}", "C1", when + timedelta(hours=2 * i), 8000, f"NEW-{i}") for i in range(3)]
    ds, prof = world([person("C1")], history("C1") + split)
    assert set(fired(structuring_signals(ds, CFG, prof), "TX-07")[-1].evidence_ids) == {"S0", "S1", "S2"}
