"""Canonical store tables. Every source row keeps its provenance beside the normalised values."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class IngestionBatch(Base):
    __tablename__ = "ingestion_batch"

    batch_id: Mapped[str] = mapped_column(String, primary_key=True)
    file_name: Mapped[str] = mapped_column(String)
    sheet: Mapped[str | None] = mapped_column(String)
    entity_type: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    accepted: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    conflicts: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    unmapped: Mapped[list] = mapped_column(JSON, default=list)


class RejectedRow(Base):
    __tablename__ = "rejected_row"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("ingestion_batch.batch_id"), index=True)
    row: Mapped[int] = mapped_column(Integer)
    raw: Mapped[dict] = mapped_column(JSON)
    reasons: Mapped[list] = mapped_column(JSON)


class Provenance:
    batch_id: Mapped[str] = mapped_column(String, index=True)
    source_file: Mapped[str] = mapped_column(String)
    source_row: Mapped[int] = mapped_column(Integer)
    raw: Mapped[dict] = mapped_column(JSON)


class CustomerRow(Provenance, Base):
    __tablename__ = "customer"

    customer_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
    dob: Mapped[str | None] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    address: Mapped[str | None] = mapped_column(String)
    city: Mapped[str | None] = mapped_column(String)
    onboarding_date: Mapped[datetime | None] = mapped_column(DateTime)
    segment: Mapped[str | None] = mapped_column(String)


class AccountRow(Provenance, Base):
    __tablename__ = "account"

    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(String, index=True)
    product: Mapped[str | None] = mapped_column(String)
    open_date: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str | None] = mapped_column(String)
    balance: Mapped[float | None] = mapped_column(Float)


class TransactionRow(Provenance, Base):
    __tablename__ = "transaction"

    txn_id: Mapped[str] = mapped_column(String, primary_key=True)
    sender_account: Mapped[str] = mapped_column(String, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String)
    type: Mapped[str | None] = mapped_column(String)
    channel: Mapped[str | None] = mapped_column(String)
    beneficiary_account: Mapped[str] = mapped_column(String)
    beneficiary_name: Mapped[str | None] = mapped_column(String)
    status: Mapped[str | None] = mapped_column(String)
    customer_id: Mapped[str | None] = mapped_column(String, index=True)
    device_id: Mapped[str | None] = mapped_column(String)
    ip: Mapped[str | None] = mapped_column(String)


class LoginRow(Provenance, Base):
    __tablename__ = "login_event"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(String, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    device_id: Mapped[str | None] = mapped_column(String)
    ip: Mapped[str | None] = mapped_column(String)
    city: Mapped[str | None] = mapped_column(String)
    country: Mapped[str | None] = mapped_column(String)
    outcome: Mapped[str] = mapped_column(String)
    event_type: Mapped[str | None] = mapped_column(String)


class ApplicationRow(Provenance, Base):
    __tablename__ = "application"

    application_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(String, index=True)
    product: Mapped[str | None] = mapped_column(String)
    amount: Mapped[float | None] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    device_id: Mapped[str | None] = mapped_column(String)
    ip: Mapped[str | None] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    status: Mapped[str | None] = mapped_column(String)
    disbursement_account: Mapped[str | None] = mapped_column(String)


class ClaimRow(Provenance, Base):
    __tablename__ = "claim"

    claim_id: Mapped[str] = mapped_column(String, primary_key=True)
    policy_id: Mapped[str] = mapped_column(String)
    customer_id: Mapped[str] = mapped_column(String, index=True)
    incident_date: Mapped[datetime] = mapped_column(DateTime)
    amount: Mapped[float] = mapped_column(Float)
    description: Mapped[str | None] = mapped_column(String)
    payout_account: Mapped[str | None] = mapped_column(String)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime)


# Keys match app.detect.dataset.TABLES, so stored tables become detection frames directly.
ENTITY_MODELS = {
    "customers": CustomerRow, "accounts": AccountRow, "transactions": TransactionRow,
    "logins": LoginRow, "applications": ApplicationRow, "claims": ClaimRow,
}
PROVENANCE_COLUMNS = ("batch_id", "source_file", "source_row", "raw")
