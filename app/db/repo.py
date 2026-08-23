import json

from app.db.sqlite import db_conn
from app.db.migrations import migrate

class Repo:
    def init_db(self):
        conn = db_conn()
        try:
            migrate(conn)
        finally:
            conn.close()

    def clear_database(self):
        conn = db_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions")
        cur.execute("DELETE FROM child_daily")
        cur.execute("DELETE FROM served_questions")
        cur.execute("DELETE FROM daily_question_banks")
        cur.execute("DELETE FROM session_current_questions")
        conn.commit()
        cur.execute("VACUUM")
        conn.commit()
        conn.close()

    # Sessions
    def get_session(self, session_id: str):
        conn = db_conn()
        row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def insert_session(self, session_id: str, day: str, created_at: str):
        conn = db_conn()
        conn.execute(
            """
            INSERT INTO sessions(session_id, child, day, served_count, answered_count, correct_count, earned, current_qid, current_quiz_type, created_at)
            VALUES (?, NULL, ?, 0, 0, 0, 0, NULL, NULL, ?)
            """,
            (session_id, day, created_at),
        )
        conn.commit()
        conn.close()

    def update_session_reset_daily(self, session_id: str, day: str):
        conn = db_conn()
        conn.execute(
            """
            UPDATE sessions
            SET day = ?, served_count = 0, answered_count = 0, correct_count = 0, earned = 0,
                current_qid = NULL, current_quiz_type = NULL,
                current_math_qid = NULL, current_knowledge_qid = NULL
            WHERE session_id = ?
            """,
            (day, session_id),
        )
        conn.execute("DELETE FROM session_current_questions WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

    def set_child(self, session_id: str, child: str):
        conn = db_conn()
        conn.execute("UPDATE sessions SET child = ? WHERE session_id = ?", (child, session_id))
        conn.commit()
        conn.close()

    def get_profile_current_qid(self, session_id: str, child: str, quiz_type: str) -> str | None:
        conn = db_conn()
        row = conn.execute(
            "SELECT question_id FROM session_current_questions WHERE session_id = ? AND child = ? AND quiz_type = ?",
            (session_id, child, quiz_type),
        ).fetchone()
        conn.close()
        return row[0] if row else None

    def set_current_qid(self, session_id: str, qid, quiz_type: str | None = None, child: str | None = None):
        conn = db_conn()
        if child and quiz_type in {"math", "knowledge"}:
            if qid is None:
                conn.execute(
                    "DELETE FROM session_current_questions WHERE session_id = ? AND child = ? AND quiz_type = ?",
                    (session_id, child, quiz_type),
                )
            else:
                conn.execute(
                    "INSERT INTO session_current_questions(session_id, child, quiz_type, question_id) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(session_id, child, quiz_type) DO UPDATE SET question_id = excluded.question_id",
                    (session_id, child, quiz_type, qid),
                )
        if quiz_type in {"math", "knowledge"}:
            column = "current_math_qid" if quiz_type == "math" else "current_knowledge_qid"
            if qid is None:
                conn.execute(f"UPDATE sessions SET {column} = NULL WHERE session_id = ?", (session_id,))
                conn.execute(
                    "UPDATE sessions SET current_qid = NULL, current_quiz_type = NULL "
                    "WHERE session_id = ? AND current_quiz_type = ?",
                    (session_id, quiz_type),
                )
            else:
                conn.execute(
                    f"UPDATE sessions SET {column} = ?, current_qid = ?, current_quiz_type = ? WHERE session_id = ?",
                    (qid, qid, quiz_type, session_id),
                )
        else:
            conn.execute(
                "UPDATE sessions SET current_qid = NULL, current_quiz_type = NULL WHERE session_id = ?",
                (session_id,),
            )
        conn.commit()
        conn.close()

    def inc_session_served(self, session_id: str):
        conn = db_conn()
        conn.execute("UPDATE sessions SET served_count = served_count + 1 WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

    def inc_session_answered(self, session_id: str, amount: int = 1):
        conn = db_conn()
        conn.execute("UPDATE sessions SET answered_count = answered_count + ? WHERE session_id = ?", (amount, session_id))
        conn.commit()
        conn.close()

    def inc_session_correct_earned(self, session_id: str, reward: int):
        conn = db_conn()
        conn.execute(
            """
            UPDATE sessions
            SET correct_count = correct_count + 1,
                earned = earned + ?
            WHERE session_id = ?
            """,
            (reward, session_id),
        )
        conn.commit()
        conn.close()

    # child_daily
    def upsert_daily(self, child: str, day: str):
        conn = db_conn()
        conn.execute(
            """
            INSERT INTO child_daily(child, day, served_count, answered_count, correct_count, earned)
            VALUES (?, ?, 0, 0, 0, 0)
            ON CONFLICT(child, day) DO NOTHING
            """,
            (child, day),
        )
        conn.commit()
        conn.close()

    def inc_daily_served(self, child: str, day: str):
        conn = db_conn()
        conn.execute(
            "UPDATE child_daily SET served_count = served_count + 1 WHERE child = ? AND day = ?",
            (child, day),
        )
        conn.commit()
        conn.close()

    def inc_daily_answered(self, child: str, day: str, amount: int = 1):
        conn = db_conn()
        conn.execute(
            "UPDATE child_daily SET answered_count = answered_count + ? WHERE child = ? AND day = ?",
            (amount, child, day),
        )
        conn.commit()
        conn.close()

    def inc_daily_correct_earned(self, child: str, day: str, reward: int):
        conn = db_conn()
        conn.execute(
            """
            UPDATE child_daily
            SET correct_count = correct_count + 1,
                earned = earned + ?
            WHERE child = ? AND day = ?
            """,
            (reward, child, day),
        )
        conn.commit()
        conn.close()

    def select_daily_range(self, child: str, start_day: str, end_day: str):
        conn = db_conn()
        rows = conn.execute(
            """
            SELECT day, served_count, answered_count, correct_count, earned
            FROM child_daily
            WHERE child = ?
              AND day >= ?
              AND day <= ?
            ORDER BY day ASC
            """,
            (child, start_day, end_day),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # Served questions (per child, quiz type, and day)
    def select_served_question_ids(self, child: str, day: str, quiz_type: str) -> set[str]:
        conn = db_conn()
        rows = conn.execute(
            """
            SELECT question_id
            FROM served_questions
            WHERE child = ? AND day = ? AND quiz_type = ?
            """,
            (child, day, quiz_type),
        ).fetchall()
        conn.close()
        return {row["question_id"] for row in rows}

    def reserve_question(self, child: str, day: str, quiz_type: str, question_id: str) -> bool:
        """Atomically mark a question as shown; False means another request got it first."""
        conn = db_conn()
        try:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO served_questions(child, day, quiz_type, question_id)
                VALUES (?, ?, ?, ?)
                """,
                (child, day, quiz_type, question_id),
            )
            conn.commit()
            return cur.rowcount == 1
        finally:
            conn.close()

    # Persisted daily banks
    def get_daily_question_bank(self, child: str, day: str, quiz_type: str) -> list[dict] | None:
        conn = db_conn()
        row = conn.execute(
            """
            SELECT bank_json
            FROM daily_question_banks
            WHERE child = ? AND day = ? AND quiz_type = ?
            """,
            (child, day, quiz_type),
        ).fetchone()
        conn.close()
        return json.loads(row["bank_json"]) if row else None

    def create_daily_question_bank(self, child: str, day: str, quiz_type: str, bank: list[dict]) -> bool:
        conn = db_conn()
        try:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO daily_question_banks(child, day, quiz_type, bank_json)
                VALUES (?, ?, ?, ?)
                """,
                (child, day, quiz_type, json.dumps(bank, ensure_ascii=False, separators=(",", ":"))),
            )
            conn.commit()
            return cur.rowcount == 1
        finally:
            conn.close()

    def cleanup_expired_question_data(self, current_day: str) -> None:
        """Keep only today's generated banks and duplicate-prevention history."""
        conn = db_conn()
        try:
            conn.execute("DELETE FROM served_questions WHERE day < ?", (current_day,))
            conn.execute("DELETE FROM daily_question_banks WHERE day < ?", (current_day,))
            conn.commit()
        finally:
            conn.close()
