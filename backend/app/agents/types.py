"""What an agent hands back to the API and the UI."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    answer: str
    intent: str
    # True only if the answer passed the grounding check (or was written by code from tool output).
    grounded: bool = True
    # True when the system declined to act (out of scope, or something it never does).
    refused: bool = False
    # Records the tools returned: the evidence the UI shows beside the answer.
    records: list[dict[str, Any]] = field(default_factory=list)
    # Every tool that ran, with its arguments and outcome (the "tool trace").
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    # Proposals the Update Agent saved: [{"change": {...}, "preview": {...}}].
    # Nothing is applied until a person confirms each one.
    pending_changes: list[dict[str, Any]] = field(default_factory=list)
