"""Shared helpers for the legacy characterization suite."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app import clock as app_clock
from app.clock import Clock
from app.config import COOKIE_NAME, get_db_path
from app.db.repo import Repo

JAKARTA = ZoneInfo("Asia/Jakarta")

# 10:00 in Jakarta, 03:00 UTC: far from either day boundary.
DEFAULT_INSTANT = datetime(2026, 11, 21, 10, 0, tzinfo=JAKARTA)
DEFAULT_DAY = "2026-11-21"

LEGACY_TABLES = (
    "sessions",
    "child_daily",
    "served_questions",
    "daily_question_banks",
    "session_current_questions",
)


class FrozenClock(Clock):
    """An application clock stopped at one absolute instant (APP_TIMEZONE by default)."""

    def __init__(self, instant: datetime = DEFAULT_INSTANT, timezone_name: str = "Asia/Jakarta"):
        super().__init__(timezone_name)
        self.instant = instant.astimezone(timezone.utc)

    def now(self) -> datetime:
        return self.instant.astimezone(self.timezone)

    def set(self, instant: datetime) -> None:
        self.instant = instant.astimezone(timezone.utc)

    def advance(self, **delta: float) -> None:
        self.instant += timedelta(**delta)

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(app_clock, "_clock", self)


def query(sql: str, params: tuple = ()) -> list[dict]:
    """Read from the database the app under test is using."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute(sql, params)]
    finally:
        conn.close()


def execute(sql: str, params: tuple = ()) -> None:
    conn = sqlite3.connect(get_db_path())
    try:
        with conn:
            conn.execute(sql, params)
    finally:
        conn.close()


def table_counts() -> dict[str, int]:
    return {table: query(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"] for table in LEGACY_TABLES}


def daily_row(child: str, day: str = DEFAULT_DAY) -> dict | None:
    rows = Repo().select_daily_range(child, day, day)
    return rows[0] if rows else None


def session_id(client: TestClient) -> str:
    return client.cookies[COOKIE_NAME]


def select_child(client: TestClient, child: str) -> None:
    response = client.get(f"/home/{child}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/quiz"


def fetch_question(client: TestClient, quiz_type: str = "math") -> dict:
    response = client.get("/api/question", params={"quiz_type": quiz_type})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ok"] is True, payload
    return payload


def stored_question(child: str, quiz_type: str, qid: str, day: str = DEFAULT_DAY) -> dict:
    bank = Repo().get_daily_question_bank(child, day, quiz_type)
    return next(question for question in bank if question["id"] == qid)


def correct_answer(child: str, quiz_type: str, qid: str, day: str = DEFAULT_DAY) -> str:
    return str(stored_question(child, quiz_type, qid, day)["answer"])


def wrong_answer(child: str, quiz_type: str, qid: str, day: str = DEFAULT_DAY) -> str:
    right = correct_answer(child, quiz_type, qid, day)
    if quiz_type == "knowledge":
        return next(option for option in "ABCD" if option != right)
    return str(int(right) + 1)


def submit(client: TestClient, qid: str, answer: str, quiz_type: str = "math"):
    return client.post("/api/answer", json={"qid": qid, "answer": answer, "quiz_type": quiz_type})


def answer_one(client: TestClient, child: str, quiz_type: str = "math", *, correct: bool = True) -> dict:
    """Serve one question and answer it; returns the answer response body."""
    qid = fetch_question(client, quiz_type)["qid"]
    choose = correct_answer if correct else wrong_answer
    response = submit(client, qid, choose(child, quiz_type, qid), quiz_type)
    assert response.status_code == 200, response.text
    return response.json()
