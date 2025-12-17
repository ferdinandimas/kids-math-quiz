from fastapi import FastAPI
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