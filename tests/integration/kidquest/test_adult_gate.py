"""Adult route availability, authorization, persisted logout, overview, and safe request logs."""

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import create_app
from app.security.adult_session import ADULT_COOKIE_NAME
from app.services.parent_auth_service import MIN_ITERATIONS, hash_parent_pin
from tests.integration.kidquest.conftest import STATE_URL, seed_progress
from tests.integration.kidquest.test_feature_gating import run_legacy_script
from tests.support import select_child


PIN = "2468"
PIN_HASH = hash_parent_pin(PIN, iterations=MIN_ITERATIONS, salt=b"adult-gate-tests")
SIGNING_KEY = "adult-session-test-signing-key-32-bytes-minimum"
SESSION_URL = "/api/kidquest/adult/session"
OVERVIEW_URL = "/api/kidquest/adult/overview"
RESET_URL = "/api/kidquest/adult/children/alleia/reset"


@pytest.fixture
def adult_config(monkeypatch, kidquest_on):
    monkeypatch.setattr(config, "KIDQUEST_PARENT_DASHBOARD_ENABLED", True)
    monkeypatch.setattr(config, "PARENT_PIN_HASH", PIN_HASH)
    monkeypatch.setattr(config, "SESSION_SIGNING_KEY", SIGNING_KEY)
    monkeypatch.setattr(config, "KIDQUEST_ADULT_SESSION_MAX_AGE", 900)


@pytest.fixture
def adult_app(db_path, clock, seeded_random, adult_config):
    return create_app()


@pytest.fixture
def adult_client(adult_app):
    client = TestClient(adult_app)
    response = client.post(SESSION_URL, json={"pin": PIN})
    assert response.status_code == 200
    return client


def assert_adult_required(response):
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "ADULT_AUTH_REQUIRED"


def test_wrong_pin_is_generic_and_does_not_set_a_cookie(adult_app):
    response = TestClient(adult_app).post(SESSION_URL, json={"pin": "0000"})
    assert_adult_required(response)
    assert "set-cookie" not in response.headers


def test_every_protected_adult_route_requires_the_adult_cookie(adult_app):
    client = TestClient(adult_app)
    calls = [
        client.delete(SESSION_URL),
        client.get(OVERVIEW_URL),
        client.post(RESET_URL, json={"scope": "legacy_history", "confirm": "HAPUS-KUIS"},
                    headers={"Idempotency-Key": "adult-auth-test"}),
    ]
    for response in calls:
        assert_adult_required(response)


def test_child_cookie_alone_never_grants_adult_access(adult_app):
    client = TestClient(adult_app)
    select_child(client, "alleia")
    assert_adult_required(client.get(OVERVIEW_URL))


@pytest.mark.parametrize(
    "dashboard,pin_hash,key",
    [
        (False, PIN_HASH, SIGNING_KEY),
        (True, "", SIGNING_KEY),
        (True, PIN_HASH, ""),
        (True, PIN_HASH, "weak"),
    ],
)
def test_adult_routes_are_legacy_404_when_flag_off_or_secrets_not_ready(
    db_path, clock, seeded_random, kidquest_on, monkeypatch, dashboard, pin_hash, key
):
    monkeypatch.setattr(config, "KIDQUEST_PARENT_DASHBOARD_ENABLED", dashboard)
    monkeypatch.setattr(config, "PARENT_PIN_HASH", pin_hash)
    monkeypatch.setattr(config, "SESSION_SIGNING_KEY", key)
    client = TestClient(create_app())

    response = client.post(SESSION_URL, json={"pin": PIN})
    assert response.status_code == 404
    assert response.json() == {"ok": False, "message": "Not found"}


def test_kidquest_disabled_hides_adult_routes_even_with_valid_secrets(
    db_path, clock, seeded_random, monkeypatch
):
    monkeypatch.setattr(config, "KIDQUEST_ENABLED", False)
    monkeypatch.setattr(config, "KIDQUEST_PARENT_DASHBOARD_ENABLED", True)
    monkeypatch.setattr(config, "PARENT_PIN_HASH", PIN_HASH)
    monkeypatch.setattr(config, "SESSION_SIGNING_KEY", SIGNING_KEY)
    response = TestClient(create_app()).post(SESSION_URL, json={"pin": PIN})
    assert response.status_code == 404 and response.json() == {"ok": False, "message": "Not found"}


