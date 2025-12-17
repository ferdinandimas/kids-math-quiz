import secrets
from datetime import date, datetime
from fastapi import Request, Response
from app.config import COOKIE_NAME
from app.db.repo import Repo

class SessionService:
    def __init__(self, repo: Repo):
        self.repo = repo

    @staticmethod
    def today_str():
        return date.today().isoformat()

    @staticmethod
    def now_str():
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def new_session_id():
        return secrets.token_urlsafe(24)

    def get_or_create(self, request: Request, response: Response) -> str:
        sess = request.cookies.get(COOKIE_NAME)

        if not sess:
            sess = self.new_session_id()
            self.repo.insert_session(sess, self.today_str(), self.now_str())
            response.set_cookie(COOKIE_NAME, sess, httponly=True, samesite="lax")
            return sess

        row = self.repo.get_session(sess)
        if not row:
            self.repo.insert_session(sess, self.today_str(), self.now_str())
            response.set_cookie(COOKIE_NAME, sess, httponly=True, samesite="lax")
            return sess

        if row["day"] != self.today_str():
            self.repo.update_session_reset_daily(sess, self.today_str())

        return sess

    def require_child(self, session_id: str):
        row = self.repo.get_session(session_id)
        return row and row.get("child")

    def set_child(self, session_id: str, child: str):
        self.repo.set_child(session_id, child)

    def get_stats(self, session_id: str):
        return self.repo.get_session(session_id)

    def set_current_qid(self, session_id: str, qid):
        self.repo.set_current_qid(session_id, qid)

    def logout(self, session_id: str):
        self.repo.logout_session(session_id)