"""KQ-003: one accepted /api/answer updates every counter exactly once, atomically."""

import sqlite3
import threading

import pytest
from fastapi.testclient import TestClient

import app.db.repo as repo_module
from app.config import COOKIE_NAME
from app.db.repo import Repo
from app.domain.question_bank import MATH_BANK_SPECS, build_knowledge_bank
from app.services.question_service import QuestionService
from app.services.stats_service import StatsService
from tests.support import (
    DEFAULT_DAY,
    correct_answer,
    daily_row,
    execute,
    fetch_question,
    query,
    select_child,
    session_id,
    submit,
    wrong_answer,
)

SYNC_ERROR = {"ok": False, "message": "Soal tidak sinkron. Klik Next lagi."}
QUOTA_ERROR = {"ok": False, "message": "Sisa kuota hari ini tidak cukup untuk soal ini."}


def snapshot() -> dict:
    """Every row the answer flow may touch."""
    return {
        "sessions": query("SELECT * FROM sessions ORDER BY session_id"),
        "child_daily": query("SELECT * FROM child_daily ORDER BY child, day"),
        "session_current_questions": query("SELECT * FROM session_current_questions ORDER BY session_id, child, quiz_type"),
    }


def same_session_client(app, client) -> TestClient:
    """A separate TestClient (own event loop) carrying the same session cookie."""
    duplicate = TestClient(app)
    duplicate.cookies.set(COOKIE_NAME, session_id(client))
    return duplicate


