"""The FastAPI application.

Run it:  uvicorn app.main:app --reload
Docs:    http://localhost:8000/docs
"""

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.deps import SessionDep
from app.api.errors import register_error_handlers
from app.api.routes_changes import router as changes_router
from app.api.routes_read import router as read_router
from app.api.schemas import HealthOut
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Engineering Knowledge Agent API",
        version="0.1.0",
        description=(
            "Requirements, test cases and risk items. Data is changed only through "
            "propose -> confirm, and every change is written to the audit log."
        ),
    )

    # Browsers only allow the frontend to call us if its address is listed here.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    register_error_handlers(app)
    app.include_router(read_router)
    app.include_router(changes_router)

    @app.get("/health", response_model=HealthOut, tags=["system"])
    def health(session: SessionDep, response: Response):
        """Is the API up, and can it reach the database?"""
        try:
            session.execute(text("SELECT 1"))
        except Exception:
            response.status_code = 503
            return {"status": "degraded", "database": "unreachable"}
        return {"status": "ok", "database": "ok"}

    return app


app = create_app()
