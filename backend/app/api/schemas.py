"""The API contract: the exact shape of every request and response.

Input models use `extra="forbid"`: unknown fields are rejected, so a client can
never sneak in something like `source` or `version`.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictIn(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- requests ----------


class ProposeChangeIn(StrictIn):
    requirement_id: str = Field(examples=["REQ-007"])
    patch: dict[str, Any] = Field(examples=[{"status": "implemented"}])
    proposed_by: str = Field(min_length=1, max_length=64, examples=["rachna"])


class ActorIn(StrictIn):
    actor: str = Field(min_length=1, max_length=64, examples=["rachna"])


# ---------- responses ----------


class RequirementOut(BaseModel):
    id: str
    title: str
    description: str
    priority: str
    status: str
    version: int
    created_at: str | None
    updated_at: str | None


class TestCaseOut(BaseModel):
    __test__ = False  # not a pytest class, despite the name
    id: str
    requirement_id: str
    title: str
    steps: str
    expected_result: str
    status: str


class RiskOut(BaseModel):
    id: str
    title: str
    description: str
    severity: int
    likelihood: int
    status: str
    score: int = Field(description="severity x likelihood (derived, never stored)")
    level: str = Field(description="low, medium or high (derived, never stored)")


class ChangeOut(BaseModel):
    id: int
    entity_type: str
    entity_id: str
    patch: dict[str, Any]
    base_version: int
    proposed_by: str
    status: str
    created_at: str | None
    resolved_at: str | None


class ProposeOut(BaseModel):
    change: ChangeOut
    preview: dict[str, dict[str, Any]] = Field(description="field -> {old, new}")


class ConfirmOut(BaseModel):
    change: ChangeOut
    already_applied: bool
    requirement: RequirementOut | None = None


class RejectOut(BaseModel):
    change: ChangeOut
    already_rejected: bool


class AuditOut(BaseModel):
    id: int
    ts: str | None
    actor: str
    source: str
    entity_type: str
    entity_id: str
    action: str
    old_value: Any | None
    new_value: Any | None
    request_id: str | None


class ChatIn(StrictIn):
    message: str = Field(max_length=1000, examples=["Which requirements have no test cases?"])


class ToolCallOut(BaseModel):
    name: str
    arguments: dict[str, Any]
    ok: bool
    error: str | None = None


class PendingChangeOut(BaseModel):
    change: ChangeOut
    preview: dict[str, dict[str, Any]]


class ChatOut(BaseModel):
    answer: str
    intent: str = Field(description="query, update, out_of_scope or refused")
    grounded: bool = Field(description="True if the answer is backed by database results")
    refused: bool = Field(description="True if the system declined to act")
    records: list[dict[str, Any]] = Field(description="the database records behind the answer")
    tool_calls: list[ToolCallOut] = Field(description="every tool the agent ran")
    pending_changes: list[PendingChangeOut] = Field(
        description="proposals saved by the Update Agent; nothing is applied until confirmed"
    )


class HealthOut(BaseModel):
    status: str
    database: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class ErrorOut(BaseModel):
    error: ErrorDetail
