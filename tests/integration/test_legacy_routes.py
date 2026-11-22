"""Characterize the legacy HTTP surface: routes, quiz issuance, answers, and statistics."""

from fastapi.routing import APIRoute
from starlette.routing import Mount, Route

from app.config import COOKIE_NAME
from tests.support import (
    DEFAULT_DAY,
    answer_one,
    correct_answer,
    daily_row,
    execute,
    fetch_question,
    query,
    select_child,
    session_id,
    stored_question,
    submit,
    wrong_answer,
)

SYNC_ERROR = {"ok": False, "message": "Soal tidak sinkron. Klik Next lagi."}
NO_CHILD = {"ok": False, "message": "Pilih akun dulu."}
UNKNOWN_QUIZ = {"ok": False, "message": "Jenis kuis tidak dikenal."}

EXPECTED_ROUTES = {
    ("/openapi.json", ("GET", "HEAD")),
    ("/docs", ("GET", "HEAD")),
    ("/docs/oauth2-redirect", ("GET", "HEAD")),
    ("/redoc", ("GET", "HEAD")),
    ("/static", ()),
    ("/favicon.ico", ("GET",)),
    ("/.well-known/{path:path}", ("GET",)),
    ("/", ("GET",)),
    ("/start", ("GET",)),
    ("/home", ("GET",)),
    ("/home/{child}", ("GET",)),
    ("/quiz", ("GET",)),
    ("/quiz/{quiz_type}", ("GET",)),
    ("/stats", ("GET",)),
    ("/api/stats", ("GET",)),
    ("/api/question", ("GET",)),
    ("/api/answer", ("POST",)),
    ("/api/admin/clear", ("POST",)),
    ("/manifest.json", ("GET",)),
    ("/manifest.webmanifest", ("GET",)),
    ("/health", ("GET",)),
}


# --- App creation and route inventory -------------------------------------------------


def test_route_inventory_is_unchanged(app):
    routes = {
        (route.path, tuple(sorted(getattr(route, "methods", None) or ())))
        for route in app.routes
        if isinstance(route, (APIRoute, Route, Mount))
    }

    assert routes == EXPECTED_ROUTES


def test_create_app_migrates_the_configured_database(app, db_path):
    assert db_path.exists()
    assert [row["version"] for row in query("SELECT version FROM schema_migrations ORDER BY version")] == list(
        range(1, 10)
    )


def test_health_manifest_and_utility_routes(client):
    assert client.get("/health").json() == {"ok": True}
    assert client.get("/favicon.ico").status_code == 204
    assert client.get("/.well-known/appspecific/com.chrome.devtools.json").status_code == 204

    manifest = client.get("/manifest.json").json()
    assert manifest == client.get("/manifest.webmanifest").json()
    assert manifest["start_url"] == "/home"
    assert manifest["icons"] == [{"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"}]


def test_static_files_are_served(client):
    response = client.get("/static/css/base.css")

    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]


def test_not_found_handling(client):
    api = client.get("/api/missing")
    assert (api.status_code, api.json()) == (404, {"ok": False, "message": "Not found"})

    static = client.get("/static/missing.css")
    assert (static.status_code, static.json()) == (404, {"detail": "Not found"})

    page = client.get("/missing-page", follow_redirects=False)
    assert (page.status_code, page.headers["location"]) == (303, "/home")


# --- Pages, redirects, and the session cookie -----------------------------------------


def test_root_creates_a_session_cookie_and_redirects_to_start(client):
    response = client.get("/", follow_redirects=False)

    assert (response.status_code, response.headers["location"]) == (307, "/start")
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE_NAME}=")
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert "Max-Age=31536000" in cookie and "Path=/" in cookie
    assert "Secure" not in cookie  # Local HTTP default; production adds Secure.
    assert query("SELECT child, day FROM sessions") == [{"child": None, "day": DEFAULT_DAY}]


def test_start_redirects_to_home_then_quiz_after_profile_selection(client):
    first = client.get("/start", follow_redirects=False)
    assert (first.status_code, first.headers["location"]) == (307, "/home")

    select_child(client, "alleia")
    second = client.get("/start", follow_redirects=False)
    assert (second.status_code, second.headers["location"]) == (307, "/quiz")


