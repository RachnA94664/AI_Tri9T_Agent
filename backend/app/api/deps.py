"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_session

# One database session per request (opened before, closed after).
# Tests replace `get_session` with a session on a temporary database.
SessionDep = Annotated[Session, Depends(get_session)]

# Requests that arrive over HTTP always come from the UI. A client cannot claim
# to be an "agent" or "system": the audit log source is set here, on the server.
API_SOURCE = "ui"

# Error responses shown in the /docs page.
ERRORS = {
    404: {"description": "Not found"},
    409: {"description": "Conflict with the current state"},
    422: {"description": "Invalid input"},
}
