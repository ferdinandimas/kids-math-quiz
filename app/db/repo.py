from app.db.sqlite import db_conn

class Repo:
    def init_db(self):
        conn = db_conn()
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
              session_id TEXT PRIMARY KEY,
              child TEXT,
              day TEXT,
              served_count INTEGER NOT NULL DEFAULT 0,
              answered_count INTEGER NOT NULL DEFAULT 0,
              correct_count INTEGER NOT NULL DEFAULT 0,
              earned INTEGER NOT NULL DEFAULT 0,
              current_qid TEXT,
              created_at TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS child_daily (
              child TEXT NOT NULL,
              day TEXT NOT NULL,
              served_count INTEGER NOT NULL DEFAULT 0,
              answered_count INTEGER NOT NULL DEFAULT 0,
              correct_count INTEGER NOT NULL DEFAULT 0,
              earned INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY (child, day)
            )
            """
        )

        conn.commit()
        conn.close()

    def ensure_column(self, table: str, col: str, col_def: str):
        conn = db_conn()
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
            conn.commit()
        conn.close()

    def clear_database(self):
        conn = db_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions")
        cur.execute("DELETE FROM child_daily")
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
            INSERT INTO sessions(session_id, child, day, served_count, answered_count, correct_count, earned, current_qid, created_at)
            VALUES (?, NULL, ?, 0, 0, 0, 0, NULL, ?)
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
            SET day = ?, served_count = 0, answered_count = 0, correct_count = 0, earned = 0, current_qid = NULL
            WHERE session_id = ?
            """,
            (day, session_id),
        )
        conn.commit()
        conn.close()

    def set_child(self, session_id: str, child: str):
        conn = db_conn()
        conn.execute("UPDATE sessions SET child = ? WHERE session_id = ?", (child, session_id))
        conn.commit()
        conn.close()

    def set_current_qid(self, session_id: str, qid):
        conn = db_conn()
        conn.execute("UPDATE sessions SET current_qid = ? WHERE session_id = ?", (qid, session_id))
        conn.commit()
        conn.close()

    def inc_session_served(self, session_id: str):
        conn = db_conn()
        conn.execute("UPDATE sessions SET served_count = served_count + 1 WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

    def inc_session_answered(self, session_id: str):
        conn = db_conn()
        conn.execute("UPDATE sessions SET answered_count = answered_count + 1 WHERE session_id = ?", (session_id,))
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

    def logout_session(self, session_id: str):
        conn = db_conn()
        conn.execute("UPDATE sessions SET child = NULL, current_qid = NULL WHERE session_id = ?", (session_id,))
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

    def inc_daily_answered(self, child: str, day: str):
        conn = db_conn()
        conn.execute(
            "UPDATE child_daily SET answered_count = answered_count + 1 WHERE child = ? AND day = ?",
            (child, day),
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