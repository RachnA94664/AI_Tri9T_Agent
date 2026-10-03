"""Shared test fixtures.

Each test gets its own fresh, empty SQLite database file, so tests never
affect each other (and never touch your real knowledge.db).
"""

import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.db.session import make_engine

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture
def session(tmp_path) -> Session:
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        yield s
    engine.dispose()


@pytest.fixture
def valid_seed() -> dict:
    return json.loads((DATA_DIR / "seed_raw.json").read_text(encoding="utf-8"))


@pytest.fixture
def invalid_seed() -> dict:
    return json.loads((DATA_DIR / "seed_invalid_examples.json").read_text(encoding="utf-8"))
