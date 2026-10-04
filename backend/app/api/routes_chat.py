"""POST /chat: ask a question or request a change in plain English."""

from dataclasses import asdict

from fastapi import APIRouter

from app.agents.orchestrator import handle_message
from app.api.deps import ERRORS, LLMDep, SessionDep
from app.api.schemas import ChatIn, ChatOut

router = APIRouter(tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatOut,
    responses={422: ERRORS[422], 503: ERRORS[503]},
)
def chat(body: ChatIn, session: SessionDep, llm: LLMDep):
    """Ask in plain English. Answers come only from the database; changes are proposals."""
    return asdict(handle_message(session, llm, body.message))
