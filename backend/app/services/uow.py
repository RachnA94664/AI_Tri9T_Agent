"""Unit of work: everything inside the `with` block commits together or not at all."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session


@contextmanager
def unit_of_work(session: Session) -> Iterator[Session]:
    """
    Unit of work: everything inside the `with` block commits together or not at all.

    Args:
        session: The database session.

    Returns:
        The session.

    Yields:
        The session.

    Raises:
        Exception: If any exception occurs during the unit of work.
    """
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
