"""Shared shapes for all workstreams. Change with a heads-up in chat (see Docs/OWNERSHIP.md)."""

from datetime import datetime
from enum import Enum
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# --- Enums -------------------------------------------------------------------

class Band(str, Enum):
    low = "Low"
    medium = "Medium"
    high = "High"


class Category(str, Enum):
    suspicious_transfer = "suspicious_transfer"
    account_takeover = "account_takeover"
    shared_device = "shared_device"
    loan_application_fraud = "loan_application_fraud"
    duplicate_claim = "duplicate_claim"


class UnitType(str, Enum):
    transaction = "transaction"
    login_burst = "login_burst"
    device_cluster = "device_cluster"
    application = "application"


class Direction(str, Enum):
    risk = "risk"
    mitigating = "mitigating"


class CaseStatus(str, Enum):
    new = "New"
    requires_investigation = "Requires Investigation"
    awaiting_information = "Awaiting Information"
    false_positive = "False Positive"
    escalated = "Escalated"
    confirmed_fraud = "Confirmed Fraud"
    closed = "Closed"


# --- Canonical records (output of ingestion, input to detection) --------------

class Customer(BaseModel):
    customer_id: str
    name: str | None = None
    dob: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    city: str | None = None
    onboarding_date: datetime | None = None
    segment: str | None = None


class Account(BaseModel):
    account_id: str
    customer_id: str
    product: str | None = None
    open_date: datetime | None = None
    status: str | None = None
    balance: float | None = None


class Transaction(BaseModel):
    txn_id: str
    sender_account: str
    timestamp: datetime
    amount: float
    currency: str | None = None
    type: str | None = None
    channel: str | None = None
    beneficiary_account: str
    beneficiary_name: str | None = None
    status: str | None = None
    customer_id: str | None = None
    device_id: str | None = None
    ip: str | None = None
    application_id: str | None = None  # explicit loan link, when a transaction is a disbursement


class LoginEvent(BaseModel):
    event_id: str | None = None
    customer_id: str
    timestamp: datetime
    device_id: str | None = None
    ip: str | None = None
    city: str | None = None
    country: str | None = None
    outcome: str
    event_type: str | None = None  # login | password_reset | beneficiary_add | profile_change | device_change


class Application(BaseModel):
    application_id: str
    customer_id: str
    product: str | None = None
    amount: float | None = None
    timestamp: datetime
    device_id: str | None = None
    ip: str | None = None
    phone: str | None = None
    email: str | None = None
    status: str | None = None
    disbursement_account: str | None = None


class Claim(BaseModel):
    claim_id: str
    policy_id: str
    customer_id: str
    incident_date: datetime
    amount: float
    description: str | None = None
    payout_account: str | None = None
    timestamp: datetime | None = None


# --- Detection output ---------------------------------------------------------

class Signal(BaseModel):
    indicator_id: str
    entity_id: str
    customer_id: str | None = None
    event_ids: list[str] = Field(default_factory=list)
    event_time: datetime
    strength: float = 1.0
    weight: float = 0.0
    direction: Direction = Direction.risk
    category: Category | None = None
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)


class Contribution(BaseModel):
    indicator_id: str | None = None
    kind: Literal["risk", "mitigation", "floor"]
    points: int
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)


class AlertEntity(BaseModel):
    entity_type: str
    entity_id: str
    role: Literal["primary", "linked"] = "linked"


class Alert(BaseModel):
    alert_id: str
    detection_run_id: str
    dedupe_key: str
    unit_type: UnitType
    primary_entity_id: str
    customer_id: str | None = None
    event_ids: list[str]
    event_time: datetime
    created_at: datetime
    category: Category
    product: str | None = None
    detection_types: list[str]
    score: int
    band: Band
    contributions: list[Contribution]
    entities: list[AlertEntity] = Field(default_factory=list)
    evidence: dict[str, list[dict]] = Field(default_factory=dict)
    narrative: str = ""
    rules_version: str


class DetectionRun(BaseModel):
    run_id: str
    rules_version: str
    records_processed: dict[str, int] = Field(default_factory=dict)
    alerts_total: int = 0
    counts_by_band: dict[str, int] = Field(default_factory=dict)
    indicators_run: list[str] = Field(default_factory=list)
    indicators_skipped: dict[str, str] = Field(default_factory=dict)
    # Kept separate from risk (revision 4): evaluated_units, insufficient_history, unresolved_link, derived_device_link
    coverage: dict[str, int] = Field(default_factory=dict)


class DetectionResponse(BaseModel):
    run: DetectionRun
    alerts: list[Alert]


# --- Cases ----------------------------------------------------------------------

class Case(BaseModel):
    case_id: str
    alert_ids: list[str]
    category: Category
    customer_id: str | None = None
    account_id: str | None = None
    score: int
    band: Band
    status: CaseStatus = CaseStatus.new
    assignee: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    grouping_reason: str = ""
    system_band: Band | None = None  # the detector's classification; `band` shows an analyst's correction
    priority: int = 0
    exposure_by_currency: dict[str, float] = Field(default_factory=dict)
    evidence_strength: str = "weak"  # how many independent facts support the case; not a probability
    needs_review: bool = False
    priority_factors: list[str] = Field(default_factory=list)


class CaseEvent(BaseModel):
    id: int | None = None
    type: Literal["decision", "action", "ai_assessment", "note", "correction", "system"] = "decision"
    detail: dict = Field(default_factory=dict)
    case_id: str
    at: datetime
    actor: str
    from_status: CaseStatus | None = None
    to_status: CaseStatus
    note: str | None = None


class CaseDecision(BaseModel):
    status: CaseStatus
    note: str | None = None
    actor: str = "analyst"


class CaseAction(BaseModel):
    action: Literal["confirm", "false_positive", "request_info", "escalate", "recommend_hold",
                    "recommend_verification", "conclude", "reclassify"]
    note: str
    actor: str = "analyst"
    band: Band | None = None  # reclassify: the new band
    outcome: Literal["Confirmed Fraud", "Closed"] | None = None  # conclude: defaults to Closed


class CaseSplit(BaseModel):
    alert_ids: list[str]
    reason: str
    actor: str = "analyst"


class CaseEventCreate(BaseModel):
    type: Literal["ai_assessment", "note", "correction"]
    note: str
    actor: str = "analyst"
    detail: dict = Field(default_factory=dict)


class CaseDetail(Case):
    alerts: list[Alert] = Field(default_factory=list)
    events: list[CaseEvent] = Field(default_factory=list)


# --- API wrappers -----------------------------------------------------------------

class IngestReport(BaseModel):
    batch_id: str
    file_name: str
    entity_type: str | None = None
    accepted: int = 0
    rejected: int = 0
    skipped: int = 0
    conflicts: int = 0
    errors: list[dict] = Field(default_factory=list)
    mapping: dict[str, str] = Field(default_factory=dict)
    unmapped: list[str] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    records_processed: dict[str, int] = Field(default_factory=dict)
    alerts_total: int = 0
    counts_by_band: dict[str, int] = Field(default_factory=dict)
    counts_by_category: dict[str, int] = Field(default_factory=dict)
    counts_by_detection_type: dict[str, int] = Field(default_factory=dict)
    over_time: list[dict] = Field(default_factory=list)
    indicators_skipped: dict[str, str] = Field(default_factory=dict)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
