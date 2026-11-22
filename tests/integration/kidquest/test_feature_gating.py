"""KIDQUEST_ENABLED and the profile allowlist guard every KidQuest route; legacy routes are byte-identical either way."""

import itertools
import random
import re

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app import config
from app.config import COOKIE_NAME
from app.main import create_app
from app.services import question_service
from app.services.session_service import SessionService
from tests.integration.kidquest.conftest import (
    KIDQUEST_ROUTES,
    PREVIEW_URL,
    STATE_URL,
    THEMES_URL,
    all_kidquest_counts,
    change_theme,
    error_code,
    open_challenge,
    start_quest,
    legacy_snapshot,
    table_rows,
)
from tests.integration.kidquest.conftest import answer as kidquest_answer
from tests.integration.kidquest.conftest import place as kidquest_place
from tests.support import correct_answer, query, select_child

KIDQUEST_CALLS = (
    ("GET", STATE_URL, {}),
    ("GET", THEMES_URL, {}),
    ("PATCH", "/api/kidquest/theme",
     {"json": {"theme_id": "kingdom", "world_version": 1, "manifest_version": 1}, "headers": {"Idempotency-Key": "gate-key-1"}}),
    ("POST", "/api/kidquest/quests/Q001/start", {"headers": {"Idempotency-Key": "gate-key-2"}}),
    ("POST", "/api/kidquest/quests/Q001/challenge", {"headers": {"Idempotency-Key": "gate-key-3"}}),
    ("POST", "/api/kidquest/challenges/ch_0000/answers", {"json": {"answer": "4"}, "headers": {"Idempotency-Key": "gate-key-4"}}),
    ("GET", "/api/kidquest/buildings/preview", {"params": {"building_type": "starter_house", "x": 1, "y": 1}}),
    ("POST", "/api/kidquest/buildings",
     {"json": {"building_type": "starter_house", "x": 1, "y": 1, "rotation": 0, "world_version": 1}, "headers": {"Idempotency-Key": "gate-key-5"}}),
)


def call_all(client: TestClient):
    return [client.request(method, url, **kwargs) for method, url, kwargs in KIDQUEST_CALLS]


# --- Disabled: no KidQuest surface ----------------------------------------------------------------


def test_disabled_kidquest_has_no_routes(app, client):
    assert not [route for route in app.routes if isinstance(route, APIRoute) and "kidquest" in route.path]
    select_child(client, "alleia")

    for response in call_all(client):
        assert response.status_code == 404
        assert response.json() == {"ok": False, "message": "Not found"}  # The legacy API 404, unchanged.
    assert all(count == 0 for count in all_kidquest_counts().values())


def test_a_router_left_mounted_still_refuses_when_disabled(kid_client, monkeypatch):
    client = kid_client("alleia")
    monkeypatch.setattr(config, "KIDQUEST_ENABLED", False)

    for response in call_all(client):
        assert response.status_code == 404 and error_code(response) == "KIDQUEST_DISABLED"
    assert table_rows("kidquest_worlds") == []


# --- Enabled: session and allowlist ------------------------------------------------------------


def test_no_session_means_profile_required_and_no_session_is_created(kid_client):
    client = kid_client()

    for response in call_all(client):
        assert response.status_code == 401 and error_code(response) == "PROFILE_REQUIRED"
        assert "set-cookie" not in response.headers
    assert query("SELECT COUNT(*) AS n FROM sessions")[0]["n"] == 0
    assert all(count == 0 for count in all_kidquest_counts().values())


def test_session_without_a_child_or_with_an_unknown_cookie_means_profile_required(kid_client):
    no_child = kid_client()
    no_child.get("/home")  # Creates a legacy session with no child selected.
    forged = kid_client()
    forged.cookies.set(COOKIE_NAME, "not-a-real-session")

    for client in (no_child, forged):
        for response in call_all(client):
            assert response.status_code == 401 and error_code(response) == "PROFILE_REQUIRED"
    assert table_rows("kidquest_worlds") == []


def test_children_outside_the_allowlist_are_refused(kid_client, monkeypatch):
    monkeypatch.setattr(config, "KIDQUEST_PROFILE_ALLOWLIST", ("alleia",))
    altha, alleia = kid_client("althafandra"), kid_client("alleia")

    for response in call_all(altha):
        assert response.status_code == 403 and error_code(response) == "KIDQUEST_DISABLED"
    assert alleia.get(STATE_URL).status_code == 200
    assert [row["child"] for row in table_rows("kidquest_worlds")] == ["alleia"]


