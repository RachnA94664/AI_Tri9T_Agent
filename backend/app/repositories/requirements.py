"""All SQL about requirements lives here."""

from datetime import UTC, datetime

from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session

from app.db.models import Requirement, TestCase


def get(session: Session, requirement_id: str) -> Requirement | None:
    return session.get(Requirement, requirement_id)


def list_all(session: Session) -> list[Requirement]:
    return list(session.scalars(select(Requirement).order_by(Requirement.id)))


def list_without_tests(session: Session) -> list[Requirement]:
    """Requirements that no test case points at."""
    has_tests = exists().where(TestCase.requirement_id == Requirement.id)
    return list(session.scalars(select(Requirement).where(~has_tests).order_by(Requirement.id)))


def update_if_version(
    session: Session, requirement_id: str, base_version: int, values: dict
) -> bool:
    """Optimistic locking: update only if nobody else changed the row meanwhile.

    The WHERE clause includes `version == base_version`. If another change got
    there first, no row matches and we return False.
    """
    result = session.execute(
        update(Requirement)
        .where(Requirement.id == requirement_id, Requirement.version == base_version)
        .values(**values, version=base_version + 1, updated_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1
