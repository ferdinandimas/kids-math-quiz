"""Signed, expiring KidQuest adult-session tokens and cookie helpers."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import hashlib
import hmac
import json
import secrets
from typing import Any

from fastapi import Response

from app import clock


ADULT_COOKIE_NAME = "kidquest_adult"
TOKEN_VERSION = 1


class AdultSessionInvalid(ValueError):
    """The adult token is missing, malformed, forged, expired, or revoked."""


@dataclass(frozen=True)
class AdultSessionClaims:
    version: int
    expires_at: int
    nonce: str


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    if not value or any(char.isspace() for char in value):
        raise AdultSessionInvalid("invalid token")
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise AdultSessionInvalid("invalid token") from exc


def issue_adult_token(signing_key: str, max_age: int) -> str:
    payload = {
        "v": TOKEN_VERSION,
        "exp": int(clock.now().timestamp()) + max_age,
        "nonce": secrets.token_urlsafe(24),
    }
    encoded = _encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(signing_key.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_encode(signature)}"


def verify_adult_token(token: str, signing_key: str) -> AdultSessionClaims:
    try:
        encoded, signature_raw = token.split(".")
        signature = _decode(signature_raw)
    except (AttributeError, ValueError) as exc:
        raise AdultSessionInvalid("invalid token") from exc
    expected = hmac.new(signing_key.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise AdultSessionInvalid("invalid token")
    try:
        payload: dict[str, Any] = json.loads(_decode(encoded))
        if set(payload) != {"v", "exp", "nonce"}:
            raise ValueError
        claims = AdultSessionClaims(int(payload["v"]), int(payload["exp"]), payload["nonce"])
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AdultSessionInvalid("invalid token") from exc
    if claims.version != TOKEN_VERSION or not isinstance(claims.nonce, str) or len(claims.nonce) < 24:
        raise AdultSessionInvalid("invalid token")
    if claims.expires_at <= int(clock.now().timestamp()):
        raise AdultSessionInvalid("expired token")
    return claims


def nonce_hash(nonce: str) -> str:
    return hashlib.sha256(nonce.encode("utf-8")).hexdigest()


def set_adult_session_cookie(response: Response, token: str, *, max_age: int, secure: bool) -> None:
    response.set_cookie(
        ADULT_COOKIE_NAME,
        token,
        max_age=max_age,
        path="/",
        secure=secure,
        httponly=True,
        samesite="strict",
    )


def clear_adult_session_cookie(response: Response, *, secure: bool) -> None:
    response.delete_cookie(
        ADULT_COOKIE_NAME,
        path="/",
        secure=secure,
        httponly=True,
        samesite="strict",
    )
