import random
from datetime import date
from app.config import DAILY_LIMIT
from app.domain.question_bank import MathBankSpec, build_daily_knowledge_bank, build_daily_math_bank
from app.services.stats_service import StatsService

class QuestionService:
    def __init__(
        self,
        stats: StatsService,
        math_specs_by_child: dict[str, MathBankSpec],
        knowledge_bank: list[dict],
    ):
        self.stats = stats
        self.math_specs_by_child = math_specs_by_child
        self.knowledge_bank = knowledge_bank

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

    def build_daily_bank(self, child: str, day: str, quiz_type: str) -> tuple[list[dict] | None, int | str | None]:
        if quiz_type == "knowledge":
            return build_daily_knowledge_bank(self.knowledge_bank, day, child), "knowledge"

        spec = self.math_specs_by_child.get(child)
        if not spec:
            return None, None
        return build_daily_math_bank(spec, day, child), spec.version

    def get_daily_bank(self, child: str, day: str, quiz_type: str) -> tuple[list[dict] | None, int | str | None]:
        self.stats.repo.cleanup_expired_question_data(day)
        bank = self.stats.repo.get_daily_question_bank(child, day, quiz_type)
        if bank is not None:
            version = "knowledge" if quiz_type == "knowledge" else self.math_specs_by_child[child].version
            return bank, version

        generated_bank, version = self.build_daily_bank(child, day, quiz_type)
        if not generated_bank:
            return None, None

        self.stats.repo.create_daily_question_bank(child, day, quiz_type, generated_bank)
        # Another request may have inserted the same daily snapshot first.
        return self.stats.repo.get_daily_question_bank(child, day, quiz_type), version

    @staticmethod
    def quota_cost(quiz_type: str) -> int:
        return 2 if quiz_type == "knowledge" else 1

    def check_daily_limit(self, child: str, quiz_type: str = "math"):
        today = self.today_str()
        recap = self.stats.get_daily_recap(child, [today])
        answered_today = int(recap["days"][0].get("answered_count", 0) or 0)
        cost = self.quota_cost(quiz_type)
        return answered_today + cost <= DAILY_LIMIT, answered_today

    @staticmethod
    def _payload_for_question(question: dict, version: int | str | None, quiz_type: str) -> dict:
        """Build the client payload without reserving or counting a question again."""
        payload = {
            "ok": True,
            "qid": question["id"],
            "prompt": question["prompt"],
            "version": version,
            "type": quiz_type,
        }
        if quiz_type == "knowledge":
            payload["options"] = question["options"]
            payload["reward"] = question["reward"]
        return payload

    def get_existing_question_payload(self, child: str, quiz_type: str, question_id: str):
        """Return an unfinished current question from today's persisted bank, if valid."""
        bank, version = self.get_daily_bank(child, self.today_str(), quiz_type)
        question = next((item for item in bank or [] if item["id"] == question_id), None)
        return self._payload_for_question(question, version, quiz_type) if question else None

    def get_question_payload(self, session_id: str, child: str, quiz_type: str = "math"):
        ok, answered_today = self.check_daily_limit(child, quiz_type)
        if not ok:
            return {"ok": False, "message": f"Batas hari ini sudah tercapai ({DAILY_LIMIT} soal). Besok lanjut ya."}, 200

        today = self.today_str()
        bank, qver = self.get_daily_bank(child, today, quiz_type)
        if not bank:
            return {"ok": False, "message": "Akun tidak dikenal."}, 400

        served_ids = self.stats.repo.select_served_question_ids(child, today, quiz_type)
        available_questions = [question for question in bank if question["id"] not in served_ids]
        if not available_questions:
            return {"ok": False, "message": "Semua soal untuk kuis ini hari ini sudah ditampilkan. Besok lanjut ya."}, 200

        q = self.pick_adaptive(child, available_questions)
        qid = q["id"]

        return self._payload_for_question(q, qver, quiz_type), 200

    def reserve_question(self, child: str, quiz_type: str, question_id: str) -> bool:
        return self.stats.repo.reserve_question(child, self.today_str(), quiz_type, question_id)

    def evaluate_answer(self, child: str, quiz_type: str, qid: str, ans_str: str):
        bank, _ = self.get_daily_bank(child, self.today_str(), quiz_type)
        q = next((question for question in bank or [] if question["id"] == qid), None)
        if not q:
            return None, None, False

        if q.get("type") == "knowledge":
            answer_id = str(q["answer"])
            correct_option = next(option for option in q["options"] if option["id"] == answer_id)
            return q, correct_option["text"], ans_str.upper() == answer_id

        try:
            user_val = int(ans_str) if ans_str.strip() != "" else None
        except ValueError:
            user_val = None

        correct_val = int(q["answer"])
        correct = user_val is not None and user_val == correct_val
        return q, correct_val, correct
