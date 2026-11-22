"""Answer idempotency (AC-04), the Jakarta daily attempt cap (PRD 8.3), and day rollover (AC-08)."""

from datetime import datetime, timezone

import pytest

from app import config
from tests.integration.kidquest.conftest import (
    STATE_URL,
    THEMES_URL,
    active_challenge_id,
    all_kidquest_counts,
    answer,
    change_theme,
    error_code,
    legacy_snapshot,
    open_challenge,
    snapshot,
    start_quest,
    table_rows,
)

# --- Idempotency (AC-04) ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["5", "4"])
def test_replaying_an_answer_key_returns_the_original_response_and_changes_nothing(kid_client, clock, value):
    client = kid_client("alleia")
    challenge_id = active_challenge_id(client)
    first = answer(client, challenge_id, value, "replay-answer-1")
    after_first, counts = snapshot("alleia"), all_kidquest_counts()

    clock.advance(minutes=3)
    replays = [answer(client, challenge_id, value, "replay-answer-1") for _ in range(3)]
    zero_padded = answer(client, challenge_id, f"0{value}", "replay-answer-1")  # Same logical answer.

    assert first.status_code == 200
    for replay in (*replays, zero_padded):
        assert (replay.status_code, replay.content) == (200, first.content)
    assert snapshot("alleia") == after_first and all_kidquest_counts() == counts


def test_reusing_an_answer_key_with_another_answer_is_a_conflict(kid_client):
    client = kid_client("alleia")
    challenge_id = active_challenge_id(client)
    answer(client, challenge_id, "5", "conflict-answer-1")
    before, counts = snapshot("alleia"), all_kidquest_counts()

    for response in (answer(client, challenge_id, "4", "conflict-answer-1"),
                     answer(client, challenge_id, "5", "conflict-answer-1", hint_count=1)):
        assert response.status_code == 409 and error_code(response) == "IDEMPOTENCY_CONFLICT"
    assert snapshot("alleia") == before and all_kidquest_counts() == counts


def test_keys_are_scoped_per_operation_and_child(kid_client):
    alleia, altha = kid_client("alleia"), kid_client("althafandra")

    responses = [start_quest(alleia, "shared-key-1"), open_challenge(alleia, "shared-key-1"),
                 change_theme(alleia, "city", 1, "shared-key-1"), start_quest(altha, "shared-key-1")]

    assert [response.status_code for response in responses] == [200, 200, 200, 200]
    operations = sorted((row["child"], row["operation"]) for row in table_rows("kidquest_idempotency"))
    assert operations == [("alleia", "quest.challenge"), ("alleia", "quest.start"), ("alleia", "theme.change"),
                          ("althafandra", "quest.start")]


def test_a_start_key_replays_its_original_response(kid_client):
    client = kid_client("alleia")
    first = start_quest(client, "start-replay-1")
    challenge_id = active_challenge_id(client)
    answer(client, challenge_id, "4", "start-replay-2")

    assert start_quest(client, "start-replay-1").content == first.content  # Still the IN_PROGRESS response.
    assert start_quest(client, "start-replay-3").json()["quest"]["status"] == "READY_TO_BUILD"


# --- Daily cap (PRD 8.3) ---------------------------------------------------------------------------


@pytest.fixture
def limit_three(monkeypatch):
    monkeypatch.setattr(config, "KIDQUEST_DAILY_ATTEMPT_LIMIT", 3)


