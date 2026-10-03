import pytest

from app.domain.errors import ValidationError
from app.domain.ids import ensure_valid_id, is_valid_id


@pytest.mark.parametrize(
    "kind,value",
    [("requirement", "REQ-001"), ("test_case", "TC-123"), ("risk", "RISK-999")],
)
def test_valid_ids(kind, value):
    assert is_valid_id(kind, value)
    assert ensure_valid_id(kind, value) == value


@pytest.mark.parametrize(
    "kind,value",
    [
        ("requirement", "R-1"),
        ("requirement", "REQ-0011"),
        ("requirement", "req-001"),
        ("requirement", "REQ-001\n"),
        ("requirement", ""),
        ("requirement", None),
        ("test_case", "REQ-001"),
        ("risk", "RISK-1"),
    ],
)
def test_invalid_ids(kind, value):
    assert not is_valid_id(kind, value)
    with pytest.raises(ValidationError):
        ensure_valid_id(kind, value)


def test_unknown_kind_is_a_programming_error():
    with pytest.raises(ValueError):
        is_valid_id("banana", "REQ-001")
