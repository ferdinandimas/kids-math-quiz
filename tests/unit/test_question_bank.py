"""Characterize the deterministic Math and General Knowledge question banks."""

import re
from collections import Counter

import pytest

from app.domain.question_bank import (
    KNOWLEDGE_QUESTION_SETS,
    MATH_BANK_SPECS,
    OPTION_IDS,
    build_daily_knowledge_bank,
    build_daily_math_bank,
    build_knowledge_bank,
    build_math_bank,
    difficulty_from_question,
    make_math_question,
)

PROMPT = re.compile(r"^(\d+) ([+\-*/]) (\d+) = \?$")
DAY = "2026-11-21"
V1, V2 = MATH_BANK_SPECS


def parse(question: dict) -> tuple[int, str, int]:
    left, operation, right = PROMPT.match(question["prompt"]).groups()
    return int(left), operation, int(right)


def all_daily_banks():
    for spec, child in ((V1, "alleia"), (V2, "althafandra")):
        yield spec, build_daily_math_bank(spec, DAY, child)


@pytest.mark.parametrize("spec", MATH_BANK_SPECS, ids=["v1", "v2"])
def test_base_math_bank_is_deterministic_with_400_unique_questions(spec):
    bank = build_math_bank(spec)

    assert len(bank) == 400
    assert len({question["id"] for question in bank}) == 400
    assert len({question["prompt"] for question in bank}) == 400
    assert bank == build_math_bank(spec)
    assert [question["id"] for question in bank[:2]] == [f"v{spec.version}_q0001", f"v{spec.version}_q0002"]


def test_daily_math_bank_is_stable_per_child_and_day_and_changes_across_days():
    first = build_daily_math_bank(V1, DAY, "alleia")

    assert first == build_daily_math_bank(V1, DAY, "alleia")
    assert first != build_daily_math_bank(V1, "2026-11-22", "alleia")
    assert first != build_daily_math_bank(V1, DAY, "althafandra")


@pytest.mark.parametrize("spec, bank", list(all_daily_banks()), ids=["v1", "v2"])
def test_daily_math_bank_has_400_unique_correct_questions(spec, bank):
    assert len(bank) == 400
    assert len({question["prompt"] for question in bank}) == 400
    assert {question["difficulty"] for question in bank} <= {"easy", "medium", "hard"}

    for question in bank:
        left, operation, right = parse(question)
        expected = {"+": left + right, "-": left - right, "*": left * right, "/": left // right if right else None}
        assert question["answer"] == expected[operation], question
        assert question["op"] == {"+": "add", "-": "sub", "*": "mul", "/": "div"}[operation]


@pytest.mark.parametrize("spec, bank", list(all_daily_banks()), ids=["v1", "v2"])
def test_subtraction_is_never_negative(spec, bank):
    subtractions = [question for question in bank if question["op"] == "sub"]

    assert subtractions
    assert all(question["answer"] >= 0 for question in subtractions)


def test_division_is_whole_and_positive():
    divisions = [question for question in build_daily_math_bank(V2, DAY, "althafandra") if question["op"] == "div"]

    assert divisions
    for question in divisions:
        left, _, right = parse(question)
        assert right > 0 and left % right == 0
        assert question["answer"] > 0


def test_bank_versions_use_their_configured_operations():
    v1_ops = Counter(question["op"] for question in build_daily_math_bank(V1, DAY, "alleia"))
    v2_ops = Counter(question["op"] for question in build_daily_math_bank(V2, DAY, "althafandra"))

    assert set(v1_ops) == {"add", "sub"}
    assert set(v2_ops) == {"add", "sub", "mul", "div"}


def test_make_math_question_rejects_non_whole_division():
    with pytest.raises(ValueError):
        make_math_question(2, 1, 7, "/", 2)


@pytest.mark.parametrize(
    "left, operation, right, expected",
    [
        (9, "+", 9, "easy"),
        (20, "+", 10, "medium"),
        (21, "+", 10, "hard"),
        (9, "-", 9, "easy"),
        (50, "-", 20, "medium"),
        (51, "-", 20, "hard"),
        (5, "*", 5, "easy"),
        (10, "*", 10, "medium"),
        (11, "*", 10, "hard"),
        (30, "/", 5, "easy"),
        (100, "/", 10, "medium"),
        (101, "/", 10, "hard"),
    ],
)
def test_difficulty_thresholds(left, operation, right, expected):
    assert difficulty_from_question(left, operation, right) == expected


def test_difficulty_rejects_operations_outside_the_bank():
    with pytest.raises(ValueError):
        difficulty_from_question(2, "*", 2, active_operations=frozenset({"+", "-"}))


def test_knowledge_bank_has_200_four_option_questions():
    bank = build_knowledge_bank()

    assert len(bank) == 200
    assert len({question["id"] for question in bank}) == 200
    assert Counter(question["level"] for question in bank) == {"pemula": 65, "menengah": 65, "mahir": 70}
    assert set(Counter(question["subject"] for question in bank).values()) == {40}
    for question in bank:
        assert question["type"] == "knowledge"
        assert [option["id"] for option in question["options"]] == list(OPTION_IDS)
        assert all(option["text"] for option in question["options"])
        assert question["answer"] in OPTION_IDS
        assert question["reward"] == 100


def test_knowledge_question_sets_load_from_json():
    assert sum(len(questions) for questions in KNOWLEDGE_QUESTION_SETS.values()) == 200


def test_daily_knowledge_bank_reorders_without_changing_content():
    template = build_knowledge_bank()
    daily = build_daily_knowledge_bank(template, DAY, "alleia")

    assert daily == build_daily_knowledge_bank(template, DAY, "alleia")
    assert [question["id"] for question in daily] != [question["id"] for question in template]
    assert sorted(daily, key=lambda q: q["id"]) == sorted(template, key=lambda q: q["id"])
    assert daily != build_daily_knowledge_bank(template, DAY, "althafandra")
