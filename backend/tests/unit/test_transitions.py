import pytest

from app.domain.errors import InvalidTransition, ValidationError
from app.domain.transitions import ALLOWED_TRANSITIONS, can_transition, ensure_transition


@pytest.mark.parametrize(
    "current,new",
    [
        ("draft", "approved"),
        ("approved", "implemented"),
        ("implemented", "verified"),
        ("draft", "obsolete"),
        ("verified", "obsolete"),
    ],
)
def test_allowed_moves(current, new):
    assert can_transition(current, new)
    ensure_transition(current, new)  # must not raise


@pytest.mark.parametrize(
    "current,new",
    [
        ("draft", "verified"),  # skipping steps
        ("draft", "implemented"),
        ("verified", "draft"),  # going backwards
        ("approved", "draft"),
        ("draft", "draft"),  # no-op is not a change
        ("obsolete", "draft"),  # obsolete is final
        ("obsolete", "obsolete"),
    ],
)
def test_forbidden_moves(current, new):
    assert not can_transition(current, new)
    with pytest.raises(InvalidTransition):
        ensure_transition(current, new)


def test_error_lists_what_is_allowed():
    with pytest.raises(InvalidTransition) as exc:
        ensure_transition("draft", "verified")
    assert exc.value.details["allowed"] == ["approved", "obsolete"]


def test_unknown_status_is_a_validation_error():
    with pytest.raises(ValidationError):
        ensure_transition("draft", "banana")


def test_obsolete_is_final():
    assert ALLOWED_TRANSITIONS["obsolete"] == set()