def test_home_and_stats_pages_render(client):
    home = client.get("/home")
    stats = client.get("/stats")

    assert home.status_code == 200 and "text/html" in home.headers["content-type"]
    assert stats.status_code == 200 and "text/html" in stats.headers["content-type"]
    assert COOKIE_NAME in client.cookies


def test_profile_selection_is_case_insensitive_and_rejects_unknown_children(client):
    select_child(client, "ALLEIA")
    assert query("SELECT child FROM sessions") == [{"child": "alleia"}]

    unknown = client.get("/home/somebody", follow_redirects=False)
    assert (unknown.status_code, unknown.headers["location"]) == (303, "/home")
    assert query("SELECT child FROM sessions") == [{"child": "alleia"}]


def test_quiz_routes_redirect_until_a_profile_is_selected(client):
    assert client.get("/quiz", follow_redirects=False).headers["location"] == "/quiz/math"
    assert client.get("/quiz/history", follow_redirects=False).headers["location"] == "/quiz/math"

    no_child = client.get("/quiz/math", follow_redirects=False)
    assert (no_child.status_code, no_child.headers["location"]) == (307, "/home")

    select_child(client, "althafandra")
    for quiz_type in ("math", "knowledge"):
        page = client.get(f"/quiz/{quiz_type}")
        assert page.status_code == 200
        assert "althafandra" in page.text


# --- Question issuance ----------------------------------------------------------------


def test_question_requires_a_profile_and_a_known_quiz_type(client):
    no_child = client.get("/api/question")
    assert (no_child.status_code, no_child.json()) == (400, NO_CHILD)

    select_child(client, "alleia")
    unknown = client.get("/api/question", params={"quiz_type": "history"})
    assert (unknown.status_code, unknown.json()) == (400, UNKNOWN_QUIZ)


def test_math_question_payload_shape_and_bank_assignment(make_client):
    for child, version in (("alleia", 1), ("althafandra", 2)):
        client = make_client()
        select_child(client, child)

        payload = fetch_question(client, "math")

        assert set(payload) == {"ok", "qid", "prompt", "version", "type"}
        assert (payload["version"], payload["type"]) == (version, "math")
        assert payload["qid"].startswith(f"v{version}_q")


def test_knowledge_question_payload_shape(client):
    select_child(client, "alleia")

    payload = fetch_question(client, "knowledge")

    assert set(payload) == {"ok", "qid", "prompt", "version", "type", "options", "reward"}
    assert (payload["version"], payload["type"], payload["reward"]) == ("knowledge", "knowledge", 100)
    assert [option["id"] for option in payload["options"]] == ["A", "B", "C", "D"]


def test_serving_a_question_persists_bank_reservation_and_counters(client):
    select_child(client, "alleia")

    qid = fetch_question(client)["qid"]

    assert query("SELECT child, day, quiz_type FROM daily_question_banks") == [
        {"child": "alleia", "day": DEFAULT_DAY, "quiz_type": "math"}
    ]
    assert query("SELECT question_id FROM served_questions") == [{"question_id": qid}]
    assert query("SELECT child, quiz_type, question_id FROM session_current_questions") == [
        {"child": "alleia", "quiz_type": "math", "question_id": qid}
    ]
    assert query("SELECT served_count, current_qid, current_math_qid, current_quiz_type FROM sessions") == [
        {"served_count": 1, "current_qid": qid, "current_math_qid": qid, "current_quiz_type": "math"}
    ]
    assert daily_row("alleia")["served_count"] == 1


def test_refresh_returns_the_active_unfinished_question_without_counting_it_again(client):
    select_child(client, "alleia")
    first = fetch_question(client)

    assert fetch_question(client) == first
    assert daily_row("alleia")["served_count"] == 1
    assert len(query("SELECT * FROM served_questions")) == 1


def test_math_and_knowledge_keep_separate_unfinished_questions(client):
    select_child(client, "alleia")
    math = fetch_question(client, "math")
    knowledge = fetch_question(client, "knowledge")

    assert fetch_question(client, "math") == math
    assert fetch_question(client, "knowledge") == knowledge


def test_questions_are_not_repeated_within_a_day(client):
    select_child(client, "alleia")

    seen = set()
    for _ in range(5):
        qid = fetch_question(client)["qid"]
        assert qid not in seen
        seen.add(qid)
        submit(client, qid, correct_answer("alleia", "math", qid))


