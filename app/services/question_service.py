import random
from datetime import date
from app.config import DAILY_LIMIT, REWARD_PER_CORRECT
from app.services.stats_service import StatsService

class QuestionService:
    def __init__(self, stats: StatsService, bank_v1: list[dict], bank_v2: list[dict], q_by_id: dict):
        self.stats = stats
        self.bank_v1 = bank_v1
        self.bank_v2 = bank_v2
        self.q_by_id = q_by_id

    @staticmethod
    def today_str():
        return date.today().isoformat()

    @staticmethod
    def split_bank_by_difficulty(bank):
        easy = [q for q in bank if q.get("difficulty") == "easy"]
        med = [q for q in bank if q.get("difficulty") == "medium"]
        hard = [q for q in bank if q.get("difficulty") == "hard"]
        return easy, med, hard

    def pick_adaptive(self, child: str, bank: list[dict]):
        easy, med, hard = self.split_bank_by_difficulty(bank)

        if not bank:
            raise ValueError("Bank soal kosong")

        days = self.stats.last_n_days(7)
        recap = self.stats.get_daily_recap(child, days)

        served7 = int(recap["totals"].get("served_count", 0) or 0)
        acc = int(recap["totals"].get("accuracy_pct", 0) or 0)

        # gating: sebelum 50 soal, pemula
        if served7 < 50:
            return random.choice(easy or med or bank)

        r = random.random()

        if acc < 60:
            return random.choice(easy or bank)

        if acc < 80:
            if r < 0.7:
                return random.choice(easy or bank)
            return random.choice(med or easy or bank)

        if r < 0.1 and hard:
            return random.choice(hard)
        if r < 0.6 and med:
            return random.choice(med)
        return random.choice(easy or med or bank)

    def resolve_bank_for_child(self, child: str):
        if child == "alleia":
            return self.bank_v1, 1
        if child == "althafandra":
            return self.bank_v2, 2
        return None, None

    def check_daily_limit(self, child: str):
        today = self.today_str()
        recap = self.stats.get_daily_recap(child, [today])
        answered_today = int(recap["days"][0].get("answered_count", 0) or 0)
        return answered_today < DAILY_LIMIT, answered_today

    def get_question_payload(self, session_id: str, child: str):
        bank, qver = self.resolve_bank_for_child(child)
        if not bank:
            return {"ok": False, "message": "Akun tidak dikenal."}, 400

        ok, answered_today = self.check_daily_limit(child)
        if not ok:
            return {"ok": False, "message": f"Batas hari ini sudah tercapai ({DAILY_LIMIT} soal). Besok lanjut ya."}, 200

        q = self.pick_adaptive(child, bank)
        qid = q["id"]
        q_full = self.q_by_id.get(qid, q)

        return {"ok": True, "qid": qid, "prompt": q_full["prompt"], "version": qver}, 200

    def evaluate_answer(self, qid: str, ans_str: str):
        q = self.q_by_id.get(qid)
        if not q:
            return None, None, False

        try:
            user_val = int(ans_str) if ans_str.strip() != "" else None
        except ValueError:
            user_val = None

        correct_val = int(q["answer"])
        correct = user_val is not None and user_val == correct_val
        return q, correct_val, correct