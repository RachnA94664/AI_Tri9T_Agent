"""Query Agent: answers questions about the data. Read-only."""

from sqlalchemy.orm import Session

from app.agents.grounding import ungrounded_ids
from app.agents.llm import LLMClient
from app.agents.prompt_loader import load_prompt
from app.agents.runner import collect_records, run_loop, tool_trace
from app.agents.tools import READ_TOOLS
from app.agents.types import AgentResult

NO_DATA_ANSWER = (
    "I can only answer from the database, and I did not look anything up for that. "
    "Try: 'Show me REQ-001', 'Which test cases belong to REQ-001?', "
    "'Show me high-risk items' or 'Which requirements have no test cases?'"
)
UNVERIFIED_ANSWER = (
    "I could not verify my answer against the database, so I am not showing it. "
    "The records I did find are listed below."
)
TOO_MANY_STEPS_ANSWER = "I could not finish looking that up. Please try a simpler question."


def answer_query(llm: LLMClient, session: Session, message: str) -> AgentResult:
    loop = run_loop(
        llm,
        session,
        system_prompt=load_prompt("query"),
        user_message=message,
        tools=READ_TOOLS,
    )
    records = collect_records(loop.events)
    trace = tool_trace(loop.events)

    if loop.rounds_exhausted:
        return AgentResult(TOO_MANY_STEPS_ANSWER, "query", False, False, records, trace)

    # An answer with no database lookup behind it is never shown.
    if not loop.events or not (loop.text or "").strip():
        return AgentResult(NO_DATA_ANSWER, "query", False, False, records, trace)

    # The grounding rule: every id in the answer must have appeared in a tool result.
    if ungrounded_ids(loop.text, loop.evidence):
        return AgentResult(UNVERIFIED_ANSWER, "query", False, False, records, trace)

    return AgentResult(loop.text.strip(), "query", True, False, records, trace)