def test_question_limit_message_when_daily_quota_is_used(client):
    select_child(client, "alleia")
    execute(
        "INSERT INTO child_daily(child, day, served_count, answered_count, correct_count, earned) "
        "VALUES ('alleia', ?, 400, 400, 0, 0)",
        (DEFAULT_DAY,),
    )

    response = client.get("/api/question")

    assert response.status_code == 200
    assert response.json() == {"ok": False, "message": "Batas hari ini sudah tercapai (400 soal). Besok lanjut ya."}


def test_all_questions_served_message(client):
    select_child(client, "alleia")
    fetch_question(client)  # Persist today's bank.
    execute(
        "INSERT OR IGNORE INTO served_questions(child, day, quiz_type, question_id) "
        "SELECT 'alleia', ?, 'math', json_extract(value, '$.id') FROM daily_question_banks, json_each(bank_json)",
        (DEFAULT_DAY,),
    )
    execute("DELETE FROM session_current_questions")

    response = client.get("/api/question")

    assert response.status_code == 200
    assert response.json() == {
        "ok": False,
        "message": "Semua soal untuk kuis ini hari ini sudah ditampilkan. Besok lanjut ya.",
    }


# --- Answer submission -----------------------------------------------------------------


def test_correct_math_answer_counts_once_and_clears_the_active_question(client):
    select_child(client, "alleia")
    qid = fetch_question(client)["qid"]
    expected = int(correct_answer("alleia", "math", qid))

    response = submit(client, qid, f" {expected} ")

    assert (response.status_code, response.json()) == (200, {"ok": True, "correct": True, "correct_answer": expected})
    row = daily_row("alleia")
    assert (row["served_count"], row["answered_count"], row["correct_count"], row["earned"]) == (1, 1, 1, 50)
    session = query("SELECT answered_count, correct_count, earned, current_qid, current_math_qid FROM sessions")[0]
    assert session == {"answered_count": 1, "correct_count": 1, "earned": 50, "current_qid": None, "current_math_qid": None}
    assert query("SELECT * FROM session_current_questions") == []


def test_wrong_and_blank_math_answers_count_as_answered_but_not_correct(client):
    select_child(client, "alleia")

    for answer in ("wrong", "blank"):
        qid = fetch_question(client)["qid"]
        expected = int(correct_answer("alleia", "math", qid))
        given = wrong_answer("alleia", "math", qid) if answer == "wrong" else ""

        response = submit(client, qid, given)

        assert response.json() == {"ok": True, "correct": False, "correct_answer": expected}

    row = daily_row("alleia")
    assert (row["answered_count"], row["correct_count"], row["earned"]) == (2, 0, 0)


def test_knowledge_answer_costs_two_units_and_rewards_100(client):
    select_child(client, "althafandra")
    qid = fetch_question(client, "knowledge")["qid"]
    letter = correct_answer("althafandra", "knowledge", qid)

    response = submit(client, qid, letter.lower(), "knowledge")  # Letters are case-insensitive.

    option_text = next(
        option["text"] for option in stored_question("althafandra", "knowledge", qid)["options"] if option["id"] == letter
    )
    assert response.json() == {"ok": True, "correct": True, "correct_answer": option_text}
    row = daily_row("althafandra")
    assert (row["answered_count"], row["correct_count"], row["earned"]) == (2, 1, 100)


def test_answer_requires_a_profile_and_a_known_quiz_type(client):
    no_child = submit(client, "v1_q0001", "1")
    assert (no_child.status_code, no_child.json()) == (400, NO_CHILD)

    select_child(client, "alleia")
    unknown = submit(client, "v1_q0001", "1", "history")
    assert (unknown.status_code, unknown.json()) == (400, UNKNOWN_QUIZ)


def test_out_of_sync_answer_is_rejected_without_counting(client):
    select_child(client, "alleia")
    qid = fetch_question(client)["qid"]

    no_active = submit(client, qid, "1", "knowledge")
    mismatch = submit(client, "v1_q9999", "1")

    assert (no_active.status_code, no_active.json()) == (400, SYNC_ERROR)
    assert (mismatch.status_code, mismatch.json()) == (400, SYNC_ERROR)
    assert daily_row("alleia")["answered_count"] == 0


