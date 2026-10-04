"""Endpoints for changing data. Nothing is edited directly:

    POST /changes              propose (saved as pending, NOT applied)
    POST /changes/{id}/confirm apply it
    POST /changes/{id}/reject  discard it

There is deliberately no PUT, PATCH or DELETE on any record.
"""

from fastapi import APIRouter

from app.api.deps import API_SOURCE, ERRORS, SessionDep
from app.api.schemas import ActorIn, ChangeOut, ConfirmOut, ProposeChangeIn, ProposeOut, RejectOut
from app.services import changes

router = APIRouter(tags=["changes"])


@router.get("/changes", response_model=list[ChangeOut])
def list_pending(session: SessionDep):
    """Changes waiting to be confirmed or rejected."""
    return changes.list_pending_changes(session)


@router.post(
    "/changes",
    response_model=ProposeOut,
    status_code=201,
    responses={404: ERRORS[404], 409: ERRORS[409], 422: ERRORS[422]},
)
def propose_change(body: ProposeChangeIn, session: SessionDep):
    """Propose a change to a requirement. Returns the pending change and a preview."""
    return changes.propose_requirement_change(
        session,
        body.requirement_id,
        body.patch,
        proposed_by=body.proposed_by,
        source=API_SOURCE,
    )


@router.post(
    "/changes/{change_id}/confirm",
    response_model=ConfirmOut,
    responses={404: ERRORS[404], 409: ERRORS[409], 422: ERRORS[422]},
)
def confirm_change(change_id: int, body: ActorIn, session: SessionDep):
    """Apply a pending change. Confirming twice is harmless (already_applied=true)."""
    return changes.confirm_change(session, change_id, actor=body.actor, source=API_SOURCE)


@router.post(
    "/changes/{change_id}/reject",
    response_model=RejectOut,
    responses={404: ERRORS[404], 409: ERRORS[409], 422: ERRORS[422]},
)
def reject_change(change_id: int, body: ActorIn, session: SessionDep):
    """Discard a pending change without applying it."""
    return changes.reject_change(session, change_id, actor=body.actor, source=API_SOURCE)
