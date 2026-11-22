"""Migration 8: additive, idempotent KidQuest tables and their constraints."""

import sqlite3

import pytest

from app.db import migrations
from app.db.migrations import MIGRATIONS, migrate
from app.db.sqlite import db_conn
from app.domain.kidquest.content import CORE_BUILDING_TYPES
from app.domain.kidquest.state import QUEST_STATUS_ORDER
from app.domain.kidquest.theme import THEME_IDS
from tests.conftest import REPO_ROOT

KIDQUEST_TABLES = {
    "kidquest_worlds",
    "kidquest_buildings",
    "kidquest_paths",
    "kidquest_child_quests",
    "kidquest_challenges",
    "kidquest_attempts",
    "kidquest_resource_balances",
    "kidquest_resource_ledger",
    "kidquest_blueprints",
    "kidquest_idempotency",
    "kidquest_daily_usage",
    "kidquest_audit_events",
    "kidquest_adult_session_revocations",
}
LEGACY_TABLES = ("sessions", "child_daily", "served_questions", "daily_question_banks", "session_current_questions",
                 "schema_migrations")
NOW = "2026-11-21T10:00:00"


@pytest.fixture
def conn(db_path):
    """A connection from the app factory, so foreign keys are ON as in production."""
    connection = db_conn()
    yield connection
    connection.close()


@pytest.fixture
def migrated(conn):
    migrate(conn)
    return conn


def tables(conn) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def insert_world(conn, child="alleia", **columns):
    values = {"child": child, "layout_version": "pulau_tunas_v1", "width": 8, "height": 8,
              "created_at": NOW, "updated_at": NOW, **columns}
    conn.execute(
        f"INSERT INTO kidquest_worlds({', '.join(values)}) VALUES ({', '.join('?' * len(values))})",
        tuple(values.values()),
    )


def insert_quest(conn, child="alleia", quest_id="Q001", status="AVAILABLE"):
    conn.execute(
        "INSERT INTO kidquest_child_quests(child, quest_id, quest_version, status, created_at, updated_at) "
        "VALUES (?, ?, 1, ?, ?, ?)",
        (child, quest_id, status, NOW, NOW),
    )


def insert_building(conn, child="alleia", building_type="starter_house", x=1, y=1, rotation=0):
    conn.execute(
        "INSERT INTO kidquest_buildings(child, type, x, y, rotation, placed_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (child, building_type, x, y, rotation, NOW, NOW),
    )


def legacy_snapshot(conn) -> dict:
    return {
        "schema": [tuple(row) for row in conn.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE tbl_name NOT LIKE 'kidquest_%' ORDER BY name")],
        "rows": {table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]
                 for table in LEGACY_TABLES if table != "schema_migrations"},
        "migrations": [tuple(row) for row in conn.execute("SELECT version, description FROM schema_migrations ORDER BY version")],
    }


# --- Applying the migration ----------------------------------------------------------------------


def test_migrations_8_and_9_are_additive():
    assert MIGRATIONS[-1][0] == 9 and "audit" in MIGRATIONS[-1][1]
    sql = " ".join((*migrations.KIDQUEST_SCHEMA, *migrations.KIDQUEST_AUDIT_SCHEMA)).upper()
    assert "DROP " not in sql and "ALTER " not in sql and "DELETE " not in sql and "UPDATE " not in sql


