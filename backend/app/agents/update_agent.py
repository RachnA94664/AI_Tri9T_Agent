"""Update Agent: turns "change REQ-007 to implemented" into a PROPOSAL. It never applies anything.

When a proposal is saved, the reply is written by CODE from the tool's result, not by
the AI, so it can never claim "done" when nothing was applied.
"""

from sqlalchemy.orm import Session

from app.agents.llm import LLMClient
from app.agents.prompt_loader import load_prompt
from app.agents.runner import ToolEvent, collect_records, run_loop, tool_trace
from app.agents.tools import PROPOSE_CHANGE, UPDATE_TOOLS
from app.agents.types import AgentResult

NEEDS_DETAILS_ANSWER = (
    "I need a requirement id and the new value. For example: "
    "'Set REQ-007 status to implemented' or 'Change the priority of REQ-003 to high'."
)
TOO_MANY_STEPS_ANSWER = "I could not finish preparing that change. Please try a simpler request."


def _describe(event: ToolEvent) -> str:
    change = event.result["change"]
    steps = "; ".join(
        f"{f}: {v['old']!r} -> {v['new']!r}" for f, v in event.result["preview"].items()
    )
    return f"Proposed change #{change['id']} for {change['entity_id']} ({steps})."


def propose_update(llm: LLMClient, session: Session, message: str) -> AgentResult:
    loop = run_loop(
        llm,
        session,
        system_prompt=load_prompt("update"),
        user_message=message,
        tools=UPDATE_TOOLS,
    )
    records = collect_records(loop.events)
    trace = tool_trace(loop.events)
    proposals = [e for e in loop.events if e.name == PROPOSE_CHANGE.name]

    if proposals:
        lines = [
            _describe(e) if e.ok else f"I could not propose that: {e.error}" for e in proposals
        ]
        saved = [e for e in proposals if e.ok]
        if saved:
            lines.append(
                "Nothing has been changed yet. Confirm or reject each proposal in the app."
            )
        return AgentResult(
            answer=" ".join(lines),
            intent="update",
            grounded=True,  # written by code from tool output
            records=records,
            tool_calls=trace,
            pending_changes=[
                {"change": e.result["change"], "preview": e.result["preview"]} for e in saved
            ],
        )

    if loop.rounds_exhausted:
        return AgentResult(TOO_MANY_STEPS_ANSWER, "update", False, False, records, trace)

    return AgentResult(NEEDS_DETAILS_ANSWER, "update", False, False, records, trace)
