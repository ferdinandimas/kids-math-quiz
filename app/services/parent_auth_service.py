"""PBKDF2 parent-PIN hashing and verification.

The encoded value is self describing: ``pbkdf2_sha256$iterations$salt$digest``. PINs and encoded
hashes are deliberately never logged here; callers receive only a boolean result.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os


ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 600_000
MIN_ITERATIONS = 100_000
MAX_ITERATIONS = 10_000_000
SALT_BYTES = 16
DIGEST_BYTES = 32


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    if not value or any(char.isspace() for char in value):
        raise ValueError("invalid base64")
    padding = "=" * (-len(value) % 4)
    try:
        return base64.b64decode(value + padding, altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("invalid base64") from exc


def _parse(encoded: str) -> tuple[int, bytes, bytes]:
    try:
        algorithm, iterations_raw, salt_raw, digest_raw = encoded.split("$")
        iterations = int(iterations_raw)
    except (AttributeError, ValueError) as exc:
        raise ValueError("invalid parent PIN hash") from exc
    salt, digest = _decode(salt_raw), _decode(digest_raw)
    if (
        algorithm != ALGORITHM
        or not MIN_ITERATIONS <= iterations <= MAX_ITERATIONS
        or not SALT_BYTES <= len(salt) <= 64
        or len(digest) != DIGEST_BYTES
    ):
        raise ValueError("invalid parent PIN hash")
    return iterations, salt, digest


def hash_parent_pin(pin: str, *, iterations: int = DEFAULT_ITERATIONS, salt: bytes | None = None) -> str:
    if not isinstance(pin, str) or not pin:
        raise ValueError("PIN must not be empty")
    salt = os.urandom(SALT_BYTES) if salt is None else salt
    if not MIN_ITERATIONS <= iterations <= MAX_ITERATIONS or not SALT_BYTES <= len(salt) <= 64:
        raise ValueError("unsupported PBKDF2 parameters")
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations, dklen=DIGEST_BYTES)
    return f"{ALGORITHM}${iterations}${_encode(salt)}${_encode(digest)}"


def is_valid_pin_hash(encoded: str) -> bool:
    try:
        _parse(encoded)
    except (TypeError, ValueError):
        return False
    return True


def verify_parent_pin(pin: str, encoded: str) -> bool:
    try:
        iterations, salt, expected = _parse(encoded)
        candidate = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations, dklen=DIGEST_BYTES)
    except (AttributeError, TypeError, ValueError):
        return False
    return hmac.compare_digest(candidate, expected)
