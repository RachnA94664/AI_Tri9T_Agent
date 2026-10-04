"""All SQL about pending changes lives here."""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PendingChange


def add(
    session: Session,
    *,
    entity_type: str,
    entity_id: str,
    patch: dict,
    base_version: int,
    proposed_by: str,
) -> PendingChange:
    change = PendingChange(
        entity_type=entity_type,
        entity_id=entity_id,
        proposed_patch=json.dumps(patch, sort_keys=True),
        base_version=base_version,
        proposed_by=proposed_by,
        status="pending",
    )
    session.add(change)
    session.flush()  # assigns change.id without committing
    return change


def get(session: Session, change_id: int) -> PendingChange | None:
    return session.get(PendingChange, change_id)


def list_by_status(session: Session, status: str = "pending") -> list[PendingChange]:
    return list(
        session.scalars(
            select(PendingChange).where(PendingChange.status == status).order_by(PendingChange.id)
        )
    )
