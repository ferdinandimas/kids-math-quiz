"""GET /kidquest and the KidQuest entry links on legacy pages (KQ-010)."""

import json
import re

import pytest
from fastapi.testclient import TestClient
from jinja2 import Environment, FileSystemLoader

from app import config
from app.main import create_app
from tests.conftest import REPO_ROOT
from tests.integration.kidquest.conftest import PAGE_URL, STATE_URL, table_rows
from tests.support import query, select_child

TEMPLATES = REPO_ROOT / "app" / "web" / "templates"
ENTRY_BLOCK = re.compile(r"\{% if kidquest_entry %\}.*?\{% endif %\}", re.S)


def boot_of(response) -> dict:
    match = re.search(r'<script id="kq-boot" type="application/json">(.*?)</script>', response.text, re.S)
    assert match, "boot JSON missing"
    return json.loads(match.group(1))


# --- The page ----------------------------------------------------------------------------------


def test_page_renders_for_an_allowlisted_child(kid_client, kq_app):
    client = kid_client("alleia")
    response = client.get(PAGE_URL)

    assert response.status_code == 200 and response.headers["content-type"].startswith("text/html")
    assert "set-cookie" not in response.headers  # Read-only, like the API.
    html = response.text
    for asset in ("/static/css/base.css", "/static/css/kidquest-tokens.css", "/static/css/kidquest.css", "/static/js/kidquest.js"):
        assert asset in html
    assert 'class="kq-app profile-theme-purple"' in html  # Same accent rule as quiz.html.
    assert "user-scalable=no" not in html and "maximum-scale" not in html  # Zoom stays allowed (200% text).
    boot = boot_of(response)
    assert boot["child"] == "alleia" and boot["name"] == "Alleia"
    assert boot["strings"] == kq_app.state.kidquest_catalog.ui_strings
    assert boot["links"] == {"home": "/home", "quiz": "/quiz/math", "stats": "/stats"}  # Legacy Quiz and Statistics stay reachable.
    assert boot["dev"] is True
    assert table_rows("kidquest_worlds") == []  # Rendering the page creates nothing; the script reads the state.


def test_page_uses_the_blue_accent_for_the_other_child(kid_client):
    assert 'profile-theme-blue' in kid_client("althafandra").get(PAGE_URL).text


