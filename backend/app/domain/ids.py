"""ID format rules: REQ-001, TC-001, RISK-001."""

import re

from app.domain.errors import ValidationError

_PATTERNS = {
    "requirement": re.compile(r"REQ-[0-9]{3}"),
    "test_case": re.compile(r"TC-[0-9]{3}"),
    "risk": re.compile(r"RISK-[0-9]{3}"),
}


def is_valid_id(kind: str, value: object) -> bool:
    """True if `value` is a string that fully matches the ID format for `kind`."""
    if kind not in _PATTERNS:
        raise ValueError(f"unknown kind: {kind!r}")
    return isinstance(value, str) and _PATTERNS[kind].fullmatch(value) is not None


def ensure_valid_id(kind: str, value: object) -> str:
    """Return the id, or raise ValidationError explaining what was wrong."""
    if not is_valid_id(kind, value):
        raise ValidationError(
            f"invalid {kind} id: {value!r}", details={"kind": kind, "value": value}
        )
    return value  # type: ignore[return-value]
