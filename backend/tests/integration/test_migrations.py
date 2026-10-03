"""The migrations must build the full schema from nothing (a fresh clone)."""

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

BACKEND = Path(__file__).resolve().parents[2]


def test_alembic_upgrade_head_creates_all_tables(tmp_path):
    db_file = tmp_path / "fresh.db"
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file}")

    command.upgrade(cfg, "head")

    with sqlite3.connect(db_file) as conn:
        tables = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
    assert {
        "requirements",
        "test_cases",
        "risk_items",
        "requirement_risks",
        "audit_log",
        "pending_changes",
    } <= tables