def test_quota_rejects_an_answer_that_would_exceed_the_daily_limit(client):
    select_child(client, "alleia")
    qid = fetch_question(client, "knowledge")["qid"]
    execute("UPDATE child_daily SET answered_count = 399 WHERE child = 'alleia'")

    response = submit(client, qid, correct_answer("alleia", "knowledge", qid), "knowledge")

    assert response.status_code == 409
    assert response.json() == {"ok": False, "message": "Sisa kuota hari ini tidak cukup untuk soal ini."}
    assert daily_row("alleia")["answered_count"] == 399
    # The question stays active after a quota rejection.
    assert query("SELECT question_id FROM session_current_questions") == [{"question_id": qid}]


def test_last_math_unit_can_still_be_answered(client):
    select_child(client, "alleia")
    qid = fetch_question(client)["qid"]
    execute("UPDATE child_daily SET answered_count = 399 WHERE child = 'alleia'")

    assert submit(client, qid, correct_answer("alleia", "math", qid)).json()["ok"] is True
    assert daily_row("alleia")["answered_count"] == 400


# --- Statistics -------------------------------------------------------------------------


def test_api_stats_reports_today_and_a_seven_day_recap(client):
    select_child(client, "alleia")
    answer_one(client, "alleia", correct=True)
    answer_one(client, "alleia", correct=False)

    payload = client.get("/api/stats").json()

    assert {key: payload[key] for key in ("ok", "child", "day", "served_count", "answered_count", "correct_count", "earned")} == {
        "ok": True,
        "child": "alleia",
        "day": DEFAULT_DAY,
        "served_count": 2,
        "answered_count": 2,
        "correct_count": 1,
        "earned": 50,
    }
    recap = payload["recap7"]
    assert recap["range"] == {"start": "2026-11-15", "end": DEFAULT_DAY}
    assert recap["generated_at"] == "2026-11-21T10:00:00"  # Jakarta wall time, legacy format.
    alleia = recap["children"]["alleia"]
    assert [day["day"] for day in alleia["days"]] == [f"2026-11-{d}" for d in range(15, 22)]
    assert alleia["days"][-1] == {
        "day": DEFAULT_DAY,
        "served_count": 2,
        "answered_count": 2,
        "correct_count": 1,
        "earned": 50,
        "accuracy_pct": 50,
    }


def test_seven_day_recap_aggregates_only_the_last_seven_days(client):
    rows = [("2026-11-14", 9, 9, 9, 450), ("2026-11-15", 10, 6, 4, 200), ("2026-11-20", 5, 3, 3, 150)]
    for day, served, answered, correct, earned in rows:
        execute(
            "INSERT INTO child_daily(child, day, served_count, answered_count, correct_count, earned) "
            "VALUES ('althafandra', ?, ?, ?, ?, ?)",
            (day, served, answered, correct, earned),
        )

    recap = client.get("/api/stats").json()["recap7"]["children"]["althafandra"]

    assert recap["totals"] == {
        "served_count": 15,
        "answered_count": 9,
        "correct_count": 7,
        "earned": 350,
        "accuracy_pct": 78,  # round(7 / 9 * 100)
    }
    assert recap["days"][0]["accuracy_pct"] == 67  # round(4 / 6 * 100)
    assert recap["days"][1] == {
        "day": "2026-11-16",
        "served_count": 0,
        "answered_count": 0,
        "correct_count": 0,
        "earned": 0,
        "accuracy_pct": 0,
    }


def test_quiz_page_shows_today_counters_and_level(client):
    select_child(client, "alleia")
    answer_one(client, "alleia", correct=True)
    sid = session_id(client)

    math_page = client.get("/quiz/math")
    knowledge_page = client.get("/quiz/knowledge")

    assert '<span id="answered">1</span> / 400' in math_page.text
    assert '<b id="correct">1</b>' in math_page.text
    assert 'Rp <b id="earned">50</b>' in math_page.text
    assert '<b id="level">Pemula</b>' in math_page.text  # Fewer than 50 answered this week.
    assert 'data-reward-per-correct="50"' in math_page.text
    assert 'data-reward-per-correct="100"' in knowledge_page.text
    assert client.cookies[COOKIE_NAME] == sid
