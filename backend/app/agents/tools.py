"""Tools: the only actions an agent can take.

Rules of the design:
  * A tool calls a SERVICE, never a repository or the database directly.
  * Arguments are validated (unknown fields rejected) before anything runs.
  * Expected problems (not found, invalid change) come back as data the model can
    read, so it can say "not found" instead of inventing an answer.
  * There is NO tool to confirm, reject or delete anything. The only write tool
    PROPOSES a change; a human confirms it in the UI.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.domain.errors import DomainError
from app.services import changes, knowledge

AGENT_ACTOR = "update-agent"
AGENT_SOURCE = "agent"


# ---------- argument models (also produce the JSON schema the AI sees) ----------


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoArgs(_Args):
    pass


class RequirementIdArgs(_Args):
    requirement_id: str = Field(description="A requirement id such as REQ-001")


class RiskListArgs(_Args):
    level: Literal["low", "medium", "high"] | None = Field(
        default=None, description="Only risks of this level. Omit for all risks."
    )


class AuditArgs(_Args):
    limit: int = Field(default=20, ge=1, le=100, description="How many entries (newest first)")
    entity_id: str | None = Field(default=None, description="Only entries about this id")


class ProposeArgs(_Args):
    requirement_id: str = Field(description="The requirement to change, such as REQ-007")
    title: str | None = Field(default=None, description="New title")
    description: str | None = Field(default=None, description="New description")
    priority: Literal["low", "medium", "high", "critical"] | None = Field(
        default=None, description="New priority"
    )
    status: Literal["draft", "approved", "implemented", "verified", "obsolete"] | None = Field(
        default=None, description="New status"
    )


# ---------- the Tool wrapper ----------


def _strip_titles(node: Any, is_property_map: bool = False) -> Any:
    """pydantic adds a "title" annotation to every field; the AI does not need them.

    Careful: inside a "properties" map the keys are FIELD NAMES, and one of our fields
    really is called "title". Those keys must be kept.
    """
    if isinstance(node, dict):
        return {
            k: _strip_titles(v, is_property_map=(k == "properties"))
            for k, v in node.items()
            if is_property_map or k != "title"
        }
    if isinstance(node, list):
        return [_strip_titles(v) for v in node]
    return node


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[Session, Any], Any]
    writes: bool = False

    def schema(self) -> dict:
        """The tool description in the format the AI provider expects."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": _strip_titles(self.args_model.model_json_schema()),
            },
        }

    def run(self, session: Session, raw_arguments: dict) -> dict:
        """Run the tool. Never raises for expected problems: returns {ok, result|error}."""
        try:
            args = self.args_model(**raw_arguments)
        except PydanticValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()
            )
            return {"ok": False, "error": {"code": "invalid_arguments", "message": problems}}
        try:
            return {"ok": True, "result": self.handler(session, args)}
        except DomainError as exc:
            return {"ok": False, "error": {"code": exc.code, "message": exc.message}}


# ---------- handlers: thin adapters over services ----------


def _propose(session: Session, a: ProposeArgs) -> dict:
    patch = a.model_dump(exclude={"requirement_id"}, exclude_none=True)
    return changes.propose_requirement_change(
        session, a.requirement_id, patch, proposed_by=AGENT_ACTOR, source=AGENT_SOURCE
    )


GET_REQUIREMENT = Tool(
    "get_requirement",
    "Get one requirement by id (title, description, priority, status, version).",
    RequirementIdArgs,
    lambda s, a: knowledge.get_requirement(s, a.requirement_id),
)
LIST_REQUIREMENTS = Tool(
    "list_requirements",
    "List all requirements.",
    NoArgs,
    lambda s, a: knowledge.list_requirements(s),
)
GET_TEST_CASES = Tool(
    "get_test_cases_for_requirement",
    "List the test cases that belong to a requirement.",
    RequirementIdArgs,
    lambda s, a: knowledge.get_test_cases_for_requirement(s, a.requirement_id),
)
LIST_RISKS = Tool(
    "list_risks",
    "List risk items with their score and level, highest first. Optionally only one level.",
    RiskListArgs,
    lambda s, a: knowledge.list_risks(s, a.level),
)
LIST_WITHOUT_TESTS = Tool(
    "list_requirements_without_tests",
    "List the requirements that have no test cases.",
    NoArgs,
    lambda s, a: knowledge.list_requirements_without_tests(s),
)
GET_AUDIT_LOG = Tool(
    "get_audit_log",
    "Show recent changes recorded in the audit log, newest first.",
    AuditArgs,
    lambda s, a: knowledge.audit_log(s, a.limit, a.entity_id),
)
PROPOSE_CHANGE = Tool(
    "propose_requirement_change",
    "Propose a change to a requirement. This does NOT apply it: a person must confirm it.",
    ProposeArgs,
    _propose,
    writes=True,
)

# What each agent is allowed to use.
READ_TOOLS: tuple[Tool, ...] = (
    GET_REQUIREMENT,
    LIST_REQUIREMENTS,
    GET_TEST_CASES,
    LIST_RISKS,
    LIST_WITHOUT_TESTS,
    GET_AUDIT_LOG,
)
UPDATE_TOOLS: tuple[Tool, ...] = (GET_REQUIREMENT, PROPOSE_CHANGE)
