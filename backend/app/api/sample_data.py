# PLACEHOLDER - owner A replaces
"""Fixed sample objects the placeholder endpoints return, so C can build screens on realistic shapes."""

from datetime import datetime, timezone

from app.schemas import (
    Alert, AlertEntity, Band, Case, CaseDetail, CaseEvent, CaseStatus, Category, Contribution,
    DashboardSummary, DetectionRun, IngestReport, UnitType,
)

T0 = datetime(2026, 10, 1, 2, 10, tzinfo=timezone.utc)
RUN_ID = "RUN-sample"

ALERTS = [
    Alert(
        alert_id="ALT-1", detection_run_id=RUN_ID, dedupe_key="sample-1", unit_type=UnitType.transaction,
        primary_entity_id="T-9001", customer_id="C002", event_ids=["L-501", "L-506", "T-9001"],
        event_time=T0, created_at=T0, category=Category.account_takeover, product="savings",
        detection_types=["LG-02", "DV-03", "HV-01", "TX-03"], score=85, band=Band.high,
        contributions=[
            Contribution(indicator_id="LG-02", kind="risk", points=21, reason="6 failed logins in 5 min, then a successful login", evidence_ids=["L-501", "L-506"]),
            Contribution(indicator_id="DV-03", kind="risk", points=14, reason="Login from new device DEV-X", evidence_ids=["L-506"]),
            Contribution(indicator_id=None, kind="floor", points=50, reason="Account-takeover chain: failed logins → new device → ₹2,10,000 transfer within 12 min", evidence_ids=["L-501", "L-506", "T-9001"]),
        ],
        entities=[AlertEntity(entity_type="customer", entity_id="C002", role="primary"), AlertEntity(entity_type="device", entity_id="DEV-X")],
        evidence={"transactions": [{"txn_id": "T-9001", "amount": 210000, "beneficiary_account": "SUP-1"}]},
        narrative="Six failed logins were followed by a login from a new device and a ₹2,10,000 transfer 12 minutes later.",
        rules_version="sample",
    ),
    Alert(
        alert_id="ALT-2", detection_run_id=RUN_ID, dedupe_key="sample-2", unit_type=UnitType.device_cluster,
        primary_entity_id="DEV-RING", event_ids=["L-700", "L-701", "L-702"], event_time=T0, created_at=T0,
        category=Category.shared_device, detection_types=["DV-01", "DV-02"], score=62, band=Band.medium,
        contributions=[
            Contribution(indicator_id="DV-01", kind="risk", points=34, reason="Device DEV-RING used by 4 customers", evidence_ids=["L-700", "L-701", "L-702"]),
            Contribution(indicator_id="DV-02", kind="risk", points=28, reason="Customers share no surname or address", evidence_ids=["C010", "C011"]),
        ],
        entities=[AlertEntity(entity_type="device", entity_id="DEV-RING", role="primary")],
        narrative="One device is shared by four unrelated customers.",
        rules_version="sample",
    ),
    Alert(
        alert_id="ALT-3", detection_run_id=RUN_ID, dedupe_key="sample-3", unit_type=UnitType.transaction,
        primary_entity_id="T-1207", customer_id="C001", event_ids=["T-1207"], event_time=T0, created_at=T0,
        category=Category.suspicious_transfer, product="current", detection_types=["TX-02"], score=12, band=Band.low,
        contributions=[
            Contribution(indicator_id="TX-02", kind="risk", points=30, reason="₹2,10,000 is above the customer's usual maximum", evidence_ids=["T-1207"]),
            Contribution(indicator_id="MT-PAYEE", kind="mitigation", points=-18, reason="Regular payee: 6 similar payments to SUP-1 in 6 months", evidence_ids=["T-1201", "T-1202"]),
        ],
        entities=[AlertEntity(entity_type="customer", entity_id="C001", role="primary")],
        narrative="Large but regular payment to a known supplier.",
        rules_version="sample",
    ),
]

CASES = [
    Case(case_id="CASE-1", alert_ids=["ALT-1"], category=Category.account_takeover, customer_id="C002",
         account_id="A-002", score=85, band=Band.high, status=CaseStatus.new, created_at=T0, updated_at=T0),
    Case(case_id="CASE-2", alert_ids=["ALT-2"], category=Category.shared_device, score=62, band=Band.medium,
         status=CaseStatus.requires_investigation, created_at=T0, updated_at=T0),
]

CASE_EVENTS = {
    "CASE-2": [CaseEvent(case_id="CASE-2", at=T0, actor="analyst", from_status=CaseStatus.new,
                         to_status=CaseStatus.requires_investigation, note="Check the four customers' KYC")],
}

DASHBOARD = DashboardSummary(
    records_processed={"customers": 200, "accounts": 260, "transactions": 5000, "logins": 3000, "applications": 150},
    alerts_total=3,
    counts_by_band={"Low": 1, "Medium": 1, "High": 1},
    counts_by_category={"account_takeover": 1, "shared_device": 1, "suspicious_transfer": 1},
    counts_by_detection_type={"LG-02": 1, "DV-03": 1, "HV-01": 1, "TX-03": 1, "DV-01": 1, "DV-02": 1, "TX-02": 1},
    over_time=[{"date": "2026-10-01", "Low": 1, "Medium": 1, "High": 1}],
)

DETECTION_RUN = DetectionRun(
    run_id=RUN_ID, rules_version="sample", records_processed=DASHBOARD.records_processed,
    alerts_total=3, counts_by_band=DASHBOARD.counts_by_band, indicators_run=["TX-01", "LG-01", "DV-01"],
)


def ingest_report(file_name: str) -> IngestReport:
    return IngestReport(batch_id="BATCH-sample", file_name=file_name, entity_type="transactions", accepted=1,
                        mapping={"txn_id": "txn_id", "amount": "amount"})


def case_detail(case: Case) -> CaseDetail:
    alerts = [a for a in ALERTS if a.alert_id in case.alert_ids]
    return CaseDetail(**case.model_dump(), alerts=alerts, events=CASE_EVENTS.get(case.case_id, []))
