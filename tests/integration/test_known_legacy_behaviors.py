"""Pin legacy behaviors that later tasks change, and the changes already made.

- day boundary is 00:00 Asia/Jakarta, independent of the container TZ   (changed by KQ-002)
- /api/stats exposes both children to any session                       -> adult gate (KQ-011)
- /api/admin/clear accepts the default password outside production      (production refused by KQ-002)
- duplicate concurrent /api/answer counts once; the loser gets 400      (fixed by KQ-003)
"""

import os
import subprocess
import sys
import threading
import time
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

import app.db.repo as repo_module
from app.config import COOKIE_NAME
from app.services.question_service import QuestionService
from app.services.session_service import SessionService
from app.services.stats_service import StatsService
from tests.conftest import REPO_ROOT
from tests.support import (
    JAKARTA,
    LEGACY_TABLES,
    answer_one,
    correct_answer,
    daily_row,
    fetch_question,
    query,
    select_child,
    session_id,
    submit,
    table_counts,
)

SYNC_ERROR = {"ok": False, "message": "Soal tidak sinkron. Klik Next lagi."}


# --- Day boundary ------------------------------------------------------------------------


@pytest.fixture
def process_timezone():
    """Switch the real process TZ (as a container would) and restore it afterwards."""
    if not hasattr(time, "tzset"):
        pytest.skip("time.tzset is POSIX-only")
    original = os.environ.get("TZ")

    def switch(tz: str) -> None:
        os.environ["TZ"] = tz
        time.tzset()

    yield switch
    if original is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = original
    time.tzset()


def test_app_day_ignores_the_process_timezone(process_timezone):
    # UTC+14 and UTC-11 are 25 hours apart: before KQ-002 these produced different days.
    for tz in ("Pacific/Kiritimati", "Pacific/Pago_Pago"):
        process_timezone(tz)
        for _ in range(3):  # Retry if Jakarta midnight passes mid-check.
            expected = datetime.now(JAKARTA).date().isoformat()
            if SessionService.today_str() == expected == QuestionService.today_str():
                break
        else:
            pytest.fail(f"app day changed with TZ={tz}")
        assert StatsService.last_n_days(1) == [expected]


@pytest.mark.parametrize(
    "jakarta_time, app_day",
    [
        (datetime(2026, 11, 21, 23, 59), "2026-11-21"),
        (datetime(2026, 11, 22, 0, 0), "2026-11-22"),  # Rollover at Jakarta midnight.
        (datetime(2026, 11, 22, 6, 59), "2026-11-22"),
        (datetime(2026, 11, 22, 7, 0), "2026-11-22"),  # 00:00 UTC no longer matters.
    ],
)
def test_day_rolls_over_at_midnight_jakarta(clock, client, jakarta_time, app_day):
    clock.set(jakarta_time.replace(tzinfo=JAKARTA))

    assert SessionService.today_str() == app_day
    assert QuestionService.today_str() == app_day
    assert StatsService.last_n_days(1) == [app_day]
    assert client.get("/api/stats").json()["day"] == app_day


def test_question_served_before_rollover_is_rejected_after_it(clock, client):
    clock.set(datetime(2026, 11, 21, 23, 58, tzinfo=JAKARTA))
    select_child(client, "alleia")
    qid = fetch_question(client)["qid"]
    answer = correct_answer("alleia", "math", qid, "2026-11-21")

    clock.advance(minutes=2)  # 00:00 Jakarta: day 2026-11-22.
    response = submit(client, qid, answer)

    assert (response.status_code, response.json()) == (400, SYNC_ERROR)
    # get_or_create reset the session for the new day and dropped its unfinished question.
    assert query("SELECT day, served_count, answered_count, current_qid FROM sessions") == [
        {"day": "2026-11-22", "served_count": 0, "answered_count": 0, "current_qid": None}
    ]
    assert query("SELECT * FROM session_current_questions") == []
    # The previous day's statistics remain; nothing was counted for either day.
    assert daily_row("alleia", "2026-11-21")["served_count"] == 1
    assert daily_row("alleia", "2026-11-21")["answered_count"] == 0
    assert daily_row("alleia", "2026-11-22") is None

    # The next question issuance deletes the previous day's bank and served history.
    new_qid = fetch_question(client)["qid"]
    assert query("SELECT day FROM daily_question_banks") == [{"day": "2026-11-22"}]
    assert query("SELECT day, question_id FROM served_questions") == [{"day": "2026-11-22", "question_id": new_qid}]


# --- Cross-child statistics ----------------------------------------------------------------


def test_api_stats_returns_both_childrens_recap_to_any_session(make_client):
    althafandra = make_client()
    select_child(althafandra, "althafandra")
    answer_one(althafandra, "althafandra", correct=True)

    alleia = make_client()
    select_child(alleia, "alleia")
    payload = alleia.get("/api/stats").json()

    assert payload["child"] == "alleia"
    assert payload["answered_count"] == 0
    assert set(payload["recap7"]["children"]) == {"althafandra", "alleia"}
    assert payload["recap7"]["children"]["althafandra"]["totals"]["answered_count"] == 1

    anonymous = make_client().get("/api/stats").json()
    assert anonymous["ok"] is True and anonymous["child"] is None
    assert anonymous["recap7"]["children"]["althafandra"]["totals"]["correct_count"] == 1


