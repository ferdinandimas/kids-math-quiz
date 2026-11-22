"""Concurrent first reads create one world; concurrent theme changes bump the version once."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.db.kidquest_repo import KidQuestRepo
from app.services.kidquest_service import KidQuestService
from tests.integration.kidquest.conftest import (
    STATE_URL,
    active_challenge_id,
    answer,
    change_theme,
    error_code,
    open_challenge,
    place,
    seed_ready_to_build,
    table_rows,
)


def run_together(count: int, task):
    barrier = threading.Barrier(count)

    def worker(index):
        barrier.wait()
        return task(index)

    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(worker, range(count)))


def test_racing_first_reads_that_both_miss_the_world_create_one_world(kq_app):
    """Force the worst interleaving: both requests see no world before either initializes it."""
    both_checked = threading.Barrier(2)
    first_lookup = threading.local()

    class RacingRepo(KidQuestRepo):
        def get_world_in(self, conn, child):
            world = super().get_world_in(conn, child)
            if not getattr(first_lookup, "done", False):
                first_lookup.done = True
                both_checked.wait(timeout=5)
            return world

    service = KidQuestService(kq_app.state.kidquest_catalog, RacingRepo())

    states = run_together(2, lambda _: service.get_or_create_state("alleia"))

    assert states[0] == states[1]
    assert len(table_rows("kidquest_worlds")) == 1
    assert len(table_rows("kidquest_child_quests")) == 6


def test_simultaneous_first_http_reads_create_one_world(kid_client):
    clients = [kid_client("alleia") for _ in range(6)]

    responses = run_together(6, lambda index: clients[index].get(STATE_URL))

    assert [response.status_code for response in responses] == [200] * 6
    assert len({response.content for response in responses}) == 1
    assert len(table_rows("kidquest_worlds")) == 1
    assert len(table_rows("kidquest_child_quests")) == 6


def test_concurrent_replays_of_one_theme_request_bump_the_version_once(kid_client):
    clients = [kid_client("alleia") for _ in range(4)]
    clients[0].get(STATE_URL)

    responses = run_together(4, lambda index: change_theme(clients[index], "kingdom", 1, "concurrent-key-1"))

    assert [response.status_code for response in responses] == [200] * 4
    assert len({response.content for response in responses}) == 1
    assert table_rows("kidquest_worlds")[0]["version"] == 2
    assert len(table_rows("kidquest_idempotency")) == 1


def test_concurrent_changes_from_one_version_have_one_winner(kid_client):
    clients = [kid_client("alleia") for _ in range(3)]
    clients[0].get(STATE_URL)
    themes = ["kingdom", "city", "kingdom"]

    responses = run_together(3, lambda index: change_theme(clients[index], themes[index], 1, f"race-key-{index}"))

    winners = [response for response in responses if response.status_code == 200]
    losers = [response for response in responses if response.status_code != 200]
    assert len(winners) == 1
    assert all(response.status_code == 409 and error_code(response) == "WORLD_VERSION_CONFLICT" for response in losers)
    world = table_rows("kidquest_worlds")[0]
    assert (world["theme_id"], world["version"]) == (winners[0].json()["theme_id"], 2)


# --- AC-11: concurrent answers (each scenario runs 50 times on a fresh world) -----------------------


def reward_counts() -> tuple:
    return (
        len(table_rows("kidquest_attempts")),
        table_rows("kidquest_daily_usage")[0]["accepted_attempts"],
        [(r["resource_type"], r["delta"]) for r in table_rows("kidquest_resource_ledger")],
        [(r["resource_type"], r["balance"]) for r in table_rows("kidquest_resource_balances")],
        [r["building_type"] for r in table_rows("kidquest_blueprints")],
        table_rows("kidquest_child_quests", "alleia")[0]["status"],
    )


@pytest.mark.parametrize("run", range(50))
def test_concurrent_correct_answers_with_one_key_reward_once(kid_client, run):
    clients = [kid_client("alleia") for _ in range(2)]
    challenge_id = active_challenge_id(clients[0])

    responses = run_together(2, lambda index: answer(clients[index], challenge_id, "4", "same-correct-key"))

    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].content == responses[1].content  # One accepted mutation, one identical replay.
    assert responses[0].json()["correct"] is True
    assert reward_counts() == (1, 1, [("wood", 4)], [("wood", 4)], ["starter_house"], "READY_TO_BUILD")


@pytest.mark.parametrize("run", range(50))
def test_concurrent_correct_answers_with_different_keys_reward_once(kid_client, run):
    clients = [kid_client("alleia") for _ in range(2)]
    challenge_id = active_challenge_id(clients[0])

    responses = run_together(2, lambda index: answer(clients[index], challenge_id, "4", f"racing-correct-key-{index}"))

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200, 409]
    loser = next(response for response in responses if response.status_code == 409)
    assert error_code(loser) == "CHALLENGE_EXPIRED"
    assert reward_counts() == (1, 1, [("wood", 4)], [("wood", 4)], ["starter_house"], "READY_TO_BUILD")


def test_concurrent_challenge_requests_create_one_challenge(kid_client):
    clients = [kid_client("alleia") for _ in range(4)]

    responses = run_together(4, lambda index: open_challenge(clients[index], f"open-race-{index}"))

    assert [response.status_code for response in responses] == [200] * 4
    assert len({response.json()["challenge"]["id"] for response in responses}) == 1
    assert len(table_rows("kidquest_challenges")) == 1
    assert table_rows("kidquest_child_quests", "alleia")[0]["status"] == "IN_PROGRESS"


# --- AC-12: concurrent placements (each scenario runs 50 times on a fresh world) --------------------


def ready_clients(kid_client, count: int):
    clients = [kid_client("alleia") for _ in range(count)]
    clients[0].get(STATE_URL)
    seed_ready_to_build("alleia")
    return clients


def assert_one_house():
    buildings = table_rows("kidquest_buildings")
    spends = [row for row in table_rows("kidquest_resource_ledger") if row["delta"] < 0]
    assert len(buildings) == 1 and len(spends) == 1
    assert table_rows("kidquest_resource_balances")[0]["balance"] == 0
    assert table_rows("kidquest_child_quests", "alleia")[0]["status"] == "COMPLETED"
    assert table_rows("kidquest_worlds")[0]["version"] == 2
    return buildings[0]


@pytest.mark.parametrize("origins", [((2, 1), (2, 1)), ((1, 1), (2, 1))], ids=["same_cell", "overlapping"])
@pytest.mark.parametrize("run", range(50))
def test_concurrent_placements_with_different_keys_build_one_house(kid_client, run, origins):
    clients = ready_clients(kid_client, 2)

    responses = run_together(2, lambda index: place(clients[index], *origins[index], 1, f"race-place-{index}"))

    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response for response in responses if response.status_code == 200)
    loser = next(response for response in responses if response.status_code == 409)
    assert error_code(loser) == "WORLD_VERSION_CONFLICT" and loser.json()["error"]["world_version"] == 2  # Refreshable.
    house = assert_one_house()
    assert (house["x"], house["y"]) == (winner.json()["building"]["x"], winner.json()["building"]["y"])


@pytest.mark.parametrize("run", range(50))
def test_concurrent_placements_with_one_key_build_once_and_replay(kid_client, run):
    clients = ready_clients(kid_client, 2)

    responses = run_together(2, lambda index: place(clients[index], 2, 1, 1, "same-place-key"))

    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].content == responses[1].content
    assert assert_one_house()["id"] == responses[0].json()["building"]["id"]
