"""Unit of work: everything inside the `with` block commits together or not at all."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session


@contextmanager
def unit_of_work(session: Session) -> Iterator[Session]:
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()  # undo EVERYTHING done inside the block
        raise
