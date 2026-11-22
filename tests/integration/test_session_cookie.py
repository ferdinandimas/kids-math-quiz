"""Every session cookie goes through one helper with explicit attributes."""

import pytest

from app import config
from app.config import COOKIE_NAME
from tests.conftest import REPO_ROOT
from tests.support import select_child

# Each request reaches a different former inline set_cookie call site.
COOKIE_SETTING_REQUESTS = {
    "get_or_create (new session)": ("GET", "/home", None),
    "get_or_create (unknown session id)": ("GET", "/home", "not-a-known-session"),
    "api_stats": ("GET", "/api/stats", None),
    "api_question": ("GET", "/api/question", None),
}


def set_cookie_header(client, method, path, cookie):
    if cookie:
        client.cookies.set(COOKIE_NAME, cookie)
    response = client.request(method, path, follow_redirects=False)
    return response.headers.get_list("set-cookie")


@pytest.mark.parametrize("call_site", COOKIE_SETTING_REQUESTS)
def test_local_cookie_attributes(make_client, call_site):
    headers = set_cookie_header(make_client(), *COOKIE_SETTING_REQUESTS[call_site])

    assert len(headers) == 1
    cookie = headers[0]
    assert cookie.startswith(f"{COOKIE_NAME}=")
    for attribute in ("HttpOnly", "SameSite=lax", "Path=/", "Max-Age=31536000"):
        assert attribute in cookie
    assert "Secure" not in cookie


@pytest.mark.parametrize("call_site", COOKIE_SETTING_REQUESTS)
def test_secure_flag_follows_session_cookie_secure(make_client, monkeypatch, call_site):
    monkeypatch.setattr(config, "SESSION_COOKIE_SECURE", True)

    headers = set_cookie_header(make_client(), *COOKIE_SETTING_REQUESTS[call_site])

    assert len(headers) == 1 and "Secure" in headers[0] and "HttpOnly" in headers[0]


def test_max_age_is_configurable(client, monkeypatch):
    monkeypatch.setattr(config, "SESSION_COOKIE_MAX_AGE", 600)

    assert "Max-Age=600" in client.get("/home").headers["set-cookie"]


def test_an_existing_session_is_not_reissued(client):
    client.get("/home")

    assert "set-cookie" not in client.get("/home").headers
    assert "set-cookie" not in client.get("/api/stats").headers


def test_local_http_flow_keeps_working(client):
    select_child(client, "alleia")

    assert client.get("/api/question").json()["ok"] is True


def test_no_inline_cookie_writes_remain():
    sources = {
        path.relative_to(REPO_ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in (REPO_ROOT / "app").rglob("*.py")
    }
    writers = {name: text.count("set_cookie(") for name, text in sources.items() if "set_cookie(" in text}

    assert writers == {"app/security/adult_session.py": 1, "app/services/session_service.py": 1}
