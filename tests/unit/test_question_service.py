"""Characterize QuestionService selection, scoring, quota, and payload rules."""

import random

import pytest

from app.domain.question_bank import MATH_BANK_SPECS, build_knowledge_bank
from app.services.question_service import QuestionService


class StubStats:
    """Stands in for StatsService: fixed seven-day totals and today's answered count."""

    def __init__(self, served7: int = 0, accuracy: int = 0, answered_today: int = 0):
        self.served7 = served7
        self.accuracy = accuracy
        self.answered_today = answered_today

    @staticmethod
    def last_n_days(n):
        return [f"day-{i}" for i in range(n)]

    def get_daily_recap(self, child, days):
        if len(days) == 1:
            return {"days": [{"answered_count": self.answered_today}], "totals": {}}
        return {"days": [], "totals": {"served_count": self.served7, "accuracy_pct": self.accuracy}}


BANK = (
    [{"id": f"e{i}", "difficulty": "easy"} for i in range(10)]
    + [{"id": f"m{i}", "difficulty": "medium"} for i in range(10)]
    + [{"id": f"h{i}", "difficulty": "hard"} for i in range(10)]
)


def service(stats=None) -> QuestionService:
    return QuestionService(
        stats or StubStats(),
        {"alleia": MATH_BANK_SPECS[0], "althafandra": MATH_BANK_SPECS[1]},
        build_knowledge_bank(),
    )


def picked_difficulties(svc: QuestionService, monkeypatch, draws: int = 300) -> set[str]:
    monkeypatch.setattr("app.services.question_service.random", random.Random(7))
    return {svc.pick_adaptive("alleia", BANK)["difficulty"] for _ in range(draws)}


def test_beginners_get_only_easy_questions_before_50_served(monkeypatch):
    assert picked_difficulties(service(StubStats(served7=49, accuracy=100)), monkeypatch) == {"easy"}


def test_low_accuracy_gets_only_easy_questions(monkeypatch):
    assert picked_difficulties(service(StubStats(served7=50, accuracy=59)), monkeypatch) == {"easy"}


def test_mid_accuracy_mixes_easy_and_medium(monkeypatch):
    assert picked_difficulties(service(StubStats(served7=50, accuracy=79)), monkeypatch) == {"easy", "medium"}


def test_high_accuracy_reaches_hard_questions(monkeypatch):
    assert picked_difficulties(service(StubStats(served7=50, accuracy=80)), monkeypatch) == {"easy", "medium", "hard"}


def test_pick_adaptive_falls_back_when_a_difficulty_is_missing(monkeypatch):
    monkeypatch.setattr("app.services.question_service.random", random.Random(7))
    hard_only = [{"id": "h", "difficulty": "hard"}]

    assert service().pick_adaptive("alleia", hard_only)["id"] == "h"


def test_pick_adaptive_rejects_an_empty_bank():
    with pytest.raises(ValueError):
        service().pick_adaptive("alleia", [])


def test_quota_cost_is_one_for_math_and_two_for_knowledge():
    assert QuestionService.quota_cost("math") == 1
    assert QuestionService.quota_cost("knowledge") == 2


@pytest.mark.parametrize(
    "answered, quiz_type, allowed",
    [(399, "math", True), (400, "math", False), (398, "knowledge", True), (399, "knowledge", False)],
)
def test_daily_limit_counts_quota_units(answered, quiz_type, allowed):
    ok, answered_today = service(StubStats(answered_today=answered)).check_daily_limit("alleia", quiz_type)

    assert (ok, answered_today) == (allowed, answered)


def test_math_payload_never_includes_the_answer():
    question = {"id": "v1_q0001", "prompt": "2 + 3 = ?", "answer": 5, "difficulty": "easy", "op": "add"}

    payload = QuestionService._payload_for_question(question, 1, "math")

    assert payload == {"ok": True, "qid": "v1_q0001", "prompt": "2 + 3 = ?", "version": 1, "type": "math"}


def test_knowledge_payload_includes_options_and_reward_but_not_the_answer():
    question = build_knowledge_bank()[0]

    payload = QuestionService._payload_for_question(question, "knowledge", "knowledge")

    assert set(payload) == {"ok", "qid", "prompt", "version", "type", "options", "reward"}
    assert payload["options"] == question["options"]
    assert payload["reward"] == 100
    assert "answer" not in payload


@pytest.mark.parametrize("child, version", [("alleia", 1), ("althafandra", 2)])
def test_build_daily_bank_uses_the_child_bank_version(child, version):
    bank, bank_version = service().build_daily_bank(child, "2026-11-21", "math")

    assert bank_version == version
    assert len(bank) == 400
    assert all(question["id"].startswith(f"v{version}_") for question in bank)


def test_build_daily_bank_for_knowledge_and_unknown_child():
    svc = service()

    knowledge, version = svc.build_daily_bank("alleia", "2026-11-21", "knowledge")
    assert (len(knowledge), version) == (200, "knowledge")
    assert svc.build_daily_bank("someone-else", "2026-11-21", "math") == (None, None)
