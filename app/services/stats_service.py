from datetime import timedelta
from enum import Enum
from app import clock
from app.db.repo import Repo
from app.db.sqlite import transaction


class AnswerOutcome(Enum):
    ACCEPTED = "accepted"
    OUT_OF_SYNC = "out_of_sync"
    OVER_QUOTA = "over_quota"


class StatsService:
    def __init__(self, repo: Repo):
        self.repo = repo

    @staticmethod
    def last_n_days(n: int):
        end = clock.today()
        return [(end - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]

    def get_daily_recap(self, child: str, days: list[str]):
        rows = self.repo.select_daily_range(child, days[0], days[-1])
        by_day = {r["day"]: r for r in rows}

        out = []
        for d in days:
            r = by_day.get(d, {"day": d, "served_count": 0, "answered_count": 0, "correct_count": 0, "earned": 0})
            served = int(r.get("served_count", 0) or 0)
            answered = int(r.get("answered_count", 0) or 0)
            correct = int(r.get("correct_count", 0) or 0)
            earned = int(r.get("earned", 0) or 0)
            acc = round((correct / answered) * 100) if answered > 0 else 0

            out.append(
                {
                    "day": d,
                    "served_count": served,
                    "answered_count": answered,
                    "correct_count": correct,
                    "earned": earned,
                    "accuracy_pct": acc,
                }
            )

        total_served = sum(x["served_count"] for x in out)
        total_answered = sum(x["answered_count"] for x in out)
        total_correct = sum(x["correct_count"] for x in out)
        total_earned = sum(x["earned"] for x in out)
        total_acc = round((total_correct / total_answered) * 100) if total_answered > 0 else 0

        return {
            "child": child,
            "days": out,
            "totals": {
                "served_count": total_served,
                "answered_count": total_answered,
                "correct_count": total_correct,
                "earned": total_earned,
                "accuracy_pct": total_acc,
            },
        }

    def upsert_daily(self, child: str, day: str):
        self.repo.upsert_daily(child, day)

    def inc_served(self, session_id: str, child: str, day: str):
        self.upsert_daily(child, day)
        self.repo.inc_session_served(session_id)
        self.repo.inc_daily_served(child, day)

    def inc_answered(self, session_id: str, child: str, day: str, amount: int = 1):
        self.upsert_daily(child, day)
        self.repo.inc_session_answered(session_id, amount)
        self.repo.inc_daily_answered(child, day, amount)

    def mark_correct(self, session_id: str, child: str, day: str, reward: int):
        self.upsert_daily(child, day)
        self.repo.inc_session_correct_earned(session_id, reward)
        self.repo.inc_daily_correct_earned(child, day, reward)

    def record_answer(
        self,
        session_id: str,
        child: str,
        quiz_type: str,
        qid: str,
        day: str,
        quota_cost: int,
        daily_limit: int,
        reward: int | None,
    ) -> AnswerOutcome:
        """Consume the active question and update every counter in one transaction.

        `reward` is the amount earned for a correct answer, or None for a wrong one. BEGIN
        IMMEDIATE serializes concurrent submissions: the first consumes the question, and a
        duplicate then finds it cleared and is reported OUT_OF_SYNC. A rejected answer
        (OUT_OF_SYNC or OVER_QUOTA) writes nothing.
        """
        repo = self.repo
        with transaction() as conn:
            if repo.get_profile_current_qid_in(conn, session_id, child, quiz_type) != qid:
                return AnswerOutcome.OUT_OF_SYNC
            if repo.get_daily_answered_in(conn, child, day) + quota_cost > daily_limit:
                return AnswerOutcome.OVER_QUOTA

            repo.upsert_daily_in(conn, child, day)
            repo.inc_session_answered_in(conn, session_id, quota_cost)
            repo.inc_daily_answered_in(conn, child, day, quota_cost)
            if reward is not None:
                repo.inc_session_correct_earned_in(conn, session_id, reward)
                repo.inc_daily_correct_earned_in(conn, child, day, reward)
            repo.set_current_qid_in(conn, session_id, None, quiz_type, child)
        return AnswerOutcome.ACCEPTED
