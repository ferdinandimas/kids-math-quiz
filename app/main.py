from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles

from app.config import APP_TITLE
from app.db.repo import Repo
from app.domain.question_bank import build_banks
from app.services.session_service import SessionService
from app.services.stats_service import StatsService
from app.services.question_service import QuestionService
from app.services.admin_service import AdminService
from app.api.routes import build_router


def create_app() -> FastAPI:
    app = FastAPI(title=APP_TITLE)
    app.mount("/static", StaticFiles(directory="static"), name="static")

    async def _handle_404(request: Request):
        path = request.url.path or ""

        # Keep API sane
        if path.startswith("/api"):
            return JSONResponse({"ok": False, "message": "Not found"}, status_code=404)

        # Don't redirect missing static assets
        if path.startswith("/static"):
            return JSONResponse({"detail": "Not found"}, status_code=404)

        # Redirect unknown pages to /home
        return RedirectResponse(url="/home", status_code=303)

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return await _handle_404(request)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(HTTPException)
    async def fastapi_http_exception_handler(request: Request, exc: HTTPException):
        if exc.status_code == 404:
            return await _handle_404(request)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    repo = Repo()
    repo.init_db()
    repo.ensure_column("sessions", "answered_count", "INTEGER NOT NULL DEFAULT 0")
    repo.ensure_column("child_daily", "answered_count", "INTEGER NOT NULL DEFAULT 0")

    bank_v1, bank_v2, q_by_id = build_banks()

    session_svc = SessionService(repo)
    stats_svc = StatsService(repo)
    q_svc = QuestionService(stats_svc, bank_v1, bank_v2, q_by_id)
    admin_svc = AdminService(repo)

    app.include_router(build_router(session_svc, stats_svc, q_svc, admin_svc))
    return app


app = create_app()