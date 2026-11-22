from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles

from app import config
from app.config import APP_TITLE, validate_startup_config
from app.db.repo import Repo
from app.domain.kidquest.content import load_catalog as load_kidquest_catalog
from app.domain.question_bank import MATH_BANK_SPECS, build_knowledge_bank
from app.services.session_service import SessionService
from app.services.stats_service import StatsService
from app.services.question_service import QuestionService
from app.services.admin_service import AdminService
from app.api.routes import build_router
from app.api.kidquest_routes import build_kidquest_page_router, build_kidquest_router, kidquest_error_handler
from app.api.kidquest_adult_routes import build_kidquest_adult_router
from app.api.kidquest_logging import KidQuestRequestLoggingMiddleware
from app.services.kidquest_adult_service import KidQuestAdultService
from app.services.kidquest_service import KidQuestError, KidQuestService

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


def create_app() -> FastAPI:
    validate_startup_config()
    app = FastAPI(title=APP_TITLE)
    # KidQuest content is validated only when KidQuest is on, so it can never block the legacy app.
    app.state.kidquest_catalog = load_kidquest_catalog() if config.KIDQUEST_ENABLED else None
    content_version = app.state.kidquest_catalog.content_version if app.state.kidquest_catalog else None
    app.add_middleware(KidQuestRequestLoggingMiddleware, content_version=content_version)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

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

    knowledge_bank = build_knowledge_bank()

    session_svc = SessionService(repo)
    stats_svc = StatsService(repo)
    q_svc = QuestionService(
        stats_svc,
        {"alleia": MATH_BANK_SPECS[0], "althafandra": MATH_BANK_SPECS[1]},
        knowledge_bank,
    )
    admin_svc = AdminService(repo)

    app.include_router(build_router(session_svc, stats_svc, q_svc, admin_svc))

    # KidQuest routes exist only when KidQuest is enabled; disabled, the legacy app is unchanged.
    if app.state.kidquest_catalog is not None:
        app.include_router(build_kidquest_router(KidQuestService(app.state.kidquest_catalog), session_svc))
        if config.adult_dashboard_ready():
            app.include_router(build_kidquest_adult_router(KidQuestAdultService()))
        app.include_router(build_kidquest_page_router(app.state.kidquest_catalog, session_svc))
        app.add_exception_handler(KidQuestError, kidquest_error_handler)
    return app


app = create_app()