def test_the_cap_blocks_new_attempts_but_replays_and_world_inspection_work(kid_client, limit_three):
    client = kid_client("alleia")
    challenge_id = active_challenge_id(client)
    accepted = [answer(client, challenge_id, value, f"cap-key-{n}") for n, value in enumerate(["5", "3", "6"])]
    assert [r.json()["daily_attempts"]["remaining"] for r in accepted] == [2, 1, 0]
    before, counts = snapshot("alleia"), all_kidquest_counts()

    blocked = [answer(client, challenge_id, "4", "cap-key-3"), answer(client, challenge_id, "7", "cap-key-4")]

    for response in blocked:
        assert response.status_code == 429 and error_code(response) == "DAILY_CAP_REACHED"
        assert response.json()["error"]["daily_attempts"] == {
            "day": "2026-11-21", "used": 3, "limit": 3, "remaining": 0, "resets_at": "2026-11-22T00:00:00+07:00"}
    assert snapshot("alleia") == before and all_kidquest_counts() == counts  # Not counted, no reward.
    assert answer(client, challenge_id, "3", "cap-key-1").content == accepted[1].content  # Replay still works.
    state = client.get(STATE_URL)
    assert state.status_code == 200 and state.json()["daily_attempts"]["remaining"] == 0
    assert state.json()["active_challenge"]["attempt_count"] == 3
    resumed = open_challenge(client, "cap-open-1")
    assert resumed.status_code == 200 and resumed.json()["daily_attempts"]["remaining"] == 0
    assert client.get(THEMES_URL).status_code == 200
    assert change_theme(client, "kingdom", 1, "cap-theme-1").status_code == 200
    assert table_rows("kidquest_daily_usage")[0]["accepted_attempts"] == 3


def test_correct_and_wrong_attempts_both_count(kid_client, monkeypatch):
    monkeypatch.setattr(config, "KIDQUEST_DAILY_ATTEMPT_LIMIT", 2)
    client = kid_client("alleia")
    challenge_id = active_challenge_id(client)

    wrong, correct = answer(client, challenge_id, "5", "count-key-1"), answer(client, challenge_id, "4", "count-key-2")

    assert (wrong.json()["daily_attempts"]["used"], correct.json()["daily_attempts"]["used"]) == (1, 2)
    assert correct.json()["daily_attempts"]["remaining"] == 0


def test_the_cap_is_per_child(kid_client, limit_three):
    alleia, altha = kid_client("alleia"), kid_client("althafandra")
    challenge_id = active_challenge_id(alleia)
    for n in range(3):
        answer(alleia, challenge_id, "5", f"per-child-{n}")

    other = answer(altha, active_challenge_id(altha), "5", "per-child-x")

    assert other.status_code == 200 and other.json()["daily_attempts"]["used"] == 1


# --- Day rollover (AC-08) --------------------------------------------------------------------------


def test_usage_resets_at_jakarta_midnight_while_progress_persists(kid_client, clock, limit_three):
    clock.set(datetime(2026, 11, 21, 16, 59, 0, tzinfo=timezone.utc))  # 23:59 in Jakarta.
    client = kid_client("alleia")
    challenge_id = active_challenge_id(client)
    for n in range(3):
        answer(client, challenge_id, "5", f"night-key-{n}")
    refused = answer(client, challenge_id, "4", "night-key-3")
    assert refused.status_code == 429
    assert refused.json()["error"]["daily_attempts"]["resets_at"] == "2026-11-22T00:00:00+07:00"
    progress_before = {k: v for k, v in snapshot("alleia").items() if k != "kidquest_daily_usage"}
    legacy_before = legacy_snapshot()

    clock.set(datetime(2026, 11, 21, 16, 59, 59, tzinfo=timezone.utc))  # Still 23:59:59 in Jakarta (UTC day unchanged after).
    assert answer(client, challenge_id, "4", "night-key-3").status_code == 429
    clock.set(datetime(2026, 11, 21, 17, 0, 1, tzinfo=timezone.utc))  # 00:00:01 Jakarta on the 22nd; still the 21st in UTC.

    state = client.get(STATE_URL).json()
    assert state["daily_attempts"] == {"day": "2026-11-22", "used": 0, "limit": 3, "remaining": 3,
                                       "resets_at": "2026-11-23T00:00:00+07:00"}
    assert {k: v for k, v in snapshot("alleia").items() if k != "kidquest_daily_usage"} == progress_before
    assert legacy_snapshot() == legacy_before
    retried = answer(client, challenge_id, "4", "night-key-3")  # The refused key was not stored, so it works now.
    assert retried.status_code == 200 and retried.json()["correct"] is True
    assert retried.json()["daily_attempts"]["used"] == 1
    usage = {row["day"]: row["accepted_attempts"] for row in table_rows("kidquest_daily_usage", "alleia")}
    assert usage == {"2026-11-21": 3, "2026-11-22": 1}
    assert state["active_challenge"]["attempt_count"] == 3  # Yesterday's attempts are kept.
