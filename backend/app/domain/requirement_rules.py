"""Rules for changing a requirement. Pure Python: no database, no network."""

from app.domain.enums import PRIORITIES
from app.domain.errors import ValidationError
from app.domain.transitions import ensure_transition

# Only these fields may be changed through a proposed change.
EDITABLE_FIELDS = ("title", "description", "priority", "status")
MAX_TITLE_LENGTH = 200


def validate_patch(current: dict, patch: object) -> dict:
    """Check a proposed change against the requirement's current values.

    Returns only the fields that really change. Raises ValidationError or
    InvalidTransition (never silently ignores bad input).
    """
    if not isinstance(patch, dict) or not patch:
        raise ValidationError("a change must be a non-empty object of field values")

    unknown = sorted(set(patch) - set(EDITABLE_FIELDS))
    if unknown:
        raise ValidationError(
            f"these fields cannot be changed: {unknown}",
            details={"unknown": unknown, "editable": list(EDITABLE_FIELDS)},
        )

    clean: dict = {}
    for field, value in patch.items():
        if field == "title":
            if not isinstance(value, str) or not value.strip():
                raise ValidationError("title must not be empty")
            value = value.strip()
            if len(value) > MAX_TITLE_LENGTH:
                raise ValidationError(f"title must be at most {MAX_TITLE_LENGTH} characters")
        elif field == "description":
            if not isinstance(value, str):
                raise ValidationError("description must be text")
        elif field == "priority":
            if value not in PRIORITIES:
                raise ValidationError(f"priority must be one of {PRIORITIES}, got {value!r}")
        elif field == "status":
            ensure_transition(current["status"], value)

        if value != current[field]:
            clean[field] = value

    if not clean:
        raise ValidationError("this change does not alter anything")
    return clean