def test_logout_revokes_a_copied_token_and_expiry_rejects_it(adult_app, clock):
    client = TestClient(adult_app)
    assert client.post(SESSION_URL, json={"pin": PIN}).status_code == 200
    copied = client.cookies[ADULT_COOKIE_NAME]
    assert client.get(OVERVIEW_URL).status_code == 200
    assert client.delete(SESSION_URL).status_code == 200

    # Rebuild the app against the same database: revocation is durable, not process memory.
    replay = TestClient(create_app())
    replay.cookies.set(ADULT_COOKIE_NAME, copied)
    assert_adult_required(replay.get(OVERVIEW_URL))

    fresh = TestClient(adult_app)
    assert fresh.post(SESSION_URL, json={"pin": PIN}).status_code == 200
    clock.advance(seconds=900)
    assert_adult_required(fresh.get(OVERVIEW_URL))


def test_overview_matches_the_prototype_fields_without_creating_missing_worlds(adult_client):
    adult_client.get(STATE_URL)  # No child cookie: proves adult auth is separate; this call is PROFILE_REQUIRED.
    child = TestClient(adult_client.app)
    select_child(child, "alleia")
    assert child.get(STATE_URL).status_code == 200
    seed_progress("alleia")

    payload = adult_client.get(OVERVIEW_URL).json()
    assert payload["ok"] is True
    assert all(set(row) == {
        "child", "world_created", "quest_status", "house_built", "attempt_count", "hints_used", "theme_id"
    } for row in payload["children"])
    # Config order is althafandra, alleia.
    by_child = {row["child"]: row for row in payload["children"]}
    assert by_child["althafandra"]["world_created"] is False
    assert by_child["alleia"] == {
        "child": "alleia", "world_created": True, "quest_status": "COMPLETED", "house_built": True,
        "attempt_count": 3, "hints_used": 2, "theme_id": "perkampungan",
    }


def test_structured_logs_are_one_per_request_and_do_not_leak_sensitive_values(adult_app, caplog):
    caplog.set_level(logging.INFO, logger="kidquest.requests")
    client = TestClient(adult_app)
    pin = PIN
    idem = "never-log-this-idempotency-key"
    login = client.post(SESSION_URL, json={"pin": pin})
    cookie = client.cookies[ADULT_COOKIE_NAME]
    child = TestClient(adult_app)
    select_child(child, "alleia")
    state = child.get(STATE_URL)
    answer = "9876"
    invalid = child.post(
        "/api/kidquest/challenges/missing/answers",
        json={"answer": answer}, headers={"Idempotency-Key": idem},
    )
    assert login.status_code == 200 and state.status_code == 200 and invalid.status_code == 404

    entries = [json.loads(record.message) for record in caplog.records if record.name == "kidquest.requests"]
    assert len(entries) == 3
    for entry in entries:
        assert set(entry) == {"operation", "request_id", "content_version", "result", "latency_ms", "error_code"}
        assert entry["request_id"] and entry["latency_ms"] >= 0
    assert invalid.headers["x-request-id"]
    combined = "\n".join(record.message for record in caplog.records)
    for secret in (pin, PIN_HASH, answer, cookie, idem):
        assert secret not in combined


def test_adult_router_active_does_not_change_any_legacy_response_bytes(
    tmp_path, monkeypatch, clock, adult_config
):
    monkeypatch.setattr(config, "KIDQUEST_PARENT_DASHBOARD_ENABLED", False)
    without_adult = run_legacy_script(tmp_path, monkeypatch, "adult-off", enabled=True)
    monkeypatch.setattr(config, "KIDQUEST_PARENT_DASHBOARD_ENABLED", True)
    with_adult = run_legacy_script(tmp_path, monkeypatch, "adult-on", enabled=True)

    assert with_adult == without_adult
