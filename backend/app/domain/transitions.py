"""Which requirement status changes are allowed.

draft -> approved -> implemented -> verified, and any status -> obsolete.
obsolete is final. There are no backward moves.
"""

from app.domain.enums import REQUIREMENT_STATUSES
from app.domain.errors import InvalidTransition, ValidationError

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"approved", "obsolete"},
    "approved": {"implemented", "obsolete"},
    "implemented": {"verified", "obsolete"},
    "verified": {"obsolete"},
    "obsolete": set(),
}


def can_transition(current: str, new: str) -> bool:
    return new in ALLOWED_TRANSITIONS.get(current, set())


def ensure_transition(current: str, new: str) -> None:
    """Raise if moving from `current` to `new` is not allowed."""
    for name, value in (("current", current), ("new", new)):
        if value not in REQUIREMENT_STATUSES:
            raise ValidationError(
                f"{name} status must be one of {REQUIREMENT_STATUSES}, got {value!r}"
            )
    if not can_transition(current, new):
        allowed = sorted(ALLOWED_TRANSITIONS[current])
        raise InvalidTransition(
            f"cannot change status from {current!r} to {new!r}",
            details={"current": current, "new": new, "allowed": allowed},
        )
