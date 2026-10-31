"""Saved Pattern Scout suggestions and analyst decisions on them. Approving a suggestion records the decision only;
it never changes rules or scores."""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base


class SuggestionRow(Base):
    __tablename__ = "agent_suggestion"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    hypothesis: Mapped[str] = mapped_column(String)
    suggested_rule: Mapped[str] = mapped_column(String)
    entities: Mapped[list] = mapped_column(JSON)
    evidence_ids: Mapped[list] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String)          # "ai" when the LLM wrote the text, else "rules"
    status: Mapped[str] = mapped_column(String, default="suggested")
    decided_by: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_note: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


FIELDS = ("id", "kind", "title", "hypothesis", "suggested_rule", "entities", "evidence_ids", "source", "status",
          "decided_by", "decision_note", "decided_at", "created_at")


def as_dict(row: SuggestionRow) -> dict:
    out = {f: getattr(row, f) for f in FIELDS}
    for f in ("decided_at", "created_at"):
        out[f] = out[f].isoformat() if out[f] else None
    return out


def save_suggestions(session: Session, suggestions: list[dict]) -> list[dict]:
    """Insert new suggestions; refresh the text of existing ones but keep their analyst decision."""
    out = []
    for s in suggestions:
        row = session.get(SuggestionRow, s["id"])
        if row is None:
            row = SuggestionRow(id=s["id"], created_at=datetime.now(timezone.utc), status="suggested")
            session.add(row)
        for f in ("kind", "title", "hypothesis", "suggested_rule", "entities", "evidence_ids", "source"):
            setattr(row, f, s[f])
        out.append(row)
    session.commit()
    return [as_dict(r) for r in out]


def list_suggestions(session: Session) -> list[dict]:
    return [as_dict(r) for r in session.query(SuggestionRow).order_by(SuggestionRow.created_at, SuggestionRow.id)]


def decide(session: Session, suggestion_id: str, decision: str, actor: str, note: str | None) -> dict | None:
    row = session.get(SuggestionRow, suggestion_id)
    if row is None:
        return None
    row.status = {"approve": "approved", "dismiss": "dismissed"}[decision]
    row.decided_by, row.decision_note, row.decided_at = actor, note, datetime.now(timezone.utc)
    session.commit()
    return as_dict(row)
