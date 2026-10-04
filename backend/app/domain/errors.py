"""Domain errors: what can go wrong in business rules.

The API layer (Phase 5) maps these to HTTP codes. Keeping them here means the
rules never depend on FastAPI.
"""


class DomainError(Exception):
    """Base class. `code` is a stable machine-readable name."""

    code = "domain_error"

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(DomainError):
    code = "validation_error"


class InvalidTransition(DomainError):
    code = "invalid_transition"


class NotFound(DomainError):
    code = "not_found"


class Conflict(DomainError):
    code = "conflict"


class ServiceUnavailable(DomainError):
    """An outside service (such as the AI provider) cannot be used right now."""

    code = "service_unavailable"