def test_an_empty_allowlist_admits_nobody(kid_client, monkeypatch):
    monkeypatch.setattr(config, "KIDQUEST_PROFILE_ALLOWLIST", ())
    client = kid_client("alleia")

    for response in call_all(client):
        assert response.status_code == 403 and error_code(response) == "KIDQUEST_DISABLED"
    assert all(count == 0 for count in all_kidquest_counts().values())


def test_gating_runs_before_request_validation(kid_client):
    response = kid_client().patch("/api/kidquest/theme", content=b"not json")

    assert response.status_code == 401 and error_code(response) == "PROFILE_REQUIRED"


# --- Legacy routes are byte-identical with KidQuest off and on -------------------------------------


def run_legacy_script(tmp_path, monkeypatch, name: str, enabled: bool, allowlist: tuple = ("alleia", "althafandra")) -> list[tuple]:
    """Drive every legacy route (and GET /kidquest) on a fresh database; record status, headers, and body bytes."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / f"{name}.sqlite3"))
    monkeypatch.setattr(question_service, "random", random.Random(20261121))
    counter = itertools.count(1)
    monkeypatch.setattr(SessionService, "new_session_id", staticmethod(lambda: f"session-{next(counter):04d}"))
    monkeypatch.setattr(config, "KIDQUEST_ENABLED", enabled)
    monkeypatch.setattr(config, "KIDQUEST_PROFILE_ALLOWLIST", allowlist if enabled else ())
    playing = enabled and "alleia" in allowlist
    app = create_app()
    client, other = TestClient(app), TestClient(app)
    recorded = []

    def record(response):
        recorded.append((response.request.method, str(response.request.url), response.status_code,
                         sorted(response.headers.multi_items()), response.content))
        return response

    def kidquest_activity():
        if not enabled:
            return
        if not playing:  # Enabled but closed for this child: every KidQuest call is refused, nothing else changes.
            assert client.get(STATE_URL).status_code == 403
            return
        # Interleave real KidQuest traffic (theme, Q001 start, challenge, wrong and correct answers,
        # preview, placement). It must not change any legacy response, including /api/stats.
        state = client.get(STATE_URL).json()
        version = state["world"]["version"]
        themed = change_theme(client, "city", version, f"legacy-script-{version}")
        assert themed.status_code == 200
        if state["quests"][0]["status"] == "READY_TO_BUILD":
            assert client.get(PREVIEW_URL, params={"building_type": "starter_house", "x": 2, "y": 1}).json()["valid"] is True
            current = themed.json()["world_version"]
            assert kidquest_place(client, 2, 1, current, f"legacy-place-{current}").status_code == 200
        if state["quests"][0]["status"] in ("AVAILABLE", "IN_PROGRESS"):
            assert start_quest(client, f"legacy-start-{version}").status_code == 200
            challenge_id = open_challenge(client, f"legacy-open-{version}").json()["challenge"]["id"]
            value = "5" if state["quests"][0]["status"] == "AVAILABLE" else "4"
            assert kidquest_answer(client, challenge_id, value, f"legacy-answer-{version}").status_code == 200

    for url in ("/", "/start", "/home", "/api/question", "/api/stats", "/stats", "/favicon.ico", "/.well-known/x",
                "/manifest.json", "/manifest.webmanifest", "/health", "/static/css/base.css", "/static/missing.png", "/no-such-page", "/api/no-such-api", "/openapi.json",
                "/kidquest"):
        record(client.get(url, follow_redirects=False))
    record(client.get("/home/alleia", follow_redirects=False))
    kidquest_activity()
    for url in ("/start", "/quiz", "/quiz/math", "/quiz/knowledge", "/quiz/other", "/home", "/kidquest"):
        record(client.get(url, follow_redirects=False))
    for quiz_type, answer in (("math", "0"), ("knowledge", "A"), ("math", None)):
        question = record(client.get("/api/question", params={"quiz_type": quiz_type})).json()
        kidquest_activity()
        answer = answer or correct_answer("alleia", quiz_type, question["qid"])
        record(client.post("/api/answer", json={"qid": question["qid"], "answer": answer, "quiz_type": quiz_type}))
    record(client.post("/api/answer", json={"qid": "stale", "answer": "1", "quiz_type": "math"}))
    record(client.get("/api/stats"))
    record(other.get("/home/althafandra", follow_redirects=False))
    record(other.get("/api/question", params={"quiz_type": "math"}))
    record(client.post("/api/admin/clear", json={"password": "wrong"}))
    record(client.post("/api/admin/clear", json={"password": config.ADMIN_CLEAR_PASSWORD}))
    record(client.get("/api/stats"))
    return recorded


LEGACY_REQUESTS = 38
# Responses KidQuest may change when it is on for the selected child (KQ-010), and how.
ENTRY_PAGES = {"http://testserver/home", "http://testserver/quiz/math", "http://testserver/quiz/knowledge"}
PAGE_URL = "http://testserver/kidquest"
ENTRY_LINK = re.compile(rb'\n[ ]*<a [^>]*href="/kidquest" data-testid="kidquest-entry"[^>]*>[^<]*(?:<img [^>]*>[^<]*)?</a>')


def assert_kidquest_script_ran():
    assert [row["is_correct"] for row in table_rows("kidquest_attempts")] == [0, 1]  # The enabled run really played Q001,
    assert [(row["type"], row["x"], row["y"]) for row in table_rows("kidquest_buildings")] == [("starter_house", 2, 1)]  # placement included.


def test_legacy_responses_are_byte_identical_with_kidquest_off_and_closed(tmp_path, monkeypatch, clock):
    """Enabled but with the child outside the allowlist, every response, /kidquest included, is the legacy one."""
    disabled = run_legacy_script(tmp_path, monkeypatch, "disabled", enabled=False)
    closed = run_legacy_script(tmp_path, monkeypatch, "closed", enabled=True, allowlist=("althafandra",))

    assert len(disabled) == LEGACY_REQUESTS
    for off, on in zip(disabled, closed, strict=True):
        assert on == off, f"{off[0]} {off[1]} differs"
    page = [entry for entry in disabled if entry[1] == PAGE_URL]
    assert [(entry[2], dict(entry[3])["location"]) for entry in page] == [(303, "/home"), (303, "/home")]  # The legacy unknown-page redirect.
    cookies = [value for entry in disabled for name, value in entry[3] if name == "set-cookie"]
    assert cookies and all(value.startswith(f"{COOKIE_NAME}=session-") for value in cookies)  # Cookies were compared too.


def test_legacy_responses_with_kidquest_on_differ_only_by_the_entry_link(tmp_path, monkeypatch, clock):
    disabled = run_legacy_script(tmp_path, monkeypatch, "disabled", enabled=False)
    enabled = run_legacy_script(tmp_path, monkeypatch, "enabled", enabled=True)

    assert len(disabled) == LEGACY_REQUESTS
    assert_kidquest_script_ran()
    assert [entry[:2] for entry in enabled] == [entry[:2] for entry in disabled]
    entry_pages = page_hits = 0
    for off, on in zip(disabled, enabled, strict=True):
        if on[1] == PAGE_URL and on[2] == 200:
            page_hits += 1  # GET /kidquest after the child was selected: the world page.
            assert b'id="kq-boot"' in on[4] and off[2] == 303
            continue
        if on[1] in ENTRY_PAGES and b"kidquest-entry" in on[4]:
            entry_pages += 1
            stripped, links = ENTRY_LINK.subn(b"", on[4])
            assert links == 1 and stripped == off[4], f"{off[1]}: more than the entry link changed"
            assert [h for h in on[3] if h[0] != "content-length"] == [h for h in off[3] if h[0] != "content-length"]
            assert on[2] == off[2]
            continue
        assert on == off, f"{off[0]} {off[1]} differs"
    # /home (child chosen), /quiz/math, /quiz/knowledge show the entry; /kidquest renders once a child is chosen.
    assert (entry_pages, page_hits) == (3, 1)


def test_enabled_app_keeps_every_legacy_route(kq_app, monkeypatch):
    def inventory(application):
        return {(route.path, tuple(sorted(getattr(route, "methods", None) or ()))) for route in application.routes}

    monkeypatch.setattr(config, "KIDQUEST_ENABLED", False)
    legacy_app = create_app()
    added = inventory(kq_app) - inventory(legacy_app)

    assert inventory(legacy_app) <= inventory(kq_app)
    assert added == KIDQUEST_ROUTES


def test_kidquest_requests_leave_legacy_tables_untouched(kid_client):
    client = kid_client("alleia")
    before = legacy_snapshot()

    client.get(STATE_URL)
    client.get(THEMES_URL)
    change_theme(client, "kingdom", 1, "legacy-check-1")
    change_theme(client, "space", 2, "legacy-check-2")

    assert legacy_snapshot() == before


def test_admin_clear_keeps_its_legacy_scope(kid_client):
    """KidQuest data is not silently added to /api/admin/clear (plan section 14)."""
    client = kid_client("alleia")
    client.get(STATE_URL)

    response = client.post("/api/admin/clear", json={"password": config.ADMIN_CLEAR_PASSWORD})

    assert response.status_code == 200
    assert [row["child"] for row in table_rows("kidquest_worlds")] == ["alleia"]
