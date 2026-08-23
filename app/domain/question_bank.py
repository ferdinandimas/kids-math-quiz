"""Reusable factories for the Math and General Knowledge question banks."""

from __future__ import annotations

import json
import random
from pathlib import Path
from hashlib import sha256
from dataclasses import dataclass
from typing import Callable, Literal, Mapping, Sequence


Operation = Literal["+", "-", "*", "/"]
Difficulty = Literal["easy", "medium", "hard"]
KnowledgeLevel = Literal["pemula", "menengah", "mahir"]
OPTION_IDS = ("A", "B", "C", "D")
MAX_GENERATION_ATTEMPTS = 200_000


def difficulty_from_question(
    left: int,
    operation: Operation,
    right: int,
    *,
    active_operations: frozenset[Operation] | None = None,
) -> Difficulty:
    """Classify Math questions from their bank's enabled operation and operands."""
    if active_operations is not None and operation not in active_operations:
        raise ValueError(f"Operation {operation!r} is not enabled for this Math bank")

    if operation == "+":
        if left <= 9 and right <= 9:
            return "easy"
        if left <= 20 and right <= 10:
            return "medium"
        return "hard"

    if operation == "-":
        if left <= 9 and right <= 9:
            return "easy"
        if left <= 50 and right <= 20:
            return "medium"
        return "hard"

    if operation == "*":
        if left <= 5 and right <= 5:
            return "easy"
        if left <= 10 and right <= 10:
            return "medium"
        return "hard"

    if operation == "/":
        if left <= 30 and right <= 5:
            return "easy"
        if left <= 100 and right <= 10:
            return "medium"
        return "hard"

    raise ValueError("Math operation must be '+', '-', '*', or '/'")


@dataclass(frozen=True)
class MathGenerationRule:
    """A reusable range and quota for generated addition/subtraction questions."""

    quota: int
    left_range: range
    operation: Operation
    right_range: range

    def draw(self, rng: random.Random) -> tuple[int, Operation, int]:
        return (
            rng.randint(self.left_range.start, self.left_range.stop - 1),
            self.operation,
            rng.randint(self.right_range.start, self.right_range.stop - 1),
        )


@dataclass(frozen=True)
class MathBankSpec:
    """Configuration required to generate one deterministic Math question bank."""

    version: int
    seed: int
    target_size: int
    rules: tuple[MathGenerationRule, ...]

    @property
    def active_operations(self) -> frozenset[Operation]:
        """Operators that this specific seed is allowed to generate."""
        return frozenset(rule.operation for rule in self.rules)


MATH_FALLBACK_RULES = (
    MathGenerationRule(45, range(1, 10), "+", range(1, 10)),
    MathGenerationRule(25, range(1, 10), "-", range(1, 10)),
    MathGenerationRule(15, range(10, 21), "+", range(1, 10)),
    MathGenerationRule(15, range(10, 21), "-", range(1, 10)),
)

MATH_BANK_SPECS = (
    MathBankSpec(
        version=1,
        seed=101,
        target_size=400,
        rules=(
            MathGenerationRule(50, range(2, 10), "+", range(2, 10)),
            MathGenerationRule(50, range(2, 10), "-", range(2, 10)),
            MathGenerationRule(100, range(10, 21), "+", range(5, 15)),
            MathGenerationRule(100, range(10, 21), "-", range(5, 15)),
            MathGenerationRule(70, range(20, 61), "-", range(5, 21)),
            MathGenerationRule(30, range(20, 100), "+", range(5, 51)),
        ),
    ),
    MathBankSpec(
        version=2,
        seed=202,
        target_size=400,
        rules=(
            MathGenerationRule(50, range(2, 9), "*", range(2, 9)),
            MathGenerationRule(50, range(2, 9), "/", range(2, 9)),
            MathGenerationRule(10, range(2, 9), "*", range(11, 19)),
            MathGenerationRule(100, range(10, 41), "+", range(5, 21)),
            MathGenerationRule(100, range(10, 41), "-", range(5, 21)),
            MathGenerationRule(30, range(20, 61), "-", range(5, 21)),
            MathGenerationRule(30, range(20, 100), "-", range(5, 51)),
            MathGenerationRule(30, range(20, 100), "+", range(5, 51)),
        ),
    ),
)


