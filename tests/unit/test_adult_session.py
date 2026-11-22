"""HMAC adult-session tokens and strict cookie attributes."""

import base64

import pytest
from fastapi import Response

from app.security.adult_session import (
    ADULT_COOKIE_NAME,
    AdultSessionInvalid,
    clear_adult_session_cookie,
    issue_adult_token,
    set_adult_session_cookie,
    verify_adult_token,
)


KEY = "k" * 32


def test_valid_token_and_expiry_use_the_application_clock(clock):
    token = issue_adult_token(KEY, 60)
    claims = verify_adult_token(token, KEY)
    assert claims.version == 1 and claims.expires_at > 0 and claims.nonce

    clock.advance(seconds=60)
    with pytest.raises(AdultSessionInvalid, match="expired"):
        verify_adult_token(token, KEY)


@pytest.mark.parametrize("mutation", ["payload", "signature", "wrong_key", "truncated"])
def test_tampered_wrong_key_and_truncated_tokens_are_rejected(clock, mutation):
    token = issue_adult_token(KEY, 60)
    payload, signature = token.split(".")
    if mutation == "payload":
        raw = bytearray(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        raw[-2] ^= 1
        payload = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
        candidate, key = f"{payload}.{signature}", KEY
    elif mutation == "signature":
        candidate, key = f"{payload}.{signature[:-1]}{'A' if signature[-1] != 'A' else 'B'}", KEY
    elif mutation == "wrong_key":
        candidate, key = token, "z" * 32
    else:
        candidate, key = token[:12], KEY
    with pytest.raises(AdultSessionInvalid):
        verify_adult_token(candidate, key)


@pytest.mark.parametrize("secure", [False, True])
def test_adult_cookie_attributes_in_dev_and_production(secure):
    response = Response()
    set_adult_session_cookie(response, "token", max_age=900, secure=secure)
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{ADULT_COOKIE_NAME}=token")
    assert all(value in cookie for value in ("HttpOnly", "SameSite=strict", "Path=/", "Max-Age=900"))
    assert ("Secure" in cookie) is secure

    logout = Response()
    clear_adult_session_cookie(logout, secure=secure)
    assert "Max-Age=0" in logout.headers["set-cookie"]