# --- Admin clear ---------------------------------------------------------------------------


def populate_both_children(make_client):
    for child in ("alleia", "althafandra"):
        client = make_client()
        select_child(client, child)
        answer_one(client, child)
        fetch_question(client, "knowledge")  # Leave an unfinished question and a second bank.


@pytest.mark.parametrize("body", [{"password": "wrong"}, {}, None])
def test_admin_clear_rejects_a_wrong_or_missing_password(make_client, client, body):
    populate_both_children(make_client)
    before = table_counts()

    response = client.post("/api/admin/clear", json=body) if body is not None else client.post(
        "/api/admin/clear", content="not json"
    )

    assert (response.status_code, response.json()) == (401, {"ok": False, "message": "Password salah."})
    assert table_counts() == before


@pytest.mark.parametrize("password", ["masukaja", "  masukaja  "])
def test_admin_clear_with_default_password_wipes_both_children_and_vacuums(make_client, client, monkeypatch, password):
    populate_both_children(make_client)
    assert all(count > 0 for count in table_counts().values())

    statements = []
    real_db_conn = repo_module.db_conn

    def traced_db_conn():
        conn = real_db_conn()
        conn.set_trace_callback(statements.append)
        return conn

    monkeypatch.setattr(repo_module, "db_conn", traced_db_conn)

    response = client.post("/api/admin/clear", json={"password": password})

    assert (response.status_code, response.json()) == (200, {"ok": True, "message": "Database sudah dikosongkan."})
    assert table_counts() == {table: 0 for table in LEGACY_TABLES}
    assert "VACUUM" in statements
    assert [row["version"] for row in query("SELECT version FROM schema_migrations")] == list(range(1, 10))
    assert query("PRAGMA freelist_count") == [{"freelist_count": 0}]


@pytest.mark.parametrize("override, expected", [(None, "masukaja"), ("s3cret", "s3cret")])
def test_admin_password_defaults_to_masukaja_when_unset(tmp_path, override, expected):
    env = {key: value for key, value in os.environ.items() if key != "ADMIN_CLEAR_PASSWORD"}
    env["PYTHONPATH"] = str(REPO_ROOT)
    if override:
        env["ADMIN_CLEAR_PASSWORD"] = override

    result = subprocess.run(
        [sys.executable, "-c", "import app.config as c; print(c.ADMIN_CLEAR_PASSWORD)"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == expected


# --- Duplicate answer submissions ----------------------------------------------------------


def test_sequential_duplicate_answer_counts_once(client):
    select_child(client, "alleia")
    qid = fetch_question(client)["qid"]
    answer = correct_answer("alleia", "math", qid)

    first = submit(client, qid, answer)
    second = submit(client, qid, answer)

    assert first.json()["ok"] is True
    assert (second.status_code, second.json()) == (400, SYNC_ERROR)
    row = daily_row("alleia")
    assert (row["answered_count"], row["correct_count"], row["earned"]) == (1, 1, 50)


def race_duplicate_answers(app, client, monkeypatch):
    """Submit the same answer twice concurrently from one session; return responses and today's row."""
    select_child(client, "alleia")
    qid = fetch_question(client)["qid"]
    answer = correct_answer("alleia", "math", qid)
    sid = session_id(client)

    # Hold both requests just after they pass the active-question check, then release them together.
    barrier = threading.Barrier(2, timeout=5)
    real_evaluate = QuestionService.evaluate_answer

    def evaluate_after_both_arrive(self, *args, **kwargs):
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            pass  # Only one request reached evaluation: nothing to interleave.
        return real_evaluate(self, *args, **kwargs)

    monkeypatch.setattr(QuestionService, "evaluate_answer", evaluate_after_both_arrive)
    responses = []

    def post_answer():
        # Separate TestClients run separate event loops, so the blocking barrier cannot deadlock.
        duplicate = TestClient(app)
        duplicate.cookies.set(COOKIE_NAME, sid)
        responses.append(submit(duplicate, qid, answer))

    threads = [threading.Thread(target=post_answer) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    return responses, daily_row("alleia")


def test_concurrent_duplicate_answer_counts_once(app, client, monkeypatch):
    """Fixed by KQ-003 (was a strict xfail): the loser finds the question consumed."""
    responses, row = race_duplicate_answers(app, client, monkeypatch)

    assert (row["answered_count"], row["correct_count"], row["earned"]) == (1, 1, 50)
    winner, loser = sorted(responses, key=lambda response: response.status_code)
    assert (winner.status_code, set(winner.json()), winner.json()["correct"]) == (200, {"ok", "correct", "correct_answer"}, True)
    assert (loser.status_code, loser.json()) == (400, SYNC_ERROR)
    assert query("SELECT answered_count, correct_count, earned, current_qid FROM sessions") == [
        {"answered_count": 1, "correct_count": 1, "earned": 50, "current_qid": None}
    ]
    assert query("SELECT * FROM session_current_questions") == []
