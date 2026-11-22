"""Per-child reset scope, idempotency, concurrency, audit, rollback, and legacy-clear compatibility."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app import config
from app.db.kidquest_repo import KidQuestRepo
from app.security.adult_session import ADULT_COOKIE_NAME
from app.services.kidquest_adult_service import KidQuestAdultService, RESET_CONFIRMATIONS
from tests.integration.kidquest.conftest import (
    LOGICAL_TABLES,
    STATE_URL,
    seed_progress,
    table_rows,
)
from tests.integration.kidquest.test_adult_gate import PIN, SESSION_URL, adult_app, adult_client, adult_config  # noqa: F401
from tests.support import LEGACY_TABLES, execute, query, select_child


RESET_BASE = "/api/kidquest/adult/children"


def reset(client, child, scope, key="reset-request-key"):
    return client.post(
        f"{RESET_BASE}/{child}/reset",
        json={"scope": scope, "confirm": RESET_CONFIRMATIONS[scope]},
        headers={"Idempotency-Key": key},
    )


def seed_legacy(child: str, session_id: str) -> None:
    execute("INSERT INTO child_daily VALUES (?, '2026-11-20', 2, 2, 1, 50)", (child,))
    execute(
        "INSERT INTO served_questions(child, day, quiz_type, question_id) VALUES (?, '2026-11-21', 'math', ?)",
        (child, f"q-{child}"),
    )
    execute(
        "INSERT INTO daily_question_banks(child, day, quiz_type, bank_json) VALUES (?, '2026-11-21', 'math', ?)",
        (child, f'[{ {"id": f"q-{child}"}!r}]'.replace("'", '"')),
    )
    execute(
        "INSERT INTO session_current_questions VALUES (?, ?, 'math', ?)",
        (session_id, child, f"q-{child}"),
    )
    execute(
        "UPDATE sessions SET served_count=7, answered_count=6, correct_count=5, earned=250, "
        "current_qid=?, current_quiz_type='math', current_math_qid=? WHERE session_id=?",
        (f"q-{child}", f"q-{child}", session_id),
    )


def seed_everything(app) -> dict[str, str]:
    sessions = {}
    for child in config.CHILDREN:
        client = TestClient(app)
        select_child(client, child)
        sessions[child] = client.cookies[config.COOKIE_NAME]
        assert client.get(STATE_URL).status_code == 200
        seed_progress(child)
        execute(
            "INSERT INTO kidquest_idempotency VALUES (?, 'seed', 'seed-key', 'hash', '200', '{}', '2026-11-21')",
            (child,),
        )
        seed_legacy(child, sessions[child])
    return sessions


def child_legacy_snapshot(child: str) -> dict:
    result = {
        table: table_rows(table, child)
        for table in ("child_daily", "served_questions", "daily_question_banks", "session_current_questions")
    }
    result["sessions"] = query("SELECT * FROM sessions WHERE child = ?", (child,))
    return result


def child_kidquest_snapshot(child: str) -> dict:
    return {table: table_rows(table, child) for table in (*LOGICAL_TABLES, "kidquest_idempotency")}


@pytest.mark.parametrize("scope", ["legacy_history", "kidquest_progress", "all_child_data"])
def test_each_reset_scope_changes_only_the_selected_child_and_scope(adult_client, scope):
    seed_everything(adult_client.app)
    other_legacy = child_legacy_snapshot("althafandra")
    other_kidquest = child_kidquest_snapshot("althafandra")
    target_legacy = child_legacy_snapshot("alleia")
    target_kidquest = child_kidquest_snapshot("alleia")

    response = reset(adult_client, "alleia", scope)

    assert response.status_code == 200
    assert child_legacy_snapshot("althafandra") == other_legacy
    assert child_kidquest_snapshot("althafandra") == other_kidquest
    after_legacy = child_legacy_snapshot("alleia")
    after_kidquest = child_kidquest_snapshot("alleia")
    if scope == "kidquest_progress":
        assert after_legacy == target_legacy
    else:
        assert all(not after_legacy[table] for table in LEGACY_TABLES if table != "sessions")
        session = after_legacy["sessions"][0]
        before = target_legacy["sessions"][0]
        assert {key: session[key] for key in ("served_count", "answered_count", "correct_count", "earned")} == {
            key: before[key] for key in ("served_count", "answered_count", "correct_count", "earned")
        }
        assert all(session[key] is None for key in (
            "current_qid", "current_quiz_type", "current_math_qid", "current_knowledge_qid"
        ))
    if scope == "legacy_history":
        assert after_kidquest == target_kidquest
    else:
        assert all(not rows for rows in after_kidquest.values())
        child = TestClient(adult_client.app)
        select_child(child, "alleia")
        fresh = child.get(STATE_URL).json()
        assert fresh["world"]["version"] == 1
        assert fresh["quests"][0]["id"] == "Q001" and fresh["quests"][0]["status"] == "AVAILABLE"

    audit = table_rows("kidquest_audit_events", "alleia")
    assert len(audit) == 1
    assert audit[0]["event_type"] == "child_data_reset" and audit[0]["scope"] == scope
    assert audit[0]["idempotency_key_hash"] != "reset-request-key"
    assert "HAPUS" not in audit[0]["details_json"]


def test_wrong_confirmation_unknown_child_and_idempotency_conflict(adult_client):
    bad = adult_client.post(
        f"{RESET_BASE}/alleia/reset",
        json={"scope": "legacy_history", "confirm": "HAPUS-DUNIA"},
        headers={"Idempotency-Key": "wrong-confirmation"},
    )
    unknown = adult_client.post(
        f"{RESET_BASE}/unknown/reset",
        json={"scope": "legacy_history", "confirm": "HAPUS-KUIS"},
        headers={"Idempotency-Key": "unknown-child-key"},
    )
    first = reset(adult_client, "alleia", "legacy_history", "conflict-key")
    conflict = reset(adult_client, "alleia", "kidquest_progress", "conflict-key")

    assert bad.status_code == 422 and bad.json()["error"]["code"] == "INVALID_CONFIRMATION"
    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "NOT_FOUND"
    assert first.status_code == 200
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_reset_replays_exact_response_from_the_audit_record(adult_client):
    seed_everything(adult_client.app)
    first = reset(adult_client, "alleia", "all_child_data", "replay-reset-key")
    replayed = reset(adult_client, "alleia", "all_child_data", "replay-reset-key")

    assert first.status_code == replayed.status_code == 200
    assert first.content == replayed.content
    assert len(table_rows("kidquest_audit_events", "alleia")) == 1


@pytest.mark.parametrize("run", range(50))
def test_concurrent_reset_replays_once_and_writes_one_audit_event(adult_app, run):
    seed_everything(adult_app)
    login = TestClient(adult_app)
    assert login.post(SESSION_URL, json={"pin": PIN}).status_code == 200
    token = login.cookies[ADULT_COOKIE_NAME]
    clients = [TestClient(adult_app), TestClient(adult_app)]
    for client in clients:
        client.cookies.set(ADULT_COOKIE_NAME, token)
    barrier = threading.Barrier(2)

    def worker(index):
        barrier.wait()
        return reset(clients[index], "alleia", "all_child_data", "concurrent-reset-key")

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(worker, range(2)))

    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].content == responses[1].content
    assert len(table_rows("kidquest_audit_events", "alleia")) == 1


def test_failure_while_writing_audit_rolls_back_every_delete(adult_app):
    seed_everything(adult_app)
    before_legacy = child_legacy_snapshot("alleia")
    before_kidquest = child_kidquest_snapshot("alleia")

    class FailingRepo(KidQuestRepo):
        def insert_reset_audit_in(self, conn, **kwargs):
            raise RuntimeError("injected audit failure")

    service = KidQuestAdultService(FailingRepo())
    with pytest.raises(RuntimeError, match="injected"):
        service.reset_child("alleia", "all_child_data", "HAPUS-SEMUA", "rollback-test-key")

    assert child_legacy_snapshot("alleia") == before_legacy
    assert child_kidquest_snapshot("alleia") == before_kidquest
    assert table_rows("kidquest_audit_events", "alleia") == []


def test_legacy_admin_clear_keeps_all_kidquest_and_audit_rows_and_stats_shape(adult_client):
    seed_everything(adult_client.app)
    reset(adult_client, "alleia", "legacy_history", "audit-before-clear")
    execute(
        "INSERT INTO kidquest_adult_session_revocations VALUES ('nonce-digest', 9999999999, '2026-11-21T10:00:00')"
    )
    kidquest_before = {
        table: table_rows(table)
        for table in (*LOGICAL_TABLES, "kidquest_idempotency", "kidquest_audit_events", "kidquest_adult_session_revocations")
    }
    stats_fields = set(adult_client.get("/api/stats").json())

    response = adult_client.post("/api/admin/clear", json={"password": config.ADMIN_CLEAR_PASSWORD})

    assert response.status_code == 200
    assert response.json() == {"ok": True, "message": "Database sudah dikosongkan."}
    assert all(not table_rows(table) for table in LEGACY_TABLES)
    assert {table: table_rows(table) for table in kidquest_before} == kidquest_before
    assert set(adult_client.get("/api/stats").json()) == stats_fields == {
        "ok", "child", "day", "served_count", "answered_count", "correct_count", "earned", "recap7"
    }
