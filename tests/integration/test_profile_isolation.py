"""Characterize how daily data and unfinished questions are separated per child."""

from tests.support import (
    DEFAULT_DAY,
    answer_one,
    correct_answer,
    daily_row,
    fetch_question,
    query,
    select_child,
    submit,
)


def test_each_child_has_independent_daily_statistics(make_client):
    alleia, althafandra = make_client(), make_client()
    select_child(alleia, "alleia")
    select_child(althafandra, "althafandra")

    answer_one(alleia, "alleia", correct=True)
    answer_one(alleia, "alleia", correct=True)
    answer_one(althafandra, "althafandra", correct=False)

    a, b = daily_row("alleia"), daily_row("althafandra")
    assert (a["served_count"], a["answered_count"], a["correct_count"], a["earned"]) == (2, 2, 2, 100)
    assert (b["served_count"], b["answered_count"], b["correct_count"], b["earned"]) == (1, 1, 0, 0)
    assert alleia.get("/api/stats").json()["answered_count"] == 2
    assert althafandra.get("/api/stats").json()["answered_count"] == 1


def test_each_child_gets_their_own_daily_bank_and_served_history(make_client):
    alleia, althafandra = make_client(), make_client()
    select_child(alleia, "alleia")
    select_child(althafandra, "althafandra")

    a_qid = fetch_question(alleia)["qid"]
    b_qid = fetch_question(althafandra)["qid"]

    assert a_qid.startswith("v1_") and b_qid.startswith("v2_")
    assert query("SELECT child, question_id FROM served_questions ORDER BY child") == [
        {"child": "alleia", "question_id": a_qid},
        {"child": "althafandra", "question_id": b_qid},
    ]
    assert query("SELECT child FROM daily_question_banks ORDER BY child") == [{"child": "alleia"}, {"child": "althafandra"}]


def test_switching_child_in_one_session_keeps_each_unfinished_question(client):
    select_child(client, "alleia")
    alleia_question = fetch_question(client)

    select_child(client, "althafandra")
    althafandra_question = fetch_question(client)
    assert althafandra_question["qid"] != alleia_question["qid"]

    select_child(client, "alleia")
    assert fetch_question(client) == alleia_question
    assert query("SELECT child, question_id FROM session_current_questions ORDER BY child") == [
        {"child": "alleia", "question_id": alleia_question["qid"]},
        {"child": "althafandra", "question_id": althafandra_question["qid"]},
    ]


def test_a_child_cannot_answer_the_other_childs_question(client):
    select_child(client, "alleia")
    alleia_qid = fetch_question(client)["qid"]
    alleia_answer = correct_answer("alleia", "math", alleia_qid)

    select_child(client, "althafandra")
    response = submit(client, alleia_qid, alleia_answer)

    assert response.status_code == 400
    assert response.json() == {"ok": False, "message": "Soal tidak sinkron. Klik Next lagi."}
    assert daily_row("alleia")["answered_count"] == 0
    assert daily_row("althafandra") is None


def test_session_row_counters_are_shared_across_children_in_one_session(client):
    """Legacy quirk: `sessions` counters are per browser session, not per child.

    The UI and /api/stats read `child_daily`, so this does not leak into displayed totals.
    """
    select_child(client, "alleia")
    answer_one(client, "alleia")
    select_child(client, "althafandra")
    answer_one(client, "althafandra")

    assert query("SELECT served_count, answered_count, correct_count, earned FROM sessions") == [
        {"served_count": 2, "answered_count": 2, "correct_count": 2, "earned": 100}
    ]
    assert daily_row("alleia")["answered_count"] == 1
    assert daily_row("althafandra")["answered_count"] == 1


def test_two_sessions_for_the_same_child_share_daily_totals_and_never_repeat_questions(make_client):
    tablet, phone = make_client(), make_client()
    select_child(tablet, "alleia")
    select_child(phone, "alleia")

    tablet_qid = fetch_question(tablet)["qid"]
    phone_qid = fetch_question(phone)["qid"]
    submit(tablet, tablet_qid, correct_answer("alleia", "math", tablet_qid))
    submit(phone, phone_qid, correct_answer("alleia", "math", phone_qid))

    assert tablet_qid != phone_qid
    row = daily_row("alleia", DEFAULT_DAY)
    assert (row["served_count"], row["answered_count"], row["correct_count"]) == (2, 2, 2)
