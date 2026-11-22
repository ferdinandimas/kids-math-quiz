"""KQ-010 browser end-to-end: the first-house loop in headless Chrome against a real server.

Runs tests/browser/kidquest/first_house_e2e.mjs (Node >= 22, no npm dependencies) against a fresh
uvicorn server on a temporary database. Skips with a clear message when Node or Chrome is missing.
Set KQ_E2E_SHOTS=<dir> to also save the screenshot matrix (360/768/1280) and comparison.html.
"""

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

SCRIPT = Path(__file__).with_name("first_house_e2e.mjs")
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
SKIPPED = 77


def node_version() -> int | None:
    node = shutil.which("node")
    if not node:
        return None
    out = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()  # e.g. v22.3.0
    return int(out.lstrip("v").split(".")[0]) if out.startswith("v") else None


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    port = free_port()
    env = {key: value for key, value in os.environ.items() if not key.startswith(("RAILWAY_", "KIDQUEST_"))}
    env.update({
        "DB_PATH": str(tmp_path / "e2e.sqlite3"),
        "KIDQUEST_ENABLED": "true",
        "KIDQUEST_PROFILE_ALLOWLIST": "alleia,althafandra",
        "KIDQUEST_DAILY_ATTEMPT_LIMIT": "3",
    })
    log = open(tmp_path / "server.log", "w")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
                            cwd=REPO_ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                urllib.request.urlopen(base + "/health", timeout=1)
                break
            except OSError:
                if proc.poll() is not None or time.monotonic() > deadline:
                    pytest.fail("e2e server did not start:\n" + (tmp_path / "server.log").read_text())
                time.sleep(0.1)
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


def test_first_house_loop_in_headless_chrome(server):
    version = node_version()
    if version is None or version < 22:
        pytest.skip(f"KidQuest browser e2e needs Node >= 22 (found {version}); install Node to run it.")
    if not Path(CHROME).exists():
        pytest.skip(f"KidQuest browser e2e needs Google Chrome at {CHROME} (set CHROME=/path/to/chrome).")
    command = ["node", str(SCRIPT), "--base", server]
    if os.environ.get("KQ_E2E_SHOTS"):
        command += ["--shots", os.environ["KQ_E2E_SHOTS"]]

    result = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, timeout=600)

    if os.environ.get("KQ_E2E_SHOTS"):
        (Path(os.environ["KQ_E2E_SHOTS"]) / "e2e-log.txt").write_text(result.stdout, encoding="utf-8")
    if result.returncode == SKIPPED:
        pytest.skip(result.stdout.strip().splitlines()[-1])
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-2000:]
    assert result.stdout.strip().splitlines()[-1].endswith("checks passed.")