def post_concurrently(clients_and_bodies) -> list:
    """Release every request at the same moment from its own thread; return responses in order."""
    start = threading.Barrier(len(clients_and_bodies), timeout=10)
    responses = [None] * len(clients_and_bodies)

    def worker(index, client, body):
        start.wait()
        responses[index] = client.post("/api/answer", json=body)

    threads = [
        threading.Thread(target=worker, args=(index, client, body))
        for index, (client, body) in enumerate(clients_and_bodies)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return responses


# --- Concurrency -------------------------------------------------------------------------------


def test_two_threads_with_one_cookie_on_the_real_route_count_each_question_once(app, client):
    select_child(client, "alleia")
    rounds = 15

    for round_number in range(1, rounds + 1):
        qid = fetch_question(client)["qid"]
        body = {"qid": qid, "answer": correct_answer("alleia", "math", qid), "quiz_type": "math"}

        responses = post_concurrently([(same_session_client(app, client), body), (same_session_client(app, client), body)])

        winner, loser = sorted(responses, key=lambda response: response.status_code)
        assert winner.status_code == 200 and winner.json()["ok"] is True
        assert (loser.status_code, loser.json()) == (400, SYNC_ERROR)
        row = daily_row("alleia")
        assert (row["answered_count"], row["correct_count"], row["earned"]) == (round_number, round_number, 50 * round_number)

    assert query("SELECT answered_count, correct_count, earned FROM sessions") == [
        {"answered_count": rounds, "correct_count": rounds, "earned": 50 * rounds}
    ]


def test_a_burst_of_duplicate_knowledge_answers_consumes_two_units_once(app, client):
    select_child(client, "althafandra")
    qid = fetch_question(client, "knowledge")["qid"]
    body = {"qid": qid, "answer": correct_answer("althafandra", "knowledge", qid), "quiz_type": "knowledge"}

    responses = post_concurrently([(same_session_client(app, client), body) for _ in range(8)])

    assert sorted(response.status_code for response in responses) == [200] + [400] * 7
    assert all(response.json() == SYNC_ERROR for response in responses if response.status_code == 400)
    row = daily_row("althafandra")
    assert (row["answered_count"], row["correct_count"], row["earned"]) == (2, 1, 100)
    assert query("SELECT * FROM session_current_questions") == []


def test_quota_is_rechecked_inside_the_transaction(app, make_client, monkeypatch):
    """Two sessions of one child race for the last two units; only one answer fits."""
    tablet, phone = make_client(), make_client()
    select_child(tablet, "alleia")
    select_child(phone, "alleia")
    bodies = []
    for device in (tablet, phone):
        qid = fetch_question(device, "knowledge")["qid"]
        bodies.append({"qid": qid, "answer": correct_answer("alleia", "knowledge", qid), "quiz_type": "knowledge"})
    execute("UPDATE child_daily SET answered_count = 398 WHERE child = 'alleia'")

    # Both requests pass the pre-transaction checks before either writes.
    barrier = threading.Barrier(2, timeout=5)
    real_evaluate = QuestionService.evaluate_answer

    def evaluate_after_both_arrive(self, *args, **kwargs):
        barrier.wait()
        return real_evaluate(self, *args, **kwargs)

    monkeypatch.setattr(QuestionService, "evaluate_answer", evaluate_after_both_arrive)
    responses = post_concurrently([(tablet, bodies[0]), (phone, bodies[1])])

    accepted, rejected = sorted(responses, key=lambda response: response.status_code)
    assert accepted.status_code == 200
    assert (rejected.status_code, rejected.json()) == (409, QUOTA_ERROR)
    row = daily_row("alleia")
    assert (row["answered_count"], row["correct_count"], row["earned"]) == (400, 1, 100)
    assert len(query("SELECT * FROM session_current_questions")) == 1  # The rejected question stays active.


# --- Rejections write nothing ----------------------------------------------------------------


def test_quota_rejection_changes_nothing(client):
    select_child(client, "alleia")
    qid = fetch_question(client, "knowledge")["qid"]
    execute("UPDATE child_daily SET answered_count = 399 WHERE child = 'alleia'")
    before = snapshot()

    response = submit(client, qid, correct_answer("alleia", "knowledge", qid), "knowledge")

    assert (response.status_code, response.json()) == (409, QUOTA_ERROR)
    assert snapshot() == before


def test_out_of_sync_rejection_changes_nothing(client):
    select_child(client, "alleia")
    qid = fetch_question(client)["qid"]
    submit(client, qid, correct_answer("alleia", "math", qid))
    before = snapshot()

    response = submit(client, qid, correct_answer("alleia", "math", qid))

    assert (response.status_code, response.json()) == (400, SYNC_ERROR)
    assert snapshot() == before


def test_incorrect_answer_counts_once_and_clears_both_active_question_stores(client):
    select_child(client, "alleia")
    qid = fetch_question(client)["qid"]

    first = submit(client, qid, wrong_answer("alleia", "math", qid))
    second = submit(client, qid, correct_answer("alleia", "math", qid))

    assert first.json()["correct"] is False
    assert (second.status_code, second.json()) == (400, SYNC_ERROR)
    row = daily_row("alleia")
    assert (row["answered_count"], row["correct_count"], row["earned"]) == (1, 0, 0)
    assert query("SELECT answered_count, current_qid, current_math_qid, current_quiz_type FROM sessions") == [
        {"answered_count": 1, "current_qid": None, "current_math_qid": None, "current_quiz_type": None}
    ]
    assert query("SELECT * FROM session_current_questions") == []


# --- Fault injection ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "failing_step",
    [
        "inc_daily_answered_in",  # Right after the first counter update (session answered).
        "inc_daily_correct_earned_in",  # After every other counter update.
        "set_current_qid_in",  # The final active-question clear.
    ],
)
def test_a_failure_mid_transaction_rolls_back_everything(app, client, monkeypatch, failing_step):
    select_child(client, "alleia")
    qid = fetch_question(client)["qid"]
    answer = correct_answer("alleia", "math", qid)
    before = snapshot()
    real_step = getattr(Repo, failing_step)
    calls = []

    def fail_after_running(self, conn, *args, **kwargs):
        real_step(self, conn, *args, **kwargs)  # The write happens, then the request fails.
        calls.append(failing_step)
        raise sqlite3.OperationalError(f"injected failure in {failing_step}")

    monkeypatch.setattr(Repo, failing_step, fail_after_running)
    failing_client = TestClient(app, raise_server_exceptions=False)
    failing_client.cookies.set(COOKIE_NAME, session_id(client))

    response = submit(failing_client, qid, answer)

    assert calls == [failing_step]
    assert response.status_code == 500
    assert snapshot() == before

    monkeypatch.setattr(Repo, failing_step, real_step)
    retry = submit(client, qid, answer)
    assert retry.json()["ok"] is True
    row = daily_row("alleia")
    assert (row["answered_count"], row["correct_count"], row["earned"]) == (1, 1, 50)


def test_all_answer_writes_share_one_connection(client, monkeypatch):
    select_child(client, "alleia")
    qid = fetch_question(client)["qid"]
    connections = {}
    steps = [
        "get_profile_current_qid_in",
        "get_daily_answered_in",
        "upsert_daily_in",
        "inc_session_answered_in",
        "inc_daily_answered_in",
        "inc_session_correct_earned_in",
        "inc_daily_correct_earned_in",
        "set_current_qid_in",
    ]
    for step in steps:
        real = getattr(Repo, step)

        def recorder(self, conn, *args, _real=real, _step=step, **kwargs):
            connections[_step] = (id(conn), conn.in_transaction)
            return _real(self, conn, *args, **kwargs)

        monkeypatch.setattr(Repo, step, recorder)

    assert submit(client, qid, correct_answer("alleia", "math", qid)).json()["ok"] is True

    assert set(connections) == set(steps)
    assert len({conn_id for conn_id, _ in connections.values()}) == 1
    # The active-question and quota reads, and every write, run inside the open transaction.
    assert all(in_tx for _, in_tx in connections.values())


