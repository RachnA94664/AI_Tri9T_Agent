"""Read-only use cases. The API and the agents call these, never the repositories."""

from sqlalchemy.orm import Session

from app.domain.enums import RISK_LEVELS
from app.domain.errors import NotFound, ValidationError
from app.domain.ids import ensure_valid_id
from app.repositories import audit as audit_repo
from app.repositories import requirements as req_repo
from app.repositories import risks as risk_repo
from app.repositories import testcases as tc_repo
from app.services import serializers as ser


def _require_requirement(session: Session, requirement_id: str):
    ensure_valid_id("requirement", requirement_id)
    req = req_repo.get(session, requirement_id)
    if req is None:
        raise NotFound(f"requirement {requirement_id} does not exist")
    return req


def get_requirement(session: Session, requirement_id: str) -> dict:
    return ser.requirement_to_dict(_require_requirement(session, requirement_id))


def list_requirements(session: Session) -> list[dict]:
    return [ser.requirement_to_dict(r) for r in req_repo.list_all(session)]


def get_test_cases_for_requirement(session: Session, requirement_id: str) -> list[dict]:
    _require_requirement(session, requirement_id)  # unknown requirement is NotFound, not []
    return [ser.testcase_to_dict(t) for t in tc_repo.for_requirement(session, requirement_id)]


def list_requirements_without_tests(session: Session) -> list[dict]:
    return [ser.requirement_to_dict(r) for r in req_repo.list_without_tests(session)]


def list_risks(session: Session, level: str | None = None) -> list[dict]:
    """All risks, highest score first; optionally only one level (low/medium/high)."""
    if level is not None and level not in RISK_LEVELS:
        raise ValidationError(f"level must be one of {RISK_LEVELS}, got {level!r}")
    items = [ser.risk_to_dict(r) for r in risk_repo.list_all(session)]
    if level is not None:
        items = [r for r in items if r["level"] == level]
    return sorted(items, key=lambda r: (-r["score"], r["id"]))


def audit_log(session: Session, limit: int = 50, entity_id: str | None = None) -> list[dict]:
    if not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValidationError("limit must be a whole number from 1 to 500")
    return [ser.audit_to_dict(e) for e in audit_repo.list_recent(session, limit, entity_id)]
