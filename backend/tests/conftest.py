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
def engine(tmp_path, migrated_template):
    """A private copy of the migrated database for ONE test."""
    db_file = tmp_path / "test.db"
    shutil.copy(migrated_template, db_file)
    eng = make_engine(f"sqlite:///{db_file}")
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine) -> Session:
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        yield s


@pytest.fixture
def api(engine, valid_seed):
    """A TestClient talking to the real app, backed by a seeded temporary database."""
    from fastapi.testclient import TestClient

    from app.db.session import get_session
    from app.main import app

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as s:
        load_seed(s, valid_seed)

    def override_get_session():
        with factory() as request_session:  # one session per request, like production
            yield request_session

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()


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
