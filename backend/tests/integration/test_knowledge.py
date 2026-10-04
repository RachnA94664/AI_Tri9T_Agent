"""Read-only use cases: they must return what is really in the database."""

import pytest

from app.domain.errors import NotFound, ValidationError
from app.services import knowledge


def test_get_requirement(seeded):
    req = knowledge.get_requirement(seeded, "REQ-001")
    assert req["title"] == "Start charging session on authenticated connection"
    assert req["version"] == 1


def test_unknown_requirement_is_not_found_never_invented(seeded):
    with pytest.raises(NotFound):
        knowledge.get_requirement(seeded, "REQ-099")


def test_malformed_id_is_a_validation_error(seeded):
    with pytest.raises(ValidationError):
        knowledge.get_requirement(seeded, "banana")


def test_test_cases_for_requirement(seeded):
    ids = [t["id"] for t in knowledge.get_test_cases_for_requirement(seeded, "REQ-001")]
    assert ids == ["TC-001", "TC-002", "TC-003", "TC-027"]


def test_test_cases_for_unknown_requirement_is_not_found(seeded):
    with pytest.raises(NotFound):
        knowledge.get_test_cases_for_requirement(seeded, "REQ-099")


def test_requirement_without_test_cases_returns_an_empty_list(seeded):
    assert knowledge.get_test_cases_for_requirement(seeded, "REQ-012") == []


def test_requirements_without_tests(seeded):
    ids = [r["id"] for r in knowledge.list_requirements_without_tests(seeded)]
    assert ids == ["REQ-012", "REQ-013", "REQ-014", "REQ-015"]


def test_high_risk_items(seeded):
    high = knowledge.list_risks(seeded, level="high")
    assert [r["id"] for r in high] == ["RISK-002"]
    assert high[0]["score"] == 15 and high[0]["level"] == "high"


def test_risks_are_sorted_by_score_and_levels_are_derived(seeded):
    risks = knowledge.list_risks(seeded)
    scores = [r["score"] for r in risks]
    assert scores == sorted(scores, reverse=True)
    by_id = {r["id"]: r for r in risks}
    assert by_id["RISK-003"]["level"] == "medium"  # 4 x 3 = 12
    assert by_id["RISK-008"]["level"] == "low"  # 5 x 1 = 5


def test_bad_risk_level_is_rejected(seeded):
    with pytest.raises(ValidationError):
        knowledge.list_risks(seeded, level="extreme")


@pytest.mark.parametrize("limit", [0, 501, "10", None])
def test_audit_limit_is_validated(seeded, limit):
    with pytest.raises(ValidationError):
        knowledge.audit_log(seeded, limit=limit)
