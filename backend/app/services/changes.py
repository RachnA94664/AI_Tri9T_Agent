"""Propose, confirm and reject changes to requirements.

The safety design:
  * propose  -> saves a PENDING change. Nothing is applied.
  * confirm  -> ONE transaction: check version, apply, bump version, write audit.
  * reject   -> closes the pending change without applying it.
Every step writes an audit row in the same transaction as the data change.
"""

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.domain import enums
from app.domain.errors import Conflict, NotFound, ValidationError
from app.domain.ids import ensure_valid_id
from app.domain.requirement_rules import validate_patch
from app.repositories import audit as audit_repo
from app.repositories import pending as pending_repo
from app.repositories import requirements as req_repo
from app.services.serializers import change_to_dict, requirement_to_dict
from app.services.uow import unit_of_work

ENTITY = "requirement"


def _now() -> datetime:
    return datetime.now(UTC)


def _check_who(actor: object, source: object) -> None:
    if not isinstance(actor, str) or not actor.strip():
        raise ValidationError("actor must not be empty")
    if source not in enums.AUDIT_SOURCES:
        raise ValidationError(f"source must be one of {enums.AUDIT_SOURCES}, got {source!r}")


def _get_change(session: Session, change_id: int):
    change = pending_repo.get(session, change_id)
    if change is None:
        raise NotFound(f"change {change_id} does not exist")
    return change


def propose_requirement_change(
    session: Session, requirement_id: str, patch: object, *, proposed_by: str, source: str = "ui"
) -> dict:
    """Validate a change and save it as pending. Changes NOTHING about the requirement."""
    ensure_valid_id("requirement", requirement_id)
    _check_who(proposed_by, source)
    req = req_repo.get(session, requirement_id)
    if req is None:
        raise NotFound(f"requirement {requirement_id} does not exist")

    clean = validate_patch(requirement_to_dict(req), patch)

    with unit_of_work(session):
        change = pending_repo.add(
            session,
            entity_type=ENTITY,
            entity_id=requirement_id,
            patch=clean,
            base_version=req.version,
            proposed_by=proposed_by,
        )
        audit_repo.add_entry(
            session,
            actor=proposed_by,
            source=source,
            entity_type=ENTITY,
            entity_id=requirement_id,
            action="propose",
            new={"change_id": change.id, "patch": clean},
        )

    preview = {f: {"old": getattr(req, f), "new": v} for f, v in clean.items()}
    return {"change": change_to_dict(change), "preview": preview}


def _expire(session: Session, change, actor: str, source: str, reason: str) -> None:
    with unit_of_work(session):
        change.status = "expired"
        change.resolved_at = _now()
        audit_repo.add_entry(
            session,
            actor=actor,
            source=source,
            entity_type=ENTITY,
            entity_id=change.entity_id,
            action="expire",
            new={"change_id": change.id, "reason": reason},
        )


def confirm_change(session: Session, change_id: int, *, actor: str, source: str = "ui") -> dict:
    """Apply a pending change. Safe to call twice: the second call changes nothing."""
    _check_who(actor, source)
    change = _get_change(session, change_id)

    if change.status == "applied":
        return {"change": change_to_dict(change), "already_applied": True}
    if change.status != "pending":
        raise Conflict(f"change {change_id} is {change.status}, so it cannot be confirmed")

    req = req_repo.get(session, change.entity_id)
    if req is None:
        raise NotFound(f"requirement {change.entity_id} does not exist")

    if req.version != change.base_version:
        _expire(session, change, actor, source, "requirement changed since the proposal")
        raise Conflict(
            "the requirement was changed after this change was proposed; propose it again",
            details={"base_version": change.base_version, "current_version": req.version},
        )

    patch = json.loads(change.proposed_patch)
    with unit_of_work(session):
        # Re-check the rules against the CURRENT values before applying.
        clean = validate_patch(requirement_to_dict(req), patch)
        old = {field: getattr(req, field) for field in clean}

        if not req_repo.update_if_version(session, req.id, change.base_version, clean):
            raise Conflict("another change was applied at the same moment; propose it again")

        change.status = "applied"
        change.resolved_at = _now()
        audit_repo.add_entry(
            session,
            actor=actor,
            source=source,
            entity_type=ENTITY,
            entity_id=req.id,
            action="update",
            old=old,
            new=clean,
        )
        session.refresh(req)  # pick up the new version and values

    return {
        "change": change_to_dict(change),
        "already_applied": False,
        "requirement": requirement_to_dict(req),
    }


def reject_change(session: Session, change_id: int, *, actor: str, source: str = "ui") -> dict:
    """Close a pending change without applying it."""
    _check_who(actor, source)
    change = _get_change(session, change_id)

    if change.status == "rejected":
        return {"change": change_to_dict(change), "already_rejected": True}
    if change.status != "pending":
        raise Conflict(f"change {change_id} is {change.status}, so it cannot be rejected")

    with unit_of_work(session):
        change.status = "rejected"
        change.resolved_at = _now()
        audit_repo.add_entry(
            session,
            actor=actor,
            source=source,
            entity_type=ENTITY,
            entity_id=change.entity_id,
            action="reject",
            new={"change_id": change.id},
        )
    return {"change": change_to_dict(change), "already_rejected": False}


def list_pending_changes(session: Session) -> list[dict]:
    return [change_to_dict(c) for c in pending_repo.list_by_status(session, "pending")]
