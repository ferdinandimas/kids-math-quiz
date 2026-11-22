"""KidQuest persistence (Migration 8 tables).

Every method takes an open connection so callers compose them inside one `transaction()`.
"""

import sqlite3

from app.config import CHILDREN
from app.domain.kidquest.content import Catalog
from app.domain.kidquest.theme import DEFAULT_THEME_ID


class KidQuestRepo:
    def initialize_world_in(self, conn: sqlite3.Connection, child: str, catalog: Catalog, now: str) -> bool:
        """Create the child's starter world and quest rows once. Returns True only when created.

        Repeating the call, or racing another request, never duplicates or changes the world.
        """
        if child not in CHILDREN:
            raise ValueError(f"Unknown child {child!r}; KidQuest worlds exist only for {', '.join(CHILDREN)}")
        layout = catalog.layout
        created = conn.execute(
            """
            INSERT OR IGNORE INTO kidquest_worlds(
              child, layout_version, theme_id, theme_manifest_version, width, height, version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (child, layout.layout_id, DEFAULT_THEME_ID, catalog.raw["themes"]["manifest_version"],
             layout.width, layout.height, now, now),
        ).rowcount == 1
        if created:
            conn.executemany(
                """
                INSERT INTO kidquest_child_quests(child, quest_id, quest_version, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [(child, quest.id, quest.version, quest.initial_status.value, now, now) for quest in catalog.quests.values()],
            )
        return created

    def get_world_in(self, conn: sqlite3.Connection, child: str) -> dict | None:
        row = conn.execute("SELECT * FROM kidquest_worlds WHERE child = ?", (child,)).fetchone()
        return dict(row) if row else None

    def get_quest_statuses_in(self, conn: sqlite3.Connection, child: str) -> dict[str, str]:
        rows = conn.execute(
            "SELECT quest_id, status FROM kidquest_child_quests WHERE child = ? ORDER BY quest_id", (child,)
        )
        return {row[0]: row[1] for row in rows}

    def get_quests_in(self, conn: sqlite3.Connection, child: str) -> dict[str, dict]:
        rows = conn.execute(
            "SELECT quest_id, quest_version, status FROM kidquest_child_quests WHERE child = ?", (child,)
        )
        return {row["quest_id"]: dict(row) for row in rows}

    def get_buildings_in(self, conn: sqlite3.Connection, child: str) -> list[dict]:
        rows = conn.execute(
            "SELECT id, type, x, y, rotation FROM kidquest_buildings WHERE child = ? ORDER BY id", (child,)
        )
        return [dict(row) for row in rows]

    def get_paths_in(self, conn: sqlite3.Connection, child: str) -> list[dict]:
        rows = conn.execute(
            "SELECT id, x, y, path_type FROM kidquest_paths WHERE child = ? ORDER BY y, x", (child,)
        )
        return [dict(row) for row in rows]

    def get_resource_balances_in(self, conn: sqlite3.Connection, child: str) -> dict[str, int]:
        rows = conn.execute("SELECT resource_type, balance FROM kidquest_resource_balances WHERE child = ?", (child,))
        return {row[0]: row[1] for row in rows}

    def get_blueprints_in(self, conn: sqlite3.Connection, child: str) -> list[str]:
        rows = conn.execute("SELECT building_type FROM kidquest_blueprints WHERE child = ? ORDER BY building_type", (child,))
        return [row[0] for row in rows]

    def get_active_challenge_in(self, conn: sqlite3.Connection, child: str) -> dict | None:
        row = conn.execute(
            """
            SELECT c.id, c.quest_id,
                   (SELECT COUNT(*) FROM kidquest_attempts a WHERE a.challenge_id = c.id) AS attempt_count
            FROM kidquest_challenges c
            WHERE c.child = ? AND c.status = 'ACTIVE'
            ORDER BY c.issued_at, c.id
            LIMIT 1
            """,
            (child,),
        ).fetchone()
        return dict(row) if row else None

    # Adult overview and scoped reset (KQ-011).

    def adult_overview_in(self, conn: sqlite3.Connection, children: tuple[str, ...] | list[str]) -> list[dict]:
        overview = []
        for child in children:
            world = conn.execute(
                "SELECT theme_id FROM kidquest_worlds WHERE child = ?", (child,)
            ).fetchone()
            quest = conn.execute(
                "SELECT status FROM kidquest_child_quests WHERE child = ? AND quest_id = 'Q001'", (child,)
            ).fetchone()
            attempts = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(hint_count), 0) FROM kidquest_attempts WHERE child = ?", (child,)
            ).fetchone()
            house = conn.execute(
                "SELECT 1 FROM kidquest_buildings WHERE child = ? AND type = 'starter_house' LIMIT 1", (child,)
            ).fetchone()
            overview.append({
                "child": child,
                "world_created": world is not None,
                "quest_status": quest[0] if quest else None,
                "house_built": house is not None,
                "attempt_count": int(attempts[0]),
                "hints_used": int(attempts[1]),
                "theme_id": world[0] if world else None,
            })
        return overview

    def reset_legacy_history_in(self, conn: sqlite3.Connection, child: str) -> dict[str, int]:
        counts = {}
        for table in ("child_daily", "served_questions", "daily_question_banks", "session_current_questions"):
            counts[table] = conn.execute(f"DELETE FROM {table} WHERE child = ?", (child,)).rowcount
        # `sessions` is shared browser state. Keep every row and all counters; clear only active-
        # question columns on sessions currently selecting this child. Other-child sessions are byte-for-byte unchanged.
        counts["sessions_active_questions"] = conn.execute(
            """
            UPDATE sessions SET current_qid = NULL, current_quiz_type = NULL,
              current_math_qid = NULL, current_knowledge_qid = NULL
            WHERE child = ?
            """,
            (child,),
        ).rowcount
        return counts

    def reset_kidquest_progress_in(self, conn: sqlite3.Connection, child: str) -> dict[str, int]:
        # Dependency order matters with PRAGMA foreign_keys=ON. Audit events and adult-session
        # revocations are intentionally excluded from every child reset.
        tables = (
            "kidquest_idempotency",
            "kidquest_attempts",
            "kidquest_challenges",
            "kidquest_resource_ledger",
            "kidquest_resource_balances",
            "kidquest_blueprints",
            "kidquest_daily_usage",
            "kidquest_buildings",
            "kidquest_paths",
            "kidquest_child_quests",
            "kidquest_worlds",
        )
        return {table: conn.execute(f"DELETE FROM {table} WHERE child = ?", (child,)).rowcount for table in tables}

    def get_reset_audit_in(
        self, conn: sqlite3.Connection, child: str, event_type: str, idempotency_key_hash: str
    ) -> dict | None:
        row = conn.execute(
            """
            SELECT request_hash, response_status, response_json
            FROM kidquest_audit_events
            WHERE child = ? AND event_type = ? AND idempotency_key_hash = ?
            """,
            (child, event_type, idempotency_key_hash),
        ).fetchone()
        return dict(row) if row else None

    def insert_reset_audit_in(
        self, conn: sqlite3.Connection, *, child: str, event_type: str, scope: str,
        idempotency_key_hash: str, request_hash: str, response_status: int,
        response_json: str, details_json: str, created_at: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO kidquest_audit_events(
              event_type, child, scope, idempotency_key_hash, request_hash,
              response_status, response_json, details_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_type, child, scope, idempotency_key_hash, request_hash,
             response_status, response_json, details_json, created_at),
        )

    def is_adult_session_revoked_in(self, conn: sqlite3.Connection, nonce_hash: str) -> bool:
        return conn.execute(
            "SELECT 1 FROM kidquest_adult_session_revocations WHERE nonce_hash = ?", (nonce_hash,)
        ).fetchone() is not None

    def revoke_adult_session_in(
        self, conn: sqlite3.Connection, nonce_hash: str, expires_at: int, revoked_at: str
    ) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO kidquest_adult_session_revocations(nonce_hash, expires_at, revoked_at)
            VALUES (?, ?, ?)
            """,
            (nonce_hash, expires_at, revoked_at),
        )

    def set_theme_in(
        self, conn: sqlite3.Connection, child: str, theme_id: str, manifest_version: int, expected_version: int, now: str
    ) -> bool:
        """Change only the theme metadata and bump the world version. False if the version moved on."""
        return conn.execute(
            """
            UPDATE kidquest_worlds
            SET theme_id = ?, theme_manifest_version = ?, version = version + 1, updated_at = ?
            WHERE child = ? AND version = ?
            """,
            (theme_id, manifest_version, now, child, expected_version),
        ).rowcount == 1

    # Idempotency: one stored outcome per (child, operation, key).

    def get_idempotency_in(self, conn: sqlite3.Connection, child: str, operation: str, key: str) -> dict | None:
        row = conn.execute(
            "SELECT request_hash, status, response_json FROM kidquest_idempotency WHERE child = ? AND operation = ? AND key = ?",
            (child, operation, key),
        ).fetchone()
        return dict(row) if row else None

    def save_idempotency_in(
        self, conn: sqlite3.Connection, child: str, operation: str, key: str, request_hash: str,
        status_code: int, response_json: str, now: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO kidquest_idempotency(child, operation, key, request_hash, status, response_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (child, operation, key, request_hash, str(status_code), response_json, now),
        )

    # Quests and challenges (KQ-008).

    def get_quest_in(self, conn: sqlite3.Connection, child: str, quest_id: str) -> dict | None:
        row = conn.execute(
            "SELECT quest_id, quest_version, status FROM kidquest_child_quests WHERE child = ? AND quest_id = ?",
            (child, quest_id),
        ).fetchone()
        return dict(row) if row else None

    def set_quest_status_in(
        self, conn: sqlite3.Connection, child: str, quest_id: str, expected: str, new: str, now: str
    ) -> bool:
        """Compare-and-set, so a status can only move from the one the caller validated."""
        return conn.execute(
            "UPDATE kidquest_child_quests SET status = ?, updated_at = ? WHERE child = ? AND quest_id = ? AND status = ?",
            (new, now, child, quest_id, expected),
        ).rowcount == 1

    def get_challenge_in(self, conn: sqlite3.Connection, child: str, challenge_id: str) -> dict | None:
        row = conn.execute(
            "SELECT * FROM kidquest_challenges WHERE id = ? AND child = ?", (challenge_id, child)
        ).fetchone()
        return dict(row) if row else None

    def get_active_challenge_for_quest_in(self, conn: sqlite3.Connection, child: str, quest_id: str) -> dict | None:
        row = conn.execute(
            "SELECT * FROM kidquest_challenges WHERE child = ? AND quest_id = ? AND status = 'ACTIVE'",
            (child, quest_id),
        ).fetchone()
        return dict(row) if row else None

    def insert_challenge_in(
        self, conn: sqlite3.Connection, challenge_id: str, child: str, quest_id: str, quest_version: int,
        content_ref: str, now: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO kidquest_challenges(id, child, quest_id, quest_version, content_ref, status, issued_at)
            VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?)
            """,
            (challenge_id, child, quest_id, quest_version, content_ref, now),
        )

    def finish_challenge_in(self, conn: sqlite3.Connection, challenge_id: str, status: str, now: str) -> bool:
        return conn.execute(
            "UPDATE kidquest_challenges SET status = ?, completed_at = ? WHERE id = ? AND status = 'ACTIVE'",
            (status, now, challenge_id),
        ).rowcount == 1

    def count_attempts_in(self, conn: sqlite3.Connection, challenge_id: str) -> int:
        return conn.execute("SELECT COUNT(*) FROM kidquest_attempts WHERE challenge_id = ?", (challenge_id,)).fetchone()[0]

    def insert_attempt_in(
        self, conn: sqlite3.Connection, child: str, attempt_key: str, challenge_id: str, skill_id: str,
        content_version: int, is_correct: bool, hint_count: int, now: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO kidquest_attempts(
              child, attempt_key, challenge_id, skill_id, content_version, is_correct, hint_count, attempted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (child, attempt_key, challenge_id, skill_id, content_version, int(is_correct), hint_count, now),
        )

    # Daily usage (Jakarta day from app/clock.py).

    def get_daily_usage_in(self, conn: sqlite3.Connection, child: str, day: str) -> int:
        row = conn.execute(
            "SELECT accepted_attempts FROM kidquest_daily_usage WHERE child = ? AND day = ?", (child, day)
        ).fetchone()
        return row[0] if row else 0

    def add_daily_usage_in(self, conn: sqlite3.Connection, child: str, day: str, now: str) -> None:
        conn.execute(
            """
            INSERT INTO kidquest_daily_usage(child, day, accepted_attempts, updated_at) VALUES (?, ?, 1, ?)
            ON CONFLICT(child, day) DO UPDATE SET accepted_attempts = accepted_attempts + 1, updated_at = excluded.updated_at
            """,
            (child, day, now),
        )

    # Rewards: the unique ledger source and the blueprint primary key make each grant happen once.

    def credit_resource_in(
        self, conn: sqlite3.Connection, child: str, resource: str, amount: int, source_type: str, source_ref: str, now: str
    ) -> bool:
        credited = conn.execute(
            """
            INSERT OR IGNORE INTO kidquest_resource_ledger(child, resource_type, delta, source_type, source_ref, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (child, resource, amount, source_type, source_ref, now),
        ).rowcount == 1
        if credited:
            conn.execute(
                """
                INSERT INTO kidquest_resource_balances(child, resource_type, balance, updated_at) VALUES (?, ?, ?, ?)
                ON CONFLICT(child, resource_type) DO UPDATE SET balance = balance + excluded.balance, updated_at = excluded.updated_at
                """,
                (child, resource, amount, now),
            )
        return credited

    def grant_blueprint_in(
        self, conn: sqlite3.Connection, child: str, building_type: str, acquisition_type: str, source_ref: str,
        content_version: int, now: str,
    ) -> bool:
        return conn.execute(
            """
            INSERT OR IGNORE INTO kidquest_blueprints(child, building_type, acquisition_type, source_ref, content_version, acquired_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (child, building_type, acquisition_type, source_ref, content_version, now),
        ).rowcount == 1

    # Placement (KQ-009).

    def insert_building_in(
        self, conn: sqlite3.Connection, child: str, building_type: str, x: int, y: int, rotation: int, now: str
    ) -> int:
        """The partial unique index on (child, type) rejects a second core building even if a caller skips validation."""
        return conn.execute(
            """
            INSERT INTO kidquest_buildings(child, type, x, y, rotation, placed_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (child, building_type, x, y, rotation, now, now),
        ).lastrowid

    def get_building_in(self, conn: sqlite3.Connection, child: str, building_id: int) -> dict | None:
        row = conn.execute(
            "SELECT id, type, x, y, rotation FROM kidquest_buildings WHERE id = ? AND child = ?", (building_id, child)
        ).fetchone()
        return dict(row) if row else None

    def debit_resource_in(
        self, conn: sqlite3.Connection, child: str, resource: str, amount: int, source_type: str, source_ref: str, now: str
    ) -> None:
        """Spend exactly once: a repeated source or an overdraft raises, rolling back the transaction."""
        conn.execute(
            """
            INSERT INTO kidquest_resource_ledger(child, resource_type, delta, source_type, source_ref, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (child, resource, -amount, source_type, source_ref, now),
        )
        updated = conn.execute(
            """
            UPDATE kidquest_resource_balances SET balance = balance - ?, updated_at = ?
            WHERE child = ? AND resource_type = ? AND balance >= ?
            """,
            (amount, now, child, resource, amount),
        ).rowcount
        if updated != 1:
            raise sqlite3.IntegrityError(f"{child} cannot spend {amount} {resource}: balance too low")

    def bump_world_version_in(self, conn: sqlite3.Connection, child: str, expected_version: int, now: str) -> bool:
        return conn.execute(
            "UPDATE kidquest_worlds SET version = version + 1, updated_at = ? WHERE child = ? AND version = ?",
            (now, child, expected_version),
        ).rowcount == 1
