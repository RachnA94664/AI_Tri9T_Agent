"""All SQL about test cases lives here."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import TestCase


def for_requirement(session: Session, requirement_id: str) -> list[TestCase]:
    return list(
        session.scalars(
            select(TestCase).where(TestCase.requirement_id == requirement_id).order_by(TestCase.id)
        )
    )
