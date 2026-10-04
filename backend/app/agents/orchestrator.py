"""The entry point for a chat message: route it, then hand it to the right agent."""

from sqlalchemy.orm import Session

from app.agents.llm import LLMClient
from app.agents.query_agent import answer_query
from app.agents.router import route
from app.agents.types import AgentResult
from app.agents.update_agent import propose_update
from app.domain.errors import ValidationError

MAX_MESSAGE_CHARS = 1000

OUT_OF_SCOPE_ANSWER = (
    "I can only help with the requirements, test cases and risk items in this database. "
    "Try: 'Show me REQ-001', 'Which requirements have no test cases?' or "
    "'Set REQ-007 status to implemented'."
)


def handle_message(session: Session, llm: LLMClient, message: str) -> AgentResult:
    text = (message or "").strip()
    if not text:
        raise ValidationError("the message must not be empty")
    if len(text) > MAX_MESSAGE_CHARS:
        raise ValidationError(f"the message must be at most {MAX_MESSAGE_CHARS} characters")

    decision = route(llm, text)

    if decision.intent == "refused":
        return AgentResult(f"I can't do that: {decision.reason}.", "refused", refused=True)
    if decision.intent == "out_of_scope":
        return AgentResult(OUT_OF_SCOPE_ANSWER, "out_of_scope", refused=True)
    if decision.intent == "update":
        return propose_update(llm, session, text)
    return answer_query(llm, session, text)