def test_empty_database_gets_every_kidquest_table_with_foreign_keys_on(conn):
    assert migrate(conn) == [1, 2, 3, 4, 5, 6, 7, 8, 9]

    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert KIDQUEST_TABLES <= tables(conn)
    assert {name for name in tables(conn) if name.startswith("kidquest_")} == KIDQUEST_TABLES
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_populated_v7_database_keeps_legacy_rows_and_schema_unchanged(conn, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(migrations, "MIGRATIONS", MIGRATIONS[:7])
        assert migrate(conn) == [1, 2, 3, 4, 5, 6, 7]
    with conn:
        conn.execute(
            "INSERT INTO sessions(session_id, child, day, served_count, answered_count, correct_count, earned, current_qid, "
            "created_at, current_quiz_type, current_math_qid) "
            "VALUES ('s1', 'alleia', '2026-11-21', 5, 4, 3, 150, 'v1_q0009', 'now', 'math', 'v1_q0009')"
        )
        conn.execute("INSERT INTO child_daily VALUES ('alleia', '2026-11-21', 5, 4, 3, 150)")
        conn.execute("INSERT INTO child_daily VALUES ('althafandra', '2026-11-20', 9, 9, 8, 400)")
        conn.execute("INSERT INTO served_questions(child, day, quiz_type, question_id, served_at) "
                     "VALUES ('alleia', '2026-11-21', 'math', 'v1_q0009', '2026-11-21 03:00:00')")
        conn.execute("INSERT INTO daily_question_banks(child, day, quiz_type, bank_json, created_at) "
                     "VALUES ('alleia', '2026-11-21', 'math', '[{\"id\":\"v1_q0009\"}]', '2026-11-21 03:00:00')")
        conn.execute("INSERT INTO session_current_questions VALUES ('s1', 'alleia', 'math', 'v1_q0009')")
    before = legacy_snapshot(conn)

    assert migrate(conn) == [8, 9]

    after = legacy_snapshot(conn)
    assert after["schema"] == before["schema"]
    assert after["rows"] == before["rows"]
    assert after["migrations"] == before["migrations"] + [(8, MIGRATIONS[7][1]), (9, MIGRATIONS[8][1])]
    assert KIDQUEST_TABLES <= tables(conn)


def test_rerunning_is_a_no_op(migrated):
    schema = [tuple(row) for row in migrated.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name")]

    assert migrate(migrated) == []
    assert [tuple(row) for row in migrated.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name")] == schema


def test_migration_8_operation_is_safe_to_repeat_with_data_present(migrated):
    insert_world(migrated)
    insert_quest(migrated)
    migrated.commit()
    migrated.execute("DELETE FROM schema_migrations WHERE version = 8")
    migrated.commit()

    assert migrate(migrated) == [8]
    assert migrated.execute("SELECT COUNT(*) FROM kidquest_worlds").fetchone()[0] == 1
    assert migrated.execute("SELECT COUNT(*) FROM kidquest_child_quests").fetchone()[0] == 1


def test_populated_v8_database_gets_migration_9_without_changing_progress(conn, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(migrations, "MIGRATIONS", MIGRATIONS[:8])
        assert migrate(conn) == [1, 2, 3, 4, 5, 6, 7, 8]
    insert_world(conn)
    insert_quest(conn)
    conn.commit()
    before = [tuple(row) for row in conn.execute("SELECT * FROM kidquest_worlds")]

    assert migrate(conn) == [9]

    assert [tuple(row) for row in conn.execute("SELECT * FROM kidquest_worlds")] == before
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert {"kidquest_audit_events", "kidquest_adult_session_revocations"} <= tables(conn)


def test_migration_9_operation_is_safe_to_repeat_with_data_present(migrated):
    migrated.execute(
        "INSERT INTO kidquest_audit_events(event_type, child, scope, idempotency_key_hash, request_hash, "
        "response_status, response_json, details_json, created_at) VALUES "
        "('child_data_reset', 'alleia', 'legacy_history', 'keyhash', 'requesthash', 200, '{}', '{}', ?)",
        (NOW,),
    )
    migrated.execute("DELETE FROM schema_migrations WHERE version = 9")
    migrated.commit()

    assert migrate(migrated) == [9]
    assert migrated.execute("SELECT COUNT(*) FROM kidquest_audit_events").fetchone()[0] == 1


def test_no_economy_tables_yet(migrated):
    assert not [name for name in tables(migrated) if any(word in name for word in ("wallet", "cashout", "xp", "supply", "income"))]


def test_migration_reads_no_content_files():
    source = (REPO_ROOT / "app" / "db" / "migrations.py").read_text(encoding="utf-8")

    for forbidden in ("import json", "open(", "read_text", "CONTENT_DIR", "app.domain", "load_catalog"):
        assert forbidden not in source


# --- Constraints -----------------------------------------------------------------------------------


def test_world_theme_defaults_and_accepts_exactly_the_supported_ids(migrated):
    insert_world(migrated, "alleia")
    assert tuple(migrated.execute("SELECT theme_id, version FROM kidquest_worlds").fetchone()) == ("perkampungan", 1)

    for theme_id in THEME_IDS:
        migrated.execute("UPDATE kidquest_worlds SET theme_id = ? WHERE child = 'alleia'", (theme_id,))
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        migrated.execute("UPDATE kidquest_worlds SET theme_id = 'space' WHERE child = 'alleia'")


def test_one_world_per_child(migrated):
    insert_world(migrated, "alleia")
    with pytest.raises(sqlite3.IntegrityError):
        insert_world(migrated, "alleia")


@pytest.mark.parametrize("building_type", CORE_BUILDING_TYPES)
def test_each_core_building_type_is_unique_per_child(migrated, building_type):
    insert_world(migrated, "alleia")
    insert_world(migrated, "althafandra")
    insert_building(migrated, "alleia", building_type)
    insert_building(migrated, "althafandra", building_type, x=3)  # Other child: allowed.

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        insert_building(migrated, "alleia", building_type, x=5)


def test_non_core_types_are_not_limited_by_the_core_index(migrated):
    insert_world(migrated)
    insert_building(migrated, building_type="future_fountain", x=1)
    insert_building(migrated, building_type="future_fountain", x=4)


@pytest.mark.parametrize("column, value", [("x", -1), ("y", -1), ("rotation", 45)])
def test_building_coordinates_and_rotation_are_checked(migrated, column, value):
    insert_world(migrated)
    kwargs = {"x": 1, "y": 1, "rotation": 0, column: value}
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        insert_building(migrated, **kwargs)


def test_paths_are_unique_per_cell_and_child(migrated):
    insert_world(migrated, "alleia")
    insert_world(migrated, "althafandra")
    statement = "INSERT INTO kidquest_paths(child, x, y, created_at) VALUES (?, 2, 3, ?)"
    migrated.execute(statement, ("alleia", NOW))
    migrated.execute(statement, ("althafandra", NOW))

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        migrated.execute(statement, ("alleia", NOW))
    assert migrated.execute("SELECT path_type FROM kidquest_paths LIMIT 1").fetchone()[0] == "basic_road"


def test_quest_status_check_matches_the_state_machine(migrated):
    insert_world(migrated)
    for index, status in enumerate(QUEST_STATUS_ORDER):
        insert_quest(migrated, quest_id=f"Q00{index + 1}", status=status.value)

    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        insert_quest(migrated, quest_id="Q009", status="DONE")
    with pytest.raises(sqlite3.IntegrityError):
        insert_quest(migrated, quest_id="Q001")  # (child, quest_id) is unique.


def test_balances_cannot_go_negative(migrated):
    insert_world(migrated)
    migrated.execute("INSERT INTO kidquest_resource_balances VALUES ('alleia', 'wood', 4, ?)", (NOW,))

    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        migrated.execute("UPDATE kidquest_resource_balances SET balance = balance - 5")


def test_ledger_sources_are_unique_and_deltas_nonzero(migrated):
    insert_world(migrated)
    statement = ("INSERT INTO kidquest_resource_ledger(child, resource_type, delta, source_type, source_ref, created_at) "
                 "VALUES ('alleia', 'wood', ?, 'quest_reward', 'Q001', ?)")
    migrated.execute(statement, (4, NOW))

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        migrated.execute(statement, (4, NOW))
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        migrated.execute(statement.replace("'Q001'", "'Q002'"), (0, NOW))


def test_challenges_attempts_and_idempotency_keys(migrated):
    insert_world(migrated)
    insert_quest(migrated)
    challenge = ("INSERT INTO kidquest_challenges(id, child, quest_id, quest_version, content_ref, status, issued_at) "
                 "VALUES (?, 'alleia', 'Q001', 1, 'Q001_C1', ?, ?)")
    migrated.execute(challenge, ("ch_1", "ACTIVE", NOW))
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        migrated.execute(challenge, ("ch_2", "ACTIVE", NOW))  # One active challenge per quest.
    migrated.execute(challenge, ("ch_3", "EXPIRED", NOW))

    attempt = ("INSERT INTO kidquest_attempts(child, attempt_key, challenge_id, skill_id, content_version, is_correct, "
               "hint_count, attempted_at) VALUES ('alleia', ?, 'ch_1', 'SUB_BASIC', 1, ?, 0, ?)")
    migrated.execute(attempt, ("key-1", 0, NOW))
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        migrated.execute(attempt, ("key-1", 1, NOW))
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        migrated.execute(attempt, ("key-2", 2, NOW))

    idempotency = ("INSERT INTO kidquest_idempotency VALUES ('alleia', 'answer', 'k1', 'hash', 'COMPLETED', '{}', ?)")
    migrated.execute(idempotency, (NOW,))
    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute(idempotency, (NOW,))

    migrated.execute("INSERT INTO kidquest_daily_usage VALUES ('alleia', '2026-11-21', 1, ?)", (NOW,))
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        migrated.execute("UPDATE kidquest_daily_usage SET accepted_attempts = -1")


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO kidquest_buildings(child, type, x, y, placed_at, updated_at) VALUES ('nobody', 'park', 0, 0, 'n', 'n')",
        "INSERT INTO kidquest_paths(child, x, y, created_at) VALUES ('nobody', 0, 0, 'n')",
        "INSERT INTO kidquest_child_quests(child, quest_id, quest_version, status, created_at, updated_at) "
        "VALUES ('nobody', 'Q001', 1, 'AVAILABLE', 'n', 'n')",
        "INSERT INTO kidquest_challenges(id, child, quest_id, quest_version, content_ref, status, issued_at) "
        "VALUES ('ch_x', 'alleia', 'Q404', 1, 'c', 'ACTIVE', 'n')",
        "INSERT INTO kidquest_attempts(child, attempt_key, challenge_id, skill_id, content_version, is_correct, attempted_at) "
        "VALUES ('alleia', 'k', 'ch_missing', 'SUB_BASIC', 1, 1, 'n')",
        "INSERT INTO kidquest_resource_ledger(child, resource_type, delta, source_type, source_ref, created_at) "
        "VALUES ('nobody', 'wood', 1, 's', 'r', 'n')",
        "INSERT INTO kidquest_blueprints VALUES ('nobody', 'park', 'quest_reward', 'Q004', 1, 'n')",
    ],
)
def test_foreign_keys_reject_orphans(migrated, statement):
    insert_world(migrated, "alleia")

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        migrated.execute(statement)


def test_buildings_and_paths_hold_no_theme_state(migrated):
    for table in ("kidquest_buildings", "kidquest_paths"):
        columns = {row[1] for row in migrated.execute(f"PRAGMA table_info({table})")}
        assert not {column for column in columns if "theme" in column or "skin" in column or "asset" in column}