def test_page_is_not_in_development_mode_on_railway(kid_client, monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    assert boot_of(kid_client("alleia").get(PAGE_URL))["dev"] is False


def test_page_child_comes_only_from_the_session(kid_client):
    response = kid_client("alleia").get(PAGE_URL, params={"child": "althafandra"}, headers={"X-Child": "althafandra"})

    assert boot_of(response)["child"] == "alleia"


@pytest.mark.parametrize("setup", ["no session", "no child", "unknown cookie", "not allowlisted", "empty allowlist"])
def test_page_redirects_like_a_legacy_unknown_page_when_not_allowed(kid_client, monkeypatch, setup):
    client = kid_client("alleia" if setup in ("not allowlisted", "empty allowlist") else None)
    if setup == "no child":
        client.get("/home")
    if setup == "unknown cookie":
        client.cookies.set(config.COOKIE_NAME, "not-a-real-session")
    if setup == "not allowlisted":
        monkeypatch.setattr(config, "KIDQUEST_PROFILE_ALLOWLIST", ("althafandra",))
    if setup == "empty allowlist":
        monkeypatch.setattr(config, "KIDQUEST_PROFILE_ALLOWLIST", ())
    unknown = client.get("/no-such-page", follow_redirects=False)

    response = client.get(PAGE_URL, follow_redirects=False)

    assert (response.status_code, response.headers["location"]) == (303, "/home")
    assert (response.content, sorted(response.headers.items())) == (unknown.content, sorted(unknown.headers.items()))
    assert table_rows("kidquest_worlds") == []


def test_page_does_not_exist_when_kidquest_is_disabled(app, client):
    select_child(client, "alleia")
    assert not [route for route in app.routes if getattr(route, "path", "") == PAGE_URL]
    response = client.get(PAGE_URL, follow_redirects=False)
    assert (response.status_code, response.headers["location"]) == (303, "/home")


def test_page_refuses_when_kidquest_is_switched_off_after_start(kid_client, monkeypatch):
    client = kid_client("alleia")
    monkeypatch.setattr(config, "KIDQUEST_ENABLED", False)
    response = client.get(PAGE_URL, follow_redirects=False)
    assert (response.status_code, response.headers["location"]) == (303, "/home")


def test_page_assets_are_served(kid_client):
    client = kid_client("alleia")
    for path in ("/static/js/kidquest.js", "/static/css/kidquest.css", "/static/css/kidquest-tokens.css"):
        assert client.get(path).status_code == 200, path


def test_page_assets_never_show_money_or_branch_on_theme_or_building():
    script = (REPO_ROOT / "static" / "js" / "kidquest.js").read_text(encoding="utf-8")
    css = (REPO_ROOT / "static" / "css" / "kidquest.css").read_text(encoding="utf-8") + \
        (REPO_ROOT / "static" / "css" / "kidquest-tokens.css").read_text(encoding="utf-8")
    def mentions(text, name):
        return re.search(rf"(?<![\w-]){name}(?![\w-])", text) is not None

    for theme_id in ("perkampungan", "kingdom", "city"):
        assert not mentions(script, theme_id) and not mentions(css, theme_id), theme_id
    for entity in ("starter_house", "garden", "bakery", "park", "bridge", "market_stall", "tutorial_zone", "bridge_zone", "expansion_zone", "Q001"):
        assert not mentions(script, entity), entity
    assert "popup-reward-coin" not in script and "data-theme=" not in css


# --- Entry links on legacy pages ------------------------------------------------------------------


def test_home_and_quiz_show_the_entry_for_an_allowlisted_child(kid_client):
    client = kid_client("alleia")

    home = client.get("/home").text
    quiz = client.get("/quiz/math").text

    assert '<a class="stats-link" href="/kidquest" data-testid="kidquest-entry">' in home and "Masuk Dunia KidQuest: Alleia" in home
    assert '<a class="header-stats-link" href="/kidquest" data-testid="kidquest-entry">Dunia KidQuest</a>' in quiz
    assert 'href="/stats"' in home and 'href="/stats"' in quiz  # Statistics stays where it was.


@pytest.mark.parametrize("setup", ["no child", "not allowlisted"])
def test_entry_is_hidden_unless_the_selected_child_is_allowlisted(kid_client, monkeypatch, setup):
    monkeypatch.setattr(config, "KIDQUEST_PROFILE_ALLOWLIST", ("althafandra",))
    client = kid_client("alleia" if setup == "not allowlisted" else None)

    assert "kidquest" not in client.get("/home").text.lower()
    if setup == "not allowlisted":
        assert "kidquest" not in client.get("/quiz/math").text.lower()


def test_entry_is_hidden_when_kidquest_is_disabled(client):
    select_child(client, "alleia")
    assert "kidquest" not in client.get("/home").text.lower()
    assert "kidquest" not in client.get("/quiz/math").text.lower()
    assert "kidquest" not in client.get("/quiz/knowledge").text.lower()


@pytest.mark.parametrize("template, context", [
    ("home.html", {"DAILY_LIMIT": 400, "REWARD_PER_CORRECT": 50}),
    ("quiz.html", {"child": "alleia", "answered_today": 3, "correct_count": 2, "earned": 100, "level": "Pemula",
                   "DAILY_LIMIT": 400, "REWARD_PER_CORRECT": 50, "quiz_type": "math"}),
    ("quiz.html", {"child": "althafandra", "answered_today": 0, "correct_count": 0, "earned": 0, "level": "Mahir",
                   "DAILY_LIMIT": 400, "REWARD_PER_CORRECT": 100, "quiz_type": "knowledge"}),
])
def test_entry_block_renders_nothing_when_off(template, context):
    """With no entry, the template renders exactly as it does with the entry block cut out of the source."""
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    source = (TEMPLATES / template).read_text(encoding="utf-8")
    assert len(ENTRY_BLOCK.findall(source)) == 1
    without_block = env.from_string(ENTRY_BLOCK.sub("", source))

    for off in ({}, {"kidquest_entry": None}):
        assert env.get_template(template).render(**context, **off) == without_block.render(**context)


def test_entering_through_the_page_then_the_api_uses_the_same_session(kid_client):
    client = kid_client("alleia")
    assert client.get(PAGE_URL).status_code == 200
    state = client.get(STATE_URL)
    assert state.status_code == 200 and state.json()["world"]["theme_id"] == "perkampungan"
    assert query("SELECT child FROM kidquest_worlds") == [{"child": "alleia"}]


def test_enabled_app_without_allowlisted_children_keeps_home_identical(tmp_path, monkeypatch, clock, db_path, seeded_random):
    monkeypatch.setattr(config, "KIDQUEST_ENABLED", True)
    monkeypatch.setattr(config, "KIDQUEST_PROFILE_ALLOWLIST", ())
    on = TestClient(create_app())
    select_child(on, "alleia")
    assert "kidquest" not in on.get("/home").text.lower()
