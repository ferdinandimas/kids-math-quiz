import secrets
from fastapi import Request, Response
from app import clock, config
from app.config import COOKIE_NAME
from app.db.repo import Repo


def set_session_cookie(response: Response, session_id: str) -> None:
    """The only place the session cookie is written."""
    response.set_cookie(
        COOKIE_NAME,
        session_id,
        max_age=config.SESSION_COOKIE_MAX_AGE,
        path=config.SESSION_COOKIE_PATH,
        secure=config.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )


class SessionService:
    def __init__(self, repo: Repo):
        self.repo = repo

    @staticmethod
    def today_str():
        return clock.today_str()

    @staticmethod
    def now_str():
        return clock.now_str()

    @staticmethod
    def new_session_id():
        return secrets.token_urlsafe(24)

    def get_or_create(self, request: Request, response: Response) -> str:
        sess = request.cookies.get(COOKIE_NAME)

        if not sess:
            sess = self.new_session_id()
            self.repo.insert_session(sess, self.today_str(), self.now_str())
            set_session_cookie(response, sess)
            return sess

        row = self.repo.get_session(sess)
        if not row:
            self.repo.insert_session(sess, self.today_str(), self.now_str())
            set_session_cookie(response, sess)
            return sess

        if row["day"] != self.today_str():
            self.repo.update_session_reset_daily(sess, self.today_str())

        return sess

    def require_child(self, session_id: str):
        row = self.repo.get_session(session_id)
        return row and row.get("child")

    def selected_child(self, request: Request) -> str | None:
        """The child this browser chose through /home/{child}, read from the server-side session.

        Read-only: it never creates a session, sets a cookie, or runs the legacy daily reset, so
        KidQuest requests leave legacy session state untouched.
        """
        session_id = request.cookies.get(COOKIE_NAME)
        row = self.repo.get_session(session_id) if session_id else None
        child = row and row.get("child")
        return child if child in config.CHILDREN else None

    def set_child(self, session_id: str, child: str):
        self.repo.set_child(session_id, child)

    def get_stats(self, session_id: str):
        return self.repo.get_session(session_id)

    def get_current_qid(self, session_id: str, child: str, quiz_type: str):
        return self.repo.get_profile_current_qid(session_id, child, quiz_type)

    def set_current_qid(self, session_id: str, qid, quiz_type: str | None = None, child: str | None = None):
        self.repo.set_current_qid(session_id, qid, quiz_type, child)