# --- Read-only evaluation -----------------------------------------------------------------------


def test_answer_evaluation_runs_only_reads(client, monkeypatch):
    select_child(client, "alleia")
    qid = fetch_question(client)["qid"]
    statements = []
    real_db_conn = repo_module.db_conn

    def traced_db_conn():
        conn = real_db_conn()
        conn.set_trace_callback(statements.append)
        return conn

    monkeypatch.setattr(repo_module, "db_conn", traced_db_conn)
    service = QuestionService(StatsService(Repo()), {"alleia": MATH_BANK_SPECS[0]}, build_knowledge_bank())

    question, correct_value, correct = service.evaluate_answer(
        "alleia", "math", qid, correct_answer("alleia", "math", qid), DEFAULT_DAY
    )

    assert (question["id"], correct) == (qid, True)
    sql = [statement for statement in statements if not statement.startswith("PRAGMA")]
    assert sql and all(statement.lstrip().upper().startswith("SELECT") for statement in sql)


def test_answering_does_not_clean_up_old_days_but_the_next_issuance_does(client):
    select_child(client, "alleia")
    qid = fetch_question(client)["qid"]
    execute(
        "INSERT INTO served_questions(child, day, quiz_type, question_id) VALUES ('alleia', '2026-11-20', 'math', 'v1_q0001')"
    )

    submit(client, qid, correct_answer("alleia", "math", qid))
    assert query("SELECT day FROM served_questions WHERE day = '2026-11-20'") == [{"day": "2026-11-20"}]

    fetch_question(client)
    assert query("SELECT day FROM served_questions WHERE day = '2026-11-20'") == []


def test_evaluation_regenerates_a_missing_bank_in_memory_without_persisting_it(client):
    select_child(client, "alleia")
    qid = fetch_question(client)["qid"]
    expected = int(correct_answer("alleia", "math", qid))
    execute("DELETE FROM daily_question_banks")

    response = submit(client, qid, str(expected))

    assert response.json() == {"ok": True, "correct": True, "correct_answer": expected}
    assert query("SELECT * FROM daily_question_banks") == []


# --- Repository delegation ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method, args, variant",
    [
        ("get_profile_current_qid", ("s", "alleia", "math"), "get_profile_current_qid_in"),
        ("set_current_qid", ("s", None, "math", "alleia"), "set_current_qid_in"),
        ("upsert_daily", ("alleia", DEFAULT_DAY), "upsert_daily_in"),
        ("inc_session_answered", ("s", 2), "inc_session_answered_in"),
        ("inc_daily_answered", ("alleia", DEFAULT_DAY, 2), "inc_daily_answered_in"),
        ("inc_session_correct_earned", ("s", 50), "inc_session_correct_earned_in"),
        ("inc_daily_correct_earned", ("alleia", DEFAULT_DAY, 50), "inc_daily_correct_earned_in"),
    ],
)
def test_plain_repo_methods_delegate_to_their_connection_variants(app, monkeypatch, method, args, variant):
    seen = []
    monkeypatch.setattr(Repo, variant, lambda self, conn, *a: seen.append((isinstance(conn, sqlite3.Connection), a)))

    getattr(Repo(), method)(*args)

    assert seen == [(True, args)]


def test_plain_repo_methods_still_commit_on_their_own(app):
    repo = Repo()
    repo.insert_session("s1", DEFAULT_DAY, "now")
    repo.set_child("s1", "alleia")
    repo.upsert_daily("alleia", DEFAULT_DAY)
    repo.inc_daily_answered("alleia", DEFAULT_DAY, 2)
    repo.inc_daily_correct_earned("alleia", DEFAULT_DAY, 100)
    repo.inc_session_answered("s1", 2)
    repo.inc_session_correct_earned("s1", 100)
    repo.set_current_qid("s1", "knowledge_mahir_001", "knowledge", "alleia")

    assert repo.get_profile_current_qid("s1", "alleia", "knowledge") == "knowledge_mahir_001"
    row = daily_row("alleia")
    assert (row["answered_count"], row["correct_count"], row["earned"]) == (2, 1, 100)
    assert query("SELECT answered_count, correct_count, earned, current_knowledge_qid FROM sessions") == [
        {"answered_count": 2, "correct_count": 1, "earned": 100, "current_knowledge_qid": "knowledge_mahir_001"}
    ]
