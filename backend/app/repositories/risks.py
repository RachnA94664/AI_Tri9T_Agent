"""All SQL about risk items lives here."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RiskItem


def list_all(session: Session) -> list[RiskItem]:
    # Score and level are derived in the domain layer, so filtering by level
    # happens in the service, not in SQL.
    return list(session.scalars(select(RiskItem).order_by(RiskItem.id)))
