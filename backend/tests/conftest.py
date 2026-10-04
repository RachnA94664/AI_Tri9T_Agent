"""Shared test fixtures.

Each test gets its own fresh SQLite database, built by the REAL migrations (so
foreign keys, CHECK constraints and the audit-log triggers all exist exactly as
in production). Migrating once and copying the file keeps tests fast.
"""

import json
import shutil
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session, sessionmaker

from app.db.seed import load_seed
from app.db.session import make_engine

BACKEND = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND / "data"


@pytest.fixture(scope="session")
def migrated_template(tmp_path_factory) -> Path:
    """An empty, fully migrated database, built once per test run."""
    db_file = tmp_path_factory.mktemp("template") / "template.db"
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file}")
    command.upgrade(cfg, "head")
    return db_file


@pytest.fixture
def session(tmp_path, migrated_template) -> Session:
    db_file = tmp_path / "test.db"
    shutil.copy(migrated_template, db_file)
    engine = make_engine(f"sqlite:///{db_file}")
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        yield s
    engine.dispose()


@pytest.fixture
def valid_seed() -> dict:
    return json.loads((DATA_DIR / "seed_raw.json").read_text(encoding="utf-8"))


@pytest.fixture
def invalid_seed() -> dict:
    return json.loads((DATA_DIR / "seed_invalid_examples.json").read_text(encoding="utf-8"))


@pytest.fixture
def seeded(session, valid_seed) -> Session:
    """A session on a database already holding the 15/30/12/16 seed data."""
    load_seed(session, valid_seed)
    return session