def make_math_question(
    version: int,
    index: int,
    left: int,
    operation: Operation,
    right: int,
    *,
    active_operations: frozenset[Operation] | None = None,
) -> dict:
    if operation == "+":
        answer = left + right
    elif operation == "-":
        answer = left - right
    elif operation == "*":
        answer = left * right
    elif operation == "/":
        if right == 0 or left <= 0 or left % right != 0:
            raise ValueError("Division questions must have a positive whole-number answer")
        answer = left // right
    else:  # Defensive guard for custom specs.
        raise ValueError("Math operation must be '+', '-', '*', or '/'")

    return {
        "id": f"v{version}_q{index:04d}",
        "prompt": f"{left} {operation} {right} = ?",
        "answer": answer,
        "difficulty": difficulty_from_question(left, operation, right, active_operations=active_operations),
        "op": {"+": "add", "-": "sub", "*": "mul", "/": "div"}[operation],
    }


def build_math_bank(spec: MathBankSpec) -> list[dict]:
    """Generate one unique, deterministic Math bank from a declarative spec."""
    rng = random.Random(spec.seed)
    seen: set[tuple[int, Operation, int]] = set()
    questions: list[dict] = []

    def add_unique(left: int, operation: Operation, right: int) -> bool:
        key = (left, operation, right)
        is_invalid_subtraction = operation == "-" and left < right
        is_invalid_division = operation == "/" and (
            right == 0 or left <= 0 or left % right != 0 or left // right <= 0
        )
        if key in seen or is_invalid_subtraction or is_invalid_division:
            return False

        seen.add(key)
        questions.append(
            make_math_question(
                spec.version,
                len(questions) + 1,
                left,
                operation,
                right,
                active_operations=spec.active_operations,
            )
        )
        return True

    def fill(count: int, draw: Callable[[], tuple[int, Operation, int]]) -> None:
        attempts = 0
        while count > 0 and attempts < MAX_GENERATION_ATTEMPTS:
            if add_unique(*draw()):
                count -= 1
            attempts += 1

    for rule in spec.rules:
        fill(rule.quota, lambda rule=rule: rule.draw(rng))

    def draw_fallback() -> tuple[int, Operation, int]:
        # Preserve the previous fallback distribution and seeded sequence.
        mode = rng.random()
        if mode < 0.45:
            rule = MATH_FALLBACK_RULES[0]
        elif mode < 0.70:
            rule = MATH_FALLBACK_RULES[1]
        elif mode < 0.85:
            rule = MATH_FALLBACK_RULES[2]
        else:
            rule = MATH_FALLBACK_RULES[3]
        return rule.draw(rng)

    fill(spec.target_size - len(questions), draw_fallback)
    if len(questions) != spec.target_size:
        raise ValueError(f"Unable to generate {spec.target_size} unique Math questions for bank v{spec.version}")
    return questions


