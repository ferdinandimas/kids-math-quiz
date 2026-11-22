"""PBKDF2 parent PIN format and the safe hash-generation script."""

import subprocess
import sys

import pytest

from app.services import parent_auth_service as auth
from tests.conftest import REPO_ROOT


def test_parent_pin_hash_round_trip_and_wrong_pin():
    encoded = auth.hash_parent_pin("2468", iterations=auth.MIN_ITERATIONS, salt=b"0123456789abcdef")

    assert encoded.startswith(f"{auth.ALGORITHM}${auth.MIN_ITERATIONS}$")
    assert auth.verify_parent_pin("2468", encoded) is True
    assert auth.verify_parent_pin("2469", encoded) is False


@pytest.mark.parametrize("encoded", ["", "sha256$1$x$y", "pbkdf2_sha256$wat$x$y", "pbkdf2_sha256$100000$x$y"])
def test_malformed_hash_is_rejected_without_raising(encoded):
    assert auth.is_valid_pin_hash(encoded) is False
    assert auth.verify_parent_pin("2468", encoded) is False


def test_verification_uses_constant_time_comparison(monkeypatch):
    encoded = auth.hash_parent_pin("2468", iterations=auth.MIN_ITERATIONS, salt=b"0123456789abcdef")
    calls = []
    original = auth.hmac.compare_digest

    def observed(left, right):
        calls.append((left, right))
        return original(left, right)

    monkeypatch.setattr(auth.hmac, "compare_digest", observed)

    assert auth.verify_parent_pin("2468", encoded) is True
    assert len(calls) == 1 and len(calls[0][0]) == len(calls[0][1]) == auth.DIGEST_BYTES


def test_hash_script_reads_stdin_and_never_accepts_pin_from_argv(tmp_path):
    script = REPO_ROOT / "scripts" / "hash_parent_pin.py"
    env = {"PYTHONPATH": str(REPO_ROOT)}
    generated = subprocess.run(
        [sys.executable, str(script)], input="2468\n", text=True, capture_output=True, cwd=tmp_path, env=env
    )
    refused = subprocess.run(
        [sys.executable, str(script), "2468"], text=True, capture_output=True, cwd=tmp_path, env=env
    )

    assert generated.returncode == 0 and auth.verify_parent_pin("2468", generated.stdout.strip())
    assert refused.returncode != 0
    assert "unrecognized arguments" in refused.stderr
