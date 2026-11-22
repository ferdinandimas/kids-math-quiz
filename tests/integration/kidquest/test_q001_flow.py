"""Q001 start, challenge, answer, retry, and reward (PRD 8.1, 9.1, 10.2, 12.1-12.2, 14.1; AC-02/03/07)."""

import pytest
from fastapi.testclient import TestClient

from app.db.kidquest_repo import KidQuestRepo
from tests.integration.kidquest.conftest import (
    STATE_URL,
    active_challenge_id,
    all_kidquest_counts,
    answer,
    error_code,
    legacy_snapshot,
    open_challenge,
    snapshot,
    start_quest,
    table_rows,
)
from tests.support import query

HINTS = [
    "Kita sudah punya 6 kayu. Hitung terus sampai 10. Berapa kali kamu menghitung?",
    "Bayangkan 10 tempat kayu. 6 tempat sudah terisi. Hitung tempat yang masih kosong.",
]
FORBIDDEN_KEYS = {"answer", "correct_answer", "reward", "reward_message", "hints"}


def leaks(value, path="") -> list[str]:
    """Places in a payload that could reveal the answer (4) or the reward before a correct answer."""
    found = []
    if isinstance(value, dict):
        found += [f"{path}.{key}" for key in value if key in FORBIDDEN_KEYS]
        for key, item in value.items():
            found += leaks(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found += leaks(item, f"{path}[{index}]")
    elif isinstance(value, int) and not isinstance(value, bool) and value == 4:
        found.append(path)
    elif isinstance(value, str) and ("4 kayu" in value or value.strip() == "4"):
        found.append(path)
    return found


def quest_status(child: str = "alleia", quest_id: str = "Q001") -> str:
    return query("SELECT status FROM kidquest_child_quests WHERE child = ? AND quest_id = ?", (child, quest_id))[0]["status"]


def reward_rows(child: str = "alleia") -> dict:
    return {
        "ledger": table_rows("kidquest_resource_ledger", child),
        "balances": table_rows("kidquest_resource_balances", child),
        "blueprints": table_rows("kidquest_blueprints", child),
    }


# --- Start and challenge ---------------------------------------------------------------------------


def test_start_moves_q001_forward_once_and_then_resumes(kid_client):
    client = kid_client("alleia")

    first = start_quest(client, "start-key-1")
    again = start_quest(client, "start-key-2")

    for response in (first, again):
        assert response.status_code == 200
        body = response.json()
        assert body["quest"]["status"] == "IN_PROGRESS"
        assert body["next_action"] == {"type": "answer_challenge", "quest_id": "Q001", "challenge_id": None}
    assert quest_status() == "IN_PROGRESS"
    assert table_rows("kidquest_challenges") == []


@pytest.mark.parametrize("quest_id, status, code", [("Q002", 409, "QUEST_LOCKED"), ("Q006", 409, "QUEST_LOCKED"),
                                                     ("Q999", 404, "NOT_FOUND"), ("house", 404, "NOT_FOUND")])
def test_locked_or_unknown_quests_are_refused_without_mutation(kid_client, quest_id, status, code):
    client = kid_client("alleia")
    client.get(STATE_URL)
    before, counts = snapshot("alleia"), all_kidquest_counts()

    for response in (start_quest(client, "locked-key-1", quest_id), open_challenge(client, "locked-key-2", quest_id)):
        assert response.status_code == status and error_code(response) == code

    assert snapshot("alleia") == before and all_kidquest_counts() == counts
    # Refusals are not stored: the same keys still work for a valid request later.
    assert start_quest(client, "locked-key-1").status_code == 200


def test_the_challenge_is_created_once_and_resumed(kid_client):
    client = kid_client("alleia")

    first = open_challenge(client, "open-key-1")  # Also starts the AVAILABLE quest.
    second = open_challenge(client, "open-key-2")
    other_session = open_challenge(kid_client("alleia"), "open-key-3")

    assert first.status_code == 200
    ids = {response.json()["challenge"]["id"] for response in (first, second, other_session)}
    assert len(ids) == 1 and next(iter(ids)).startswith("ch_")
    assert quest_status() == "IN_PROGRESS"
    rows = table_rows("kidquest_challenges")
    assert [(row["quest_id"], row["quest_version"], row["content_ref"], row["status"]) for row in rows] == [
        ("Q001", 1, "Q001#Q001_C1", "ACTIVE")
    ]


def test_challenge_matches_prd_12_1_without_answer_or_reward(kid_client):
    client = kid_client("alleia")

    started, opened = start_quest(client, "leak-key-1").json(), open_challenge(client, "leak-key-2").json()
    state = client.get(STATE_URL).json()
    assert state["active_challenge"]["id"] == opened["challenge"]["id"]
    state_without_map = {k: v for k, v in state.items() if k not in ("world", "theme")}  # Map coordinates may be 4.
    payloads = [started, opened, state_without_map]
    challenge = payloads[1]["challenge"]

    assert {k: challenge[k] for k in ("quest_id", "content_version", "skill_id", "type", "prompt", "visual_context", "attempt_count")} == {
        "quest_id": "Q001", "content_version": 1, "skill_id": "SUB_BASIC", "type": "numeric",
        "prompt": "Kita butuh 10 kayu. Sudah ada 6. Berapa lagi?",
        "visual_context": {"item": "wood", "required": 10, "available": 6}, "attempt_count": 0,
    }
    assert challenge["reward_preview"] == "Hadiah: kayu yang kurang + Cetak biru Rumah" and challenge["hint"] is None
    for payload in payloads:
        assert leaks(payload) == [], payload
    assert "child" not in challenge


# --- Wrong answers (PRD 10.2, AC-03) ------------------------------------------------------------


def test_a_wrong_answer_records_one_attempt_and_keeps_the_challenge(kid_client):
    client = kid_client("alleia")
    challenge_id = active_challenge_id(client)

    response = answer(client, challenge_id, "5", "wrong-key-1")

    assert response.status_code == 200
    body = response.json()
    assert (body["correct"], body["challenge"], body["quest"]["status"]) == (
        False, {"id": challenge_id, "status": "ACTIVE", "attempt_count": 1}, "IN_PROGRESS")
    assert body["hint"] == {"level": 1, "kind": "hint", "text": HINTS[0]}
    assert body["daily_attempts"]["used"] == 1 and body["daily_attempts"]["remaining"] == 19
    assert body["next_action"] == {"type": "answer_challenge", "quest_id": "Q001", "challenge_id": challenge_id}
    assert leaks(body) == []
    attempts = table_rows("kidquest_attempts")
    assert [(a["is_correct"], a["hint_count"], a["skill_id"], a["content_version"], a["attempt_key"]) for a in attempts] == [
        (0, 0, "SUB_BASIC", 1, "wrong-key-1")
    ]
    assert table_rows("kidquest_daily_usage")[0]["accepted_attempts"] == 1
    assert reward_rows() == {"ledger": [], "balances": [], "blueprints": []}
    assert table_rows("kidquest_challenges")[0]["status"] == "ACTIVE" and quest_status() == "IN_PROGRESS"


def test_hints_progress_from_neutral_to_worked_example(kid_client):
    client = kid_client("alleia")
    challenge_id = active_challenge_id(client)

    bodies = [answer(client, challenge_id, value, f"hint-key-{n}", hint_count=9).json() for n, value in enumerate(["5", "3", "6"])]

    assert [body["hint"]["level"] for body in bodies] == [1, 2, 2]
    assert [body["hint"]["kind"] for body in bodies] == ["hint", "worked_example", "worked_example"]
    assert bodies[1]["hint"] == {"level": 2, "kind": "worked_example", "text": HINTS[1],
                                 "visual": {"item": "wood", "required": 10, "available": 6}}
    assert all(leaks(body) == [] for body in bodies)
    # The stored hint count is what the server had shown before each attempt; the client's 9 is ignored.
    assert [a["hint_count"] for a in sorted(table_rows("kidquest_attempts"), key=lambda a: a["id"])] == [0, 1, 2]
    resumed = open_challenge(client, "hint-resume-1").json()["challenge"]
    assert (resumed["attempt_count"], resumed["hint"]["level"]) == (3, 2)
    assert client.get(STATE_URL).json()["active_challenge"] == {"id": challenge_id, "quest_id": "Q001", "attempt_count": 3}


# --- Correct answer -------------------------------------------------------------------------------


def test_correct_answer_after_retries_grants_the_reward_once(kid_client):
    client = kid_client("alleia")
    challenge_id = active_challenge_id(client)
    answer(client, challenge_id, "5", "flow-key-1")

    response = answer(client, challenge_id, "4", "flow-key-2", hint_count=1)

    assert response.status_code == 200
    body = response.json()
    assert body["correct"] is True and "hint" not in body
    assert body["challenge"] == {"id": challenge_id, "status": "COMPLETED", "attempt_count": 2}
    assert body["quest"]["status"] == "READY_TO_BUILD"
    assert body["reward"] == {"resources": {"wood": 4}, "blueprints": ["starter_house"]}
    assert body["reward_message"] == "Hebat! Kamu dapat 4 kayu dan cetak biru Rumah."
    assert body["inventory"] == {"resources": {"wood": 4, "stone": 0}, "blueprints": ["starter_house"]}
    assert body["next_action"] == {"type": "place_building", "quest_id": "Q001", "building_id": "starter_house"}
    rewards = reward_rows()
    assert [(r["resource_type"], r["delta"], r["source_type"], r["source_ref"]) for r in rewards["ledger"]] == [
        ("wood", 4, "quest_reward", "Q001")]
    assert [(r["resource_type"], r["balance"]) for r in rewards["balances"]] == [("wood", 4)]
    assert [(r["building_type"], r["acquisition_type"], r["source_ref"]) for r in rewards["blueprints"]] == [
        ("starter_house", "quest_reward", "Q001")]
    challenge = table_rows("kidquest_challenges")[0]
    assert challenge["status"] == "COMPLETED" and challenge["completed_at"]
    assert quest_status() == "READY_TO_BUILD"  # COMPLETED only after placement (KQ-009).


def test_after_the_reward_the_quest_points_at_building(kid_client):
    client = kid_client("alleia")
    challenge_id = active_challenge_id(client)
    answer(client, challenge_id, "4", "done-key-1")

    resumed = open_challenge(client, "done-key-2").json()
    restarted = start_quest(client, "done-key-3").json()
    state = client.get(STATE_URL).json()

    assert resumed["challenge"] is None and resumed["next_action"]["type"] == "place_building"
    assert restarted["quest"]["status"] == "READY_TO_BUILD"  # Never backward.
    assert state["active_challenge"] is None and state["quests"][0]["status"] == "READY_TO_BUILD"
    assert state["inventory"] == {"resources": {"wood": 4, "stone": 0}, "blueprints": ["starter_house"]}
    assert len(table_rows("kidquest_challenges")) == 1


def test_answering_a_finished_challenge_is_refused_without_mutation(kid_client):
    client = kid_client("alleia")
    challenge_id = active_challenge_id(client)
    answer(client, challenge_id, "4", "finished-key-1")
    before, counts = snapshot("alleia"), all_kidquest_counts()

    for value in ("4", "7"):
        response = answer(client, challenge_id, value, f"finished-key-{value}x")
        assert response.status_code == 409 and error_code(response) == "CHALLENGE_EXPIRED"
        assert response.json()["error"]["challenge_status"] == "COMPLETED"

    assert snapshot("alleia") == before and all_kidquest_counts() == counts


@pytest.mark.parametrize("value", ["04", " 4 ", "4"])
def test_answer_text_is_read_as_a_number(kid_client, value):
    client = kid_client("alleia")

    assert answer(client, active_challenge_id(client), value, "number-key-1").json()["correct"] is True


# --- Validation and isolation --------------------------------------------------------------------


@pytest.mark.parametrize(
    "body, fields",
    [
        ({"answer": "empat"}, ["answer"]),
        ({"answer": ""}, ["answer"]),
        ({"answer": "-4"}, ["answer"]),
        ({"answer": "4.0"}, ["answer"]),
        ({"answer": "12345"}, ["answer"]),
        ({"answer": 4}, ["answer"]),
        ({"answer": "4", "hint_count": -1}, ["hint_count"]),
        ({"answer": "4", "hint_count": "1"}, ["hint_count"]),
        ({"answer": "4", "child": "althafandra"}, ["child"]),
        ({}, ["answer"]),
    ],
)
def test_malformed_answers_are_rejected_without_counting(kid_client, body, fields):
    client = kid_client("alleia")
    challenge_id = active_challenge_id(client)
    before, counts = snapshot("alleia"), all_kidquest_counts()

    response = client.post(f"/api/kidquest/challenges/{challenge_id}/answers", json=body, headers={"Idempotency-Key": "bad-answer-1"})

    assert response.status_code == 400 and error_code(response) == "INVALID_REQUEST"
    assert response.json()["error"]["fields"] == fields
    assert snapshot("alleia") == before and all_kidquest_counts() == counts


def test_every_quest_mutation_requires_an_idempotency_key(kid_client):
    client = kid_client("alleia")
    challenge_id = active_challenge_id(client)
    counts = all_kidquest_counts()

    for response in (
        client.post("/api/kidquest/quests/Q001/start"),
        client.post("/api/kidquest/quests/Q001/challenge"),
        client.post(f"/api/kidquest/challenges/{challenge_id}/answers", json={"answer": "4"}),
    ):
        assert response.status_code == 400 and response.json()["error"]["fields"] == ["Idempotency-Key"]
    assert all_kidquest_counts() == counts


def test_bodiless_routes_reject_a_child_in_the_body(kid_client):
    client = kid_client("alleia")

    response = client.post("/api/kidquest/quests/Q001/start", json={"child": "althafandra"}, headers={"Idempotency-Key": "child-key-1"})

    assert response.status_code == 400 and response.json()["error"]["fields"] == ["child"]
    assert start_quest(client, "child-key-2", "Q001").status_code == 200


def test_a_child_cannot_answer_the_other_childs_challenge(kid_client):
    alleia, altha = kid_client("alleia"), kid_client("althafandra")
    challenge_id = active_challenge_id(alleia)
    altha.get(STATE_URL)
    before = {child: snapshot(child) for child in ("alleia", "althafandra")}

    response = answer(altha, challenge_id, "4", "steal-key-1")

    assert response.status_code == 404 and error_code(response) == "NOT_FOUND"
    assert {child: snapshot(child) for child in ("alleia", "althafandra")} == before


def test_one_childs_progress_never_alters_the_other(kid_client):
    alleia, altha = kid_client("alleia"), kid_client("althafandra")
    altha.get(STATE_URL)
    other_before = snapshot("althafandra")

    challenge_id = active_challenge_id(alleia)
    answer(alleia, challenge_id, "5", "iso-key-1")
    answer(alleia, challenge_id, "4", "iso-key-2")

    assert snapshot("althafandra") == other_before
    assert altha.get(STATE_URL).json()["quests"][0]["status"] == "AVAILABLE"


# --- Legacy compatibility and rollback -----------------------------------------------------------


def test_kidquest_attempts_do_not_change_legacy_statistics(kid_client):
    """Decision (PRD 14.1 step 5 'selected legacy counters' = none before the economy): no child_daily change."""
    client = kid_client("alleia")
    stats_before, legacy_before = client.get("/api/stats").json(), legacy_snapshot()

    challenge_id = active_challenge_id(client)
    for n, value in enumerate(["5", "3", "4"]):
        answer(client, challenge_id, value, f"legacy-key-{n}")

    assert client.get("/api/stats").json() == stats_before
    assert legacy_snapshot() == legacy_before


def test_a_failure_mid_answer_rolls_everything_back(kq_app, kid_client):
    client = kid_client("alleia")
    challenge_id = active_challenge_id(client)
    before, counts = snapshot("alleia"), all_kidquest_counts()

    def broken(*args, **kwargs):
        raise RuntimeError("disk full")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(KidQuestRepo, "grant_blueprint_in", broken)  # After the attempt, usage, status, and wood.
        failing = TestClient(kq_app, raise_server_exceptions=False, cookies=client.cookies)
        assert answer(failing, challenge_id, "4", "rollback-key-1").status_code == 500
    assert snapshot("alleia") == before and all_kidquest_counts() == counts

    retry = answer(client, challenge_id, "4", "rollback-key-1")  # Nothing was stored, so the same key works.
    assert retry.status_code == 200 and retry.json()["correct"] is True
    assert len(table_rows("kidquest_resource_ledger")) == 1