def daily_seed(base_seed: int, day: str, scope: str) -> int:
    """Derive a stable daily seed without reusing a profile's base sequence."""
    digest = sha256(f"{base_seed}:{day}:{scope}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def build_daily_math_bank(spec: MathBankSpec, day: str, child: str) -> list[dict]:
    """Generate a new deterministic Math bank for one child and calendar day."""
    daily_spec = MathBankSpec(
        version=spec.version,
        seed=daily_seed(spec.seed, day, f"math:{child}"),
        target_size=spec.target_size,
        rules=spec.rules,
    )
    return build_math_bank(daily_spec)


@dataclass(frozen=True)
class KnowledgeQuestionSpec:
    prompt: str
    options: tuple[str, str, str, str]
    answer: str
    subject: str


KNOWLEDGE_DIFFICULTIES: Mapping[KnowledgeLevel, Difficulty] = {
    "pemula": "easy",
    "menengah": "medium",
    "mahir": "hard",
}

KNOWLEDGE_QUESTION_FILE = Path(__file__).resolve().parents[2] / "static" / "knowledge_questions.json"


def _load_knowledge_question_sets() -> Mapping[KnowledgeLevel, tuple[KnowledgeQuestionSpec, ...]]:
    """Load and validate the shared knowledge bank from its JSON source."""
    try:
        raw = json.loads(KNOWLEDGE_QUESTION_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to load knowledge question bank: {KNOWLEDGE_QUESTION_FILE}") from exc

    records = raw.get("questions") if isinstance(raw, dict) else None
    if raw.get("version") != 1 or not isinstance(records, list) or len(records) != 200:
        raise ValueError("Knowledge question bank must be version 1 and contain exactly 200 questions")

    expected_levels = set(KNOWLEDGE_DIFFICULTIES)
    expected_subjects = {"IPA", "Bahasa Indonesia", "Bahasa Inggris", "PPKN", "Geografi"}
    grouped: dict[KnowledgeLevel, list[KnowledgeQuestionSpec]] = {level: [] for level in expected_levels}
    seen_ids: set[str] = set()
    for record in records:
        level = record.get("level")
        subject = record.get("subject")
        options = record.get("options")
        if level not in expected_levels or subject not in expected_subjects:
            raise ValueError(f"Invalid knowledge question category: {level!r}/{subject!r}")
        if record.get("id") in seen_ids or not isinstance(record.get("id"), str):
            raise ValueError(f"Duplicate or invalid knowledge question id: {record.get('id')!r}")
        seen_ids.add(record["id"])
        if not isinstance(options, list) or len(options) != 4:
            raise ValueError(f"Knowledge question {record.get('id')!r} must have four options")
        option_ids = [option.get("id") for option in options]
        if option_ids != list(OPTION_IDS) or record.get("answer") not in OPTION_IDS:
            raise ValueError(f"Invalid options or answer for knowledge question {record.get('id')!r}")
        grouped[level].append(KnowledgeQuestionSpec(
            prompt=str(record["prompt"]),
            options=tuple(str(option["text"]) for option in options),
            answer=record["answer"],
            subject=subject,
        ))

    expected_level_counts = {"pemula": 65, "menengah": 65, "mahir": 70}
    for level, questions in grouped.items():
        if len(questions) != expected_level_counts[level]:
            raise ValueError(f"Knowledge level {level!r} has an unexpected question count")
    subject_counts = {
        subject: sum(question.subject == subject for questions in grouped.values() for question in questions)
        for subject in expected_subjects
    }
    if set(subject_counts.values()) != {40}:
        raise ValueError("Knowledge question bank must contain 40 questions per subject")
    return {level: tuple(questions) for level, questions in grouped.items()}


KNOWLEDGE_QUESTION_SETS = _load_knowledge_question_sets()


def make_knowledge_question(level: KnowledgeLevel, index: int, spec: KnowledgeQuestionSpec) -> dict:
    if spec.answer not in OPTION_IDS:
        raise ValueError("Knowledge answers must use one of A, B, C, or D")

    return {
        "id": f"knowledge_{level}_{index:03d}",
        "type": "knowledge",
        "level": level,
        "difficulty": KNOWLEDGE_DIFFICULTIES[level],
        "subject": spec.subject,
        "prompt": spec.prompt,
        "options": [
            {"id": option_id, "text": option}
            for option_id, option in zip(OPTION_IDS, spec.options)
        ],
        "answer": spec.answer,
        "reward": 100,
    }


def build_knowledge_bank(
    question_sets: Mapping[KnowledgeLevel, Sequence[KnowledgeQuestionSpec]] = KNOWLEDGE_QUESTION_SETS,
) -> list[dict]:
    """Build a UI-ready multiple-choice bank from the JSON-backed content specs."""
    return [
        make_knowledge_question(level, index, question)
        for level, questions in question_sets.items()
        for index, question in enumerate(questions, start=1)
    ]


def build_daily_knowledge_bank(template_bank: Sequence[dict], day: str, child: str) -> list[dict]:
    """Create a daily randomized ordering while leaving question content unchanged."""
    bank = [question.copy() for question in template_bank]
    random.Random(daily_seed(0, day, f"knowledge:{child}")).shuffle(bank)
    return bank

