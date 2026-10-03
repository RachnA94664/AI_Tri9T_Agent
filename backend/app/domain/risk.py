"""Risk score and level. Derived in code, never stored in the database."""

from app.domain.errors import ValidationError

# Change the thresholds here and nowhere else.
HIGH_THRESHOLD = 15
MEDIUM_THRESHOLD = 8


def _check_scale(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise ValidationError(f"{name} must be a whole number from 1 to 5, got {value!r}")
    return value


def risk_score(severity: int, likelihood: int) -> int:
    return _check_scale("severity", severity) * _check_scale("likelihood", likelihood)


def risk_level(score: int) -> str:
    if score >= HIGH_THRESHOLD:
        return "high"
    if score >= MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def level_for(severity: int, likelihood: int) -> str:
    return risk_level(risk_score(severity, likelihood))
