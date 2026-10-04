"""Turn errors into HTTP responses with ONE consistent JSON shape:

{"error": {"code": "...", "message": "...", "details": {...}}}
"""

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.errors import (
    Conflict,
    DomainError,
    InvalidTransition,
    NotFound,
    ServiceUnavailable,
    ValidationError,
)

logger = logging.getLogger("app")

# Order matters only for subclasses; none of these inherit from each other.
STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFound: 404,
    ValidationError: 422,
    InvalidTransition: 409,  # the request clashes with the current state
    Conflict: 409,
    ServiceUnavailable: 503,  # e.g. the AI provider is down or no API key is set
}


def error_response(status: int, code: str, message: str, details: dict | None = None):
    body = {"error": {"code": code, "message": message, "details": details or {}}}
    return JSONResponse(status_code=status, content=jsonable_encoder(body))


async def domain_error_handler(_: Request, exc: DomainError):
    status = next((s for cls, s in STATUS_BY_ERROR.items() if isinstance(exc, cls)), 400)
    return error_response(status, exc.code, exc.message, exc.details)


async def request_validation_handler(_: Request, exc: RequestValidationError):
    return error_response(
        422,
        "validation_error",
        "the request is not valid",
        {"errors": jsonable_encoder(exc.errors())},
    )


async def http_error_handler(_: Request, exc: StarletteHTTPException):
    # Unknown URL (404), wrong method (405), ...
    return error_response(exc.status_code, "http_error", str(exc.detail))


async def unhandled_error_handler(_: Request, exc: Exception):
    # Log the real cause for us; tell the client nothing that could leak internals.
    logger.exception("unhandled error")
    return error_response(500, "internal_error", "something went wrong on the server")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
