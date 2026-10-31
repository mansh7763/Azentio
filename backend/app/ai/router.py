"""Level 2 AI endpoints (workstream C): Ask FinShield and reviewer memory."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.assistant import answer, reviewer_memory
from app.db import get_session

router = APIRouter(tags=["assistant"])


class AssistantRequest(BaseModel):
    question: str
    screen: dict = Field(default_factory=dict)


@router.post("/assistant")
def ask(body: AssistantRequest, session: Session = Depends(get_session)):
    if not body.question.strip():
        raise HTTPException(422, "Ask a question about what is on screen.")
    return answer(session, body.question.strip(), body.screen)


@router.get("/assistant/memory")
def memory(case_id: str | None = None, entity_id: str | None = None, session: Session = Depends(get_session)):
    """What earlier reviewers found on this case and on cases sharing its customer or account."""
    return {"items": reviewer_memory(session, case_id, {entity_id} if entity_id else set())}
