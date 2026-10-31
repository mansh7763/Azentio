"""Issue #6 Part B: boundaries of every threshold (B1), fraudster evasions (B3), data edge cases (B4) and
metamorphic properties (B5). Benign twins (B2) live next to each rule's own tests."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app.detect.config import load_rules
from app.detect.dataset import Dataset, prepare
from app.detect.engine import run_detection
from app.detect.indicators.applications import application_signals
from app.detect.indicators.logins import login_bursts, login_signals
from app.detect.indicators.transfers import hv_threshold, transfer_signals
from app.features.profiles import transaction_profiles
from app.score.scoring import band_for
from app.schemas import Band

T0 = datetime(2026, 3, 1, 9, tzinfo=timezone.utc)
CFG = load_rules()
ORDER = {Band.low: 0, Band.medium: 1, Band.high: 2}


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def person(cid, name=None, address=None):
    return {"customer_id": cid, "name": name or f"Person {cid}", "address": address or f"{cid} Street",
            "city": "Pune", "segment": "retail", "onboarding_date": "2025-01-01", "phone": f"98{cid[-1]}0000000"}


def tx(tid, cid, when, amount, payee, kind="transfer", status="success", currency="INR", **extra):
    return {"txn_id": tid, "sender_account": f"A-{cid}", "timestamp": when if isinstance(when, str) else iso(when),
            "amount": str(amount), "currency": currency, "type": kind, "status": status,
            "beneficiary_account": payee, **extra}


def login(eid, cid, when, device, outcome="success", event_type="login"):
    return {"event_id": eid, "customer_id": cid, "timestamp": iso(when), "device_id": device, "outcome": outcome,
            "event_type": event_type}


def frames(people, txns=(), logins=(), apps=None):
    out = {"customers": pd.DataFrame(people),
           "accounts": pd.DataFrame([{"account_id": f"A-{p['customer_id']}", "customer_id": p["customer_id"],
                                      "product": "savings"} for p in people])}
    if txns:
        out["transactions"] = pd.DataFrame(list(txns))
    if logins:
        out["logins"] = pd.DataFrame(list(logins))
    if apps:
        out["applications"] = pd.DataFrame(apps)
    return Dataset.from_frames(**out)


def prepared(ds):
    ds = prepare(ds, CFG)
    return ds, (transaction_profiles(ds, CFG) if ds.has("transactions") else None)


def ids(signals, indicator_id):
    return [s.entity_id for s in signals if s.indicator_id == indicator_id]


def steady(cid, n=6, amount=1000, payee="SHOP"):
    return [tx(f"{cid}-H{i}", cid, T0 + timedelta(days=7 * i), amount, payee) for i in range(n)]


def alert_for(result, entity):
    return next((a for a in result.alerts if a.primary_entity_id == entity), None)


# ============================== B1 — boundaries =============================================================

@pytest.mark.parametrize("amount,fires", [(1299, False), (1300, True)])
def test_tx01_z_boundary(amount, fires):
    """Six payments of 1,000: median 1,000, MAD 0, so the denominator is the floor of 100 and z = 3 at 1,300."""
    ds, prof = prepared(frames([person("C1")], steady("C1") + [tx("T", "C1", T0 + timedelta(days=60), amount, "SHOP")]))
    assert ("T" in ids(transfer_signals(ds, CFG, prof), "TX-01")) == fires


def test_tx01_needs_min_history_for_the_customers_own_baseline():
    ds, prof = prepared(frames([person("C1")], steady("C1", n=4) + [tx("T", "C1", T0 + timedelta(days=60), 9000, "SHOP")]))
    sig = [s for s in transfer_signals(ds, CFG, prof) if s.indicator_id == "TX-01" and s.entity_id == "T"]
    assert sig and "the customer's" not in sig[0].reason and sig[0].strength <= 0.5  # weaker population evidence


@pytest.mark.parametrize("gap_minutes,count,fires", [(5, 5, True), (5, 4, False), (5.0 + 1 / 240, 5, False)])
def test_tx04_velocity_boundary(gap_minutes, count, fires):
    """5 transfers within 20 minutes; the 5th exactly at 20:00 counts, at 20:01 does not."""
    burst = [tx(f"V{i}", "C1", T0 + timedelta(days=60, minutes=gap_minutes * i), 500, "SHOP") for i in range(count)]
    ds, prof = prepared(frames([person("C1")], steady("C1") + burst))
    assert bool(ids(transfer_signals(ds, CFG, prof), "TX-04")) == fires


@pytest.mark.parametrize("payees,fires", [(3, False), (4, True)])
def test_tx05_fan_out_boundary(payees, fires):
    fan = [tx(f"F{i}", "C1", T0 + timedelta(days=60, hours=5 * i), 900, f"NEW-{i}") for i in range(payees)]
    ds, prof = prepared(frames([person("C1")], steady("C1") + fan))
    assert bool(ids(transfer_signals(ds, CFG, prof), "TX-05")) == fires


@pytest.mark.parametrize("earlier,has_threshold", [(19, False), (20, True)])
def test_hv01_needs_min_samples(earlier, has_threshold):
    rows = [tx(f"S{i}", f"C{i % 3}", T0 + timedelta(hours=i), 1000 + i, "SHOP") for i in range(earlier)]
    rows.append(tx("LAST", "C0", T0 + timedelta(days=5), 5000, "SHOP"))
    ds, _ = prepared(frames([person(f"C{i}") for i in range(3)], rows))
    assert (hv_threshold(ds, CFG)["LAST"] is not None) == has_threshold


def _burst(n_fail, spread_minutes, success_after=None, device="DEV-NEW"):
    rows = [login(f"H{i}", "C1", T0 + timedelta(days=i), "DEV-OLD") for i in range(6)]
    start = T0 + timedelta(days=30)
    step = spread_minutes / max(1, n_fail - 1)
    rows += [login(f"F{i}", "C1", start + timedelta(minutes=step * i), device, outcome="fail") for i in range(n_fail)]
    if success_after is not None:
        rows.append(login("OK", "C1", start + timedelta(minutes=spread_minutes + success_after), device))
    ds, _ = prepared(frames([person("C1")], logins=rows))
    bursts = login_bursts(ds, CFG)
    return bursts, login_signals(ds, CFG, bursts)


@pytest.mark.parametrize("n_fail,spread,fires", [(5, 10, True), (4, 3, False), (5, 10 + 1 / 60, False)])
def test_lg01_burst_boundary(n_fail, spread, fires):
    bursts, _ = _burst(n_fail, spread)
    assert bool(bursts) == fires


@pytest.mark.parametrize("after,fires", [(30, True), (31, False)])
def test_lg02_success_window_boundary(after, fires):
    _, signals = _burst(5, 8, success_after=after)
    assert bool(ids(signals, "LG-02")) == fires


@pytest.mark.parametrize("minutes_after_success,chain", [(30, True), (31, False)])
def test_takeover_chain_window_boundary(minutes_after_success, chain):
    """Failed logins -> success on a new device -> payment to a new payee: a chain only within 30 minutes."""
    logins = [login(f"H{i}", "C1", T0 + timedelta(days=i), "DEV-OLD") for i in range(6)]
    start = T0 + timedelta(days=60)
    logins += [login(f"F{i}", "C1", start + timedelta(minutes=i), "DEV-NEW", outcome="fail") for i in range(5)]
    logins.append(login("OK", "C1", start + timedelta(minutes=6), "DEV-NEW"))
    pay = tx("PAY", "C1", start + timedelta(minutes=6 + minutes_after_success), 1000, "NEW-PAYEE")
    result = run_detection(frames([person("C1")], steady("C1") + [pay], logins))
    alert = alert_for(result, "PAY")
    assert (alert is not None and any(d.startswith("CHAIN:ato") for d in alert.detection_types)) == chain


def _ring(n, last_hours=50):
    """n unrelated applicants on one device sharing a phone; the last applies `last_hours` after the first."""
    hours = [0] + [last_hours * (i + 1) / max(1, n - 1) for i in range(n - 1)]
    apps = [{"application_id": f"APP{i}", "customer_id": f"C{i}", "product": "personal_loan", "amount": "100000",
             "timestamp": iso(T0 + timedelta(hours=h)), "device_id": "DEV-R", "phone": "9000000001",
             "disbursement_account": f"A-C{i}"} for i, h in enumerate(hours)]
    ds, _ = prepared(frames([person(f"C{i}") for i in range(n)], apps=apps))
    return ids(application_signals(ds, CFG), "AP-01")


def test_ap01_applicant_and_window_boundaries():
    assert _ring(3) == ["APP2"]
    assert _ring(2) == []
    assert _ring(3, last_hours=72) == ["APP2"]
    assert _ring(3, last_hours=72 + 1 / 3600) == []


@pytest.mark.parametrize("moved,hours,fires", [(0.70, 47, True), (0.699, 47, False), (0.70, 48 + 1 / 3600, False)])
def test_ap03_share_and_window_boundary(moved, hours, fires):
    app = [{"application_id": "APP1", "customer_id": "C1", "product": "personal_loan", "amount": "100000",
            "timestamp": iso(T0), "disbursement_account": "A-C1"}]
    disb = tx("DISB", "BANK", T0 + timedelta(hours=1), 100000, "A-C1", kind="loan_disbursement")
    out = tx("OUT", "C1", T0 + timedelta(hours=1 + hours), round(100000 * moved, 2), "MULE-NEW")
    result = run_detection(frames([person("C1")], steady("C1") + [disb, out], apps=app))
    alert = alert_for(result, "OUT")
    assert (alert is not None and "AP-03" in alert.detection_types) == fires


@pytest.mark.parametrize("score,band", [(39, Band.low), (40, Band.medium), (69, Band.medium), (70, Band.high)])
def test_band_boundaries(score, band):
    assert band_for(score, CFG) == band


def test_equal_timestamps_are_ordered_by_id_deterministically():
    same = iso(T0 + timedelta(days=60))
    rows = steady("C1") + [tx("B", "C1", same, 5000, "NEW-1"), tx("A", "C1", same, 5000, "NEW-2")]
    one = run_detection(frames([person("C1")], rows))
    two = run_detection(frames([person("C1")], list(reversed(rows))))
    assert [(a.primary_entity_id, a.score) for a in one.alerts] == [(a.primary_entity_id, a.score) for a in two.alerts]


# ============================== B3 — evasions ===============================================================
# Each evasion must still reach at least Medium through another rule, or be listed in KNOWN_GAPS with its reason.

KNOWN_GAPS = {
    "loan-to-mule split across the 48h window": (
        "AP-03 needs 70% within 48h of the disbursement; moving 65% inside and the rest just after evades it. "
        "TX-06 needs 5 earlier windows of history, which a freshly funded mule account rarely has."),
}

HIST = [3000, 7000, 4000, 6000, 5000, 3500, 6500, 4500, 5500, 5000]


def varied(cid):
    return [tx(f"{cid}-H{i}", cid, T0 + timedelta(days=7 * i), a, f"SHOP-{i % 3}") for i, a in enumerate(HIST)]


def worst(result, entities):
    found = [a for a in result.alerts if a.primary_entity_id in entities]
    return max((ORDER[a.band] for a in found), default=-1)


def test_evasion_split_large_transfer_below_the_line():
    when = T0 + timedelta(days=80)
    split = [tx(f"S{i}", "C1", when + timedelta(hours=2 * i), 8000, f"NEW-{i}") for i in range(4)]
    result = run_detection(frames([person("C1")], varied("C1") + split))
    assert worst(result, {f"S{i}" for i in range(4)}) >= ORDER[Band.medium]


def test_evasion_slowed_velocity_still_caught_by_fan_out():
    """4 transfers every 20+ minutes all day to new payees: TX-04 is evaded, TX-05 / TX-06 are not."""
    when = T0 + timedelta(days=80)
    slow = [tx(f"V{i}", "C1", when + timedelta(minutes=25 * i), 4000, f"NEW-{i}") for i in range(8)]
    result = run_detection(frames([person("C1")], varied("C1") + slow))
    assert worst(result, {f"V{i}" for i in range(8)}) >= ORDER[Band.medium]


def test_evasion_takeover_waits_past_the_chain_window():
    """Waiting 35 minutes defeats the 30-minute chain, but the login burst and the payment stay reviewable."""
    logins = [login(f"H{i}", "C1", T0 + timedelta(days=i), "DEV-OLD") for i in range(6)]
    start = T0 + timedelta(days=80)
    logins += [login(f"F{i}", "C1", start + timedelta(minutes=i), "DEV-NEW", outcome="fail") for i in range(5)]
    logins.append(login("OK", "C1", start + timedelta(minutes=6), "DEV-NEW"))
    pay = tx("PAY", "C1", start + timedelta(minutes=41), 60000, "NEW-PAYEE")
    result = run_detection(frames([person("C1")], varied("C1") + [pay], logins))
    assert ORDER[alert_for(result, "PAY").band] >= ORDER[Band.medium]
    burst = [a for a in result.alerts if a.unit_type.value == "login_burst"]
    assert burst and ORDER[burst[0].band] >= ORDER[Band.medium]


def test_evasion_loan_swarm_on_different_devices_sharing_one_payout():
    """Each applicant uses their own device, but all loans pay out to one account: AP-04 catches the payout."""
    apps = [{"application_id": f"APP{i}", "customer_id": f"C{i}", "product": "personal_loan", "amount": "100000",
             "timestamp": iso(T0 + timedelta(hours=5 * i)), "device_id": f"DEV-{i}", "phone": f"9{i}00000000",
             "disbursement_account": "MULE-PAYOUT"} for i in range(3)]
    result = run_detection(frames([person(f"C{i}") for i in range(3)], apps=apps))
    assert worst(result, {"APP2"}) >= ORDER[Band.medium]
    family = [person(f"C{i}", f"Kiran{i} Sharma", "55 Rose Lane") for i in range(3)]
    assert worst(run_detection(frames(family, apps=apps)), {"APP2"}) < ORDER[Band.medium]  # one household's joint account


def test_known_gaps_are_documented():
    """A known gap is acceptable; a hidden one is not. This keeps the list visible in test output."""
    assert all(reason for reason in KNOWN_GAPS.values())


# ============================== B4 — data edge cases ========================================================

def test_unresolved_customer_is_counted_not_guessed():
    rows = steady("C1") + [{**tx("ORPHAN", "C1", T0 + timedelta(days=60), 90000, "NEW"), "sender_account": "A-UNKNOWN"}]
    result = run_detection(frames([person("C1")], rows))
    assert result.run.coverage["unresolved_link"] == 1


def test_other_currency_is_never_judged_against_an_inr_baseline():
    ds, prof = prepared(frames([person("C1")], steady("C1") + [tx("USD", "C1", T0 + timedelta(days=60), 1300, "SHOP", currency="USD")]))
    assert "USD" not in ids(transfer_signals(ds, CFG, prof), "TX-01")


def test_timezone_offsets_give_identical_results():
    utc = steady("C1") + [tx("T", "C1", "2026-05-10T04:30:00Z", 9000, "NEW")]
    ist = steady("C1") + [tx("T", "C1", "2026-05-10T10:00:00+05:30", 9000, "NEW")]
    a, b = run_detection(frames([person("C1")], utc)), run_detection(frames([person("C1")], ist))
    assert [(x.primary_entity_id, x.score) for x in a.alerts] == [(x.primary_entity_id, x.score) for x in b.alerts]


def test_incoming_credits_never_score_as_outgoing_risk():
    credit = {**tx("SALARY", "EMPLOYER", T0 + timedelta(days=60), 900000, "A-C1", kind="salary_credit")}
    result = run_detection(frames([person("C1")], steady("C1") + [credit]))
    assert alert_for(result, "SALARY") is None


def test_failed_transfers_never_enter_baselines():
    failed = tx("FAIL", "C1", T0 + timedelta(days=50), 1000000, "SHOP", status="failed")
    ds, prof = prepared(frames([person("C1")], steady("C1") + [failed, tx("T", "C1", T0 + timedelta(days=60), 1300, "SHOP")]))
    assert prof.loc["T", "prior_median"] == 1000 and "T" in ids(transfer_signals(ds, CFG, prof), "TX-01")


def test_duplicate_rows_do_not_double_alert_or_crash():
    rows = steady("C1") + [tx("DUP", "C1", T0 + timedelta(days=60), 90000, "NEW")] * 2
    result = run_detection(frames([person("C1")], rows))
    assert [a.primary_entity_id for a in result.alerts].count("DUP") == 1
    assert result.run.coverage["duplicate_ids_dropped"] == 1


def test_non_ascii_names_and_huge_amounts_explain_cleanly():
    people = [person("C1", "Ä́nanyā Ōmkār", "9 गली")]
    result = run_detection(frames(people, steady("C1") + [tx("BIG", "C1", T0 + timedelta(days=60), 9.5e12, "NEW")]))
    alert = alert_for(result, "BIG")
    assert alert and "9,500,000,000,000" in alert.narrative


# ============================== B5 — metamorphic properties =================================================

def _scores(result):
    return sorted((a.unit_type.value, a.score, a.band.value) for a in result.alerts)


def test_adding_an_unrelated_quiet_customer_changes_nothing(raw_golden):
    base = run_detection(raw_golden)
    frames_ = {k: v.copy() for k, v in raw_golden.frames.items()}
    frames_["customers"] = pd.concat([frames_["customers"], pd.DataFrame([person("C999")])], ignore_index=True)
    assert _scores(run_detection(Dataset(frames_))) == _scores(base)


def test_renaming_ids_consistently_keeps_every_score(raw_golden):
    """Prefixing every identifier keeps their order, so ties break the same way and every score must match."""
    id_cols = ("customer_id", "account_id", "txn_id", "event_id", "application_id", "sender_account",
               "beneficiary_account", "disbursement_account", "device_id")
    renamed = {}
    for name, df in raw_golden.frames.items():
        df = df.copy()
        for col in id_cols:
            if col in df:
                df[col] = df[col].map(lambda v: f"Z{v}" if isinstance(v, str) and v else v)
        renamed[name] = df
    assert _scores(run_detection(Dataset(renamed))) == _scores(run_detection(raw_golden))


def test_scaling_all_money_by_ten_keeps_every_score(raw_golden):
    """Rules compare amounts with the customer's own amounts, so a currency redenomination changes nothing
    (the absolute floor is scaled with it)."""
    scaled = {}
    for name, df in raw_golden.frames.items():
        df = df.copy()
        for col in ("amount", "balance"):
            if col in df:
                df[col] = df[col].map(lambda v: str(float(v) * 10) if v not in (None, "") else v)
        scaled[name] = df
    floor = load_rules().floor_amount * 10
    assert _scores(run_detection(Dataset(scaled), overrides={"floor_amount": floor})) == _scores(run_detection(raw_golden))
