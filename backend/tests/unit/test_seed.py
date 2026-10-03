"""Tests for the seed loader and the database constraints (Phase 2)."""

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.db import models
from app.db.seed import load_seed


def count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_valid_seed_loads_everything(session, valid_seed):
    report = load_seed(session, valid_seed)

    assert report.rejected == []
    assert report.inserted == {
        "requirements": 15,
        "test_cases": 30,
        "risk_items": 12,
        "requirement_risks": 16,
    }
    assert count(session, models.Requirement) == 15


def test_all_invalid_examples_are_rejected(session, valid_seed, invalid_seed):
    load_seed(session, valid_seed)  # so the "duplicate REQ-001" row has something to collide with
    before = {
        m: count(session, m)
        for m in (models.Requirement, models.TestCase, models.RiskItem, models.RequirementRisk)
    }

    report = load_seed(session, invalid_seed)

    assert len(report.rejected) == 7
    assert all(v == 0 for v in report.inserted.values())
    after = {m: count(session, m) for m in before}
    assert after == before  # nothing bad reached the database


@pytest.mark.parametrize(
    "fragment",
    [
        "duplicate ID",
        "id must look like",
        "must not be empty",
        "priority must be one of",
        "unknown requirement",
        "between 1 and 5",
        "unknown risk",
    ],
)
def test_rejection_reasons_are_explained(session, valid_seed, invalid_seed, fragment):
    load_seed(session, valid_seed)
    report = load_seed(session, invalid_seed)
    assert any(fragment in line for line in report.rejected), report.rejected


def test_duplicate_ids_inside_one_file_are_rejected(session):
    row = {"id": "REQ-001", "title": "A", "priority": "low", "status": "draft"}
    report = load_seed(session, {"requirements": [row, dict(row, title="B")]})
    assert report.inserted["requirements"] == 1
    assert any("duplicate ID" in r for r in report.rejected)


def test_database_rejects_orphan_test_case(session):
    """Foreign keys must be ON: a test case for a missing requirement fails."""
    session.add(models.TestCase(id="TC-999", requirement_id="REQ-999", title="x", status="not_run"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_database_rejects_out_of_range_severity(session):
    session.add(models.RiskItem(id="RISK-999", title="x", severity=9, likelihood=2, status="open"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_database_rejects_bad_id_format(session):
    session.add(models.Requirement(id="R-1", title="x", priority="low", status="draft"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_cannot_delete_requirement_that_has_test_cases(session, valid_seed):
    load_seed(session, valid_seed)
    # Direct SQL (not session.delete) so the DATABASE's ON DELETE RESTRICT is what we test.
    with pytest.raises(IntegrityError):
        session.execute(delete(models.Requirement).where(models.Requirement.id == "REQ-001"))
        session.commit()
