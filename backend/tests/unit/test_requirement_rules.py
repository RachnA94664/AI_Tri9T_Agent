import pytest

from app.domain.errors import InvalidTransition, ValidationError
from app.domain.requirement_rules import MAX_TITLE_LENGTH, validate_patch

CURRENT = {
    "title": "Detect ground fault",
    "description": "Open the contactor above 20 mA.",
    "priority": "critical",
    "status": "implemented",
}


def test_valid_status_change_is_returned():
    assert validate_patch(CURRENT, {"status": "verified"}) == {"status": "verified"}


def test_unchanged_fields_are_dropped():
    patch = {"status": "verified", "priority": "critical"}
    assert validate_patch(CURRENT, patch) == {"status": "verified"}


def test_title_is_trimmed():
    assert validate_patch(CURRENT, {"title": "  New title  "}) == {"title": "New title"}


@pytest.mark.parametrize("bad", [None, [], {}, "status", 5])
def test_patch_must_be_a_non_empty_object(bad):
    with pytest.raises(ValidationError):
        validate_patch(CURRENT, bad)


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError) as exc:
        validate_patch(CURRENT, {"id": "REQ-999"})
    assert exc.value.details["unknown"] == ["id"]


def test_version_cannot_be_set_by_a_patch():
    with pytest.raises(ValidationError):
        validate_patch(CURRENT, {"version": 99})


@pytest.mark.parametrize(
    "patch",
    [
        {"title": ""},
        {"title": "   "},
        {"title": 5},
        {"title": "x" * (MAX_TITLE_LENGTH + 1)},
        {"description": 5},
        {"priority": "urgent"},
    ],
)
def test_bad_values_are_rejected(patch):
    with pytest.raises(ValidationError):
        validate_patch(CURRENT, patch)


def test_status_must_follow_the_state_machine():
    with pytest.raises(InvalidTransition):
        validate_patch(CURRENT, {"status": "draft"})  # backwards


def test_a_change_that_alters_nothing_is_rejected():
    with pytest.raises(ValidationError):
        validate_patch(CURRENT, {"priority": "critical"})
