"""The propose / confirm / reject flow: the safety core of the system."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import models
from app.domain.errors import Conflict, InvalidTransition, NotFound, ValidationError
from app.services import changes, knowledge

WHO = {"proposed_by": "rachna"}
ACT = {"actor": "rachna"}


def audit_count(session) -> int:
    """
    Count the number of audit log entries.
    
    Args:
        session: The database session.
    
    Returns:
        The number of audit log entries.
    """
    return session.scalar(select(func.count()).select_from(models.AuditLog))


def requirement(session, req_id):
    """
    Get a requirement by its ID.
    
    Args:
        session: The database session.
        req_id: The ID of the requirement to get.
    """
    session.expire_all()  # make sure we read what is really stored
    return session.get(models.Requirement, req_id)


# ---------- propose ----------


def test_propose_saves_a_pending_change_and_applies_nothing(seeded):
    """
    Test that proposing a change saves it as pending and applies nothing.
    
    Args:
        seeded: The seeded database session.
    """
    result = changes.propose_requirement_change(seeded, "REQ-007", {"status": "implemented"}, **WHO)

    assert result["change"]["status"] == "pending"
    assert result["preview"] == {"status": {"old": "approved", "new": "implemented"}}
    req = requirement(seeded, "REQ-007")
    assert req.status == "approved" and req.version == 1  # untouched


def test_propose_writes_an_audit_entry(seeded):
    """
    Test that proposing a change writes an audit entry.
    
    Args:
        seeded: The seeded database session.
    """
    changes.propose_requirement_change(seeded, "REQ-007", {"status": "implemented"}, **WHO)

    entry = knowledge.audit_log(seeded)[0]
    assert entry["action"] == "propose" and entry["entity_id"] == "REQ-007"
    assert entry["actor"] == "rachna" and entry["source"] == "ui"


def test_invalid_transition_is_rejected_and_nothing_is_stored(seeded):
    """
    Test that an invalid transition is rejected and nothing is stored.
    
    Args:
        seeded: The seeded database session.
    """
    before = audit_count(seeded)
    with pytest.raises(InvalidTransition):
        changes.propose_requirement_change(seeded, "REQ-007", {"status": "draft"}, **WHO)

    assert changes.list_pending_changes(seeded) == []
    assert audit_count(seeded) == before


@pytest.mark.parametrize(
    "req_id,patch,error",
    [
        ("REQ-099", {"status": "verified"}, NotFound),
        ("banana", {"status": "verified"}, ValidationError),
        ("REQ-007", {"id": "REQ-500"}, ValidationError),
        ("REQ-007", {}, ValidationError),
        ("REQ-007", {"priority": "urgent"}, ValidationError),
    ],
)
def test_bad_proposals_are_rejected(seeded, req_id, patch, error):
    """
    Test that bad proposals are rejected.
    
    Args:
        seeded: The seeded database session.
        req_id: The ID of the requirement to change.
        patch: The proposed change.
        error: The expected error.
    """
    with pytest.raises(error):
        changes.propose_requirement_change(seeded, req_id, patch, **WHO)
    assert changes.list_pending_changes(seeded) == []


def test_bad_actor_or_source_is_rejected(seeded):
    """
    Test that bad actor or source is rejected.
    
    Args:
        seeded: The seeded database session.
    """
    with pytest.raises(ValidationError):
        changes.propose_requirement_change(seeded, "REQ-007", {"priority": "low"}, proposed_by=" ")
    with pytest.raises(ValidationError):
        changes.propose_requirement_change(
            seeded, "REQ-007", {"priority": "low"}, proposed_by="x", source="hacker"
        )


# ---------- confirm ----------


def test_confirm_applies_the_change_bumps_the_version_and_logs_it(seeded):
    """
    Test that confirming a change applies it, bumps the version, and logs it.
    
    Args:
        seeded: The seeded database session.
    """
    cid = changes.propose_requirement_change(seeded, "REQ-007", {"status": "implemented"}, **WHO)[
        "change"
    ]["id"]

    result = changes.confirm_change(seeded, cid, **ACT)

    assert result["already_applied"] is False
    req = requirement(seeded, "REQ-007")
    assert req.status == "implemented" and req.version == 2
    entry = next(e for e in knowledge.audit_log(seeded) if e["action"] == "update")
    assert entry["old_value"] == {"status": "approved"}
    assert entry["new_value"] == {"status": "implemented"}


def test_confirming_twice_changes_nothing_the_second_time(seeded):
    """
    Test that confirming a change twice changes nothing the second time.
    
    Args:
        seeded: The seeded database session.
    """
    cid = changes.propose_requirement_change(seeded, "REQ-007", {"status": "implemented"}, **WHO)[
        "change"
    ]["id"]
    changes.confirm_change(seeded, cid, **ACT)
    audit_after_first = audit_count(seeded)

    second = changes.confirm_change(seeded, cid, **ACT)

    assert second["already_applied"] is True
    assert requirement(seeded, "REQ-007").version == 2  # not bumped again
    assert audit_count(seeded) == audit_after_first  # no duplicate audit row


def test_stale_version_is_a_conflict_and_the_old_change_expires(seeded):
    """
    Test that a stale version is a conflict and the old change expires.
    
    Args:
        seeded: The seeded database session.
    """
    first = changes.propose_requirement_change(seeded, "REQ-007", {"status": "implemented"}, **WHO)
    second = changes.propose_requirement_change(seeded, "REQ-007", {"status": "obsolete"}, **WHO)
    changes.confirm_change(seeded, first["change"]["id"], **ACT)  # version 1 -> 2

    with pytest.raises(Conflict):
        changes.confirm_change(seeded, second["change"]["id"], **ACT)

    assert requirement(seeded, "REQ-007").status == "implemented"  # second was NOT applied
    expired = seeded.get(models.PendingChange, second["change"]["id"])
    assert expired.status == "expired"
    assert any(e["action"] == "expire" for e in knowledge.audit_log(seeded))


def test_failure_in_the_middle_rolls_everything_back(seeded, monkeypatch):
    """
    Test that a failure in the middle rolls everything back.
    
    Args:
        seeded: The seeded database session.
        monkeypatch: The monkeypatch fixture.
    """
    cid = changes.propose_requirement_change(seeded, "REQ-007", {"status": "implemented"}, **WHO)[
        "change"
    ]["id"]
    real_add_entry = changes.audit_repo.add_entry

    def failing_add_entry(*args, **kwargs):
        if kwargs.get("action") == "update":
            raise RuntimeError("disk exploded while writing the audit row")
        return real_add_entry(*args, **kwargs)

    monkeypatch.setattr(changes.audit_repo, "add_entry", failing_add_entry)

    with pytest.raises(RuntimeError):
        changes.confirm_change(seeded, cid, **ACT)

    req = requirement(seeded, "REQ-007")
    assert req.status == "approved" and req.version == 1  # data change was undone
    assert seeded.get(models.PendingChange, cid).status == "pending"  # still confirmable
    assert not any(e["action"] == "update" for e in knowledge.audit_log(seeded))


def test_confirm_unknown_change_is_not_found(seeded):
    """
    Test that an unknown change is not found.
    
    Args:
        seeded: The seeded database session.
    """
    with pytest.raises(NotFound):
        changes.confirm_change(seeded, 9999, **ACT)


# ---------- reject ----------


def test_reject_closes_the_change_without_applying_it(seeded):
    """
    Test that rejecting a change closes it without applying it.
    
    Args:
        seeded: The seeded database session.
    """
    cid = changes.propose_requirement_change(seeded, "REQ-007", {"status": "implemented"}, **WHO)[
        "change"
    ]["id"]

    changes.reject_change(seeded, cid, **ACT)

    assert requirement(seeded, "REQ-007").status == "approved"
    assert any(e["action"] == "reject" for e in knowledge.audit_log(seeded))
    with pytest.raises(Conflict):
        changes.confirm_change(seeded, cid, **ACT)  # cannot confirm a rejected change


def test_rejecting_twice_is_harmless(seeded):
    """
    Test that rejecting a change twice is harmless.
    
    Args:
        seeded: The seeded database session.
    """
    cid = changes.propose_requirement_change(seeded, "REQ-007", {"status": "implemented"}, **WHO)[
        "change"
    ]["id"]
    changes.reject_change(seeded, cid, **ACT)
    assert changes.reject_change(seeded, cid, **ACT)["already_rejected"] is True


def test_cannot_reject_an_applied_change(seeded):
    """
    Test that an applied change cannot be rejected.
    
    Args:
        seeded: The seeded database session.
    """
    cid = changes.propose_requirement_change(seeded, "REQ-007", {"status": "implemented"}, **WHO)[
        "change"
    ]["id"]
    changes.confirm_change(seeded, cid, **ACT)
    with pytest.raises(Conflict):
        changes.reject_change(seeded, cid, **ACT)


# ---------- the audit log is append-only ----------


def test_audit_rows_cannot_be_updated(seeded):
    """
    Test that audit rows cannot be updated.
    
    Args:
        seeded: The seeded database session.
    """
    changes.propose_requirement_change(seeded, "REQ-007", {"status": "implemented"}, **WHO)
    entry = seeded.scalars(select(models.AuditLog)).first()
    entry.actor = "someone else"
    with pytest.raises(IntegrityError, match="append-only"):
        seeded.commit()
    seeded.rollback()


def test_audit_rows_cannot_be_deleted(seeded):  
    """
    Test that audit rows cannot be deleted.
    
    Args:
        seeded: The seeded database session.
    """
    changes.propose_requirement_change(seeded, "REQ-007", {"status": "implemented"}, **WHO)
    entry = seeded.scalars(select(models.AuditLog)).first()
    seeded.delete(entry)
    with pytest.raises(IntegrityError, match="append-only"):
        seeded.commit()
    seeded.rollback()
