"""
Risk score and level. Derived in code, never stored in the database."""

from app.domain.errors import ValidationError

# Change the thresholds here and nowhere else.
HIGH_THRESHOLD = 15
MEDIUM_THRESHOLD = 8


def _check_scale(name: str, value: object) -> int:
    """
    Check if the value is a whole number from 1 to 5.

    Args:
        name: The name of the value to check.
        value: The value to check.

    Returns:
        The value if it is a whole number from 1 to 5.

    Raises:
        ValidationError: If the value is not a whole number from 1 to 5.
    """
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise ValidationError(f"{name} must be a whole number from 1 to 5, got {value!r}")
    return value


def risk_score(severity: int, likelihood: int) -> int:
    """
    Calculate the risk score.

    Args:
        severity: The severity of the risk.
        likelihood: The likelihood of the risk.

    Returns:
        The risk score.

    Raises:
        ValidationError: If the severity or likelihood is not a whole number from 1 to 5.
    """
    return _check_scale("severity", severity) * _check_scale("likelihood", likelihood)


def risk_level(score: int) -> str:
    """
    Get the risk level.

    Args:
        score: The risk score.

    Returns:
        The risk level.
    """
    if score >= HIGH_THRESHOLD:
        return "high"
    if score >= MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def level_for(severity: int, likelihood: int) -> str:
    """
    Get the risk level for the given severity and likelihood.

    Args:
        severity: The severity of the risk.
        likelihood: The likelihood of the risk.

    Returns:
        The risk level.

    Raises:
        ValidationError: If the severity or likelihood is not a whole number from 1 to 5.
    """
    return risk_level(risk_score(severity, likelihood))
