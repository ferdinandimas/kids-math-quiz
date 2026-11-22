---
id: KQ-001
title: Establish test and characterization baseline
status: DONE
owner: senior-dev
depends_on: []
milestone: M0
updated: 2026-11-21
---

# KQ-001 — Establish test and characterization baseline

## Outcome

The existing quiz application has a repeatable automated safety net before KidQuest changes begin.

## Source references

- [Implementation plan — M0](../KidQuest_Implementation_Plan.md)
- [PRD — §3 verified repository baseline, §4.3 test baseline](../KidQuest_Build_Your_World_PRD_v1.4.md)

## Current-code hazards to handle first

- **Import-time database binding:** `app/config.py` reads `DB_PATH` at import; `app/db/sqlite.py` binds it via `from app.config import DB_PATH`; `app/main.py` runs `app = create_app()` at import, which migrates `math_app.sqlite3` in the working directory. Set `DB_PATH` before any `app.*` import (for example in `tests/conftest.py` at module top), or make `db_conn` read the path at call time. Changing the environment after import has no effect.
- **Working-directory paths:** `StaticFiles(directory="static")` and `Jinja2Templates(directory="app/web/templates")` are relative. Run tests from the repository root or make the paths absolute.
- **Python version:** the code uses PEP 604 unions in evaluated signatures (`app/db/repo.py`, `app/services/question_service.py`), so it needs Python 3.10+. `Readme.md` says 3.9+. Docker uses 3.12; document 3.12 as the supported version.
- **Unseeded randomness:** `QuestionService.pick_adaptive` uses the module-level `random`; tests seed or patch it.
- **Time:** `date.today()` and `datetime.now()` are called directly in `session_service.py`, `question_service.py`, `stats_service.py`, and `routes.py`. Until the KQ-002 clock exists, freeze time by patching each module.

## Scope

1. Inventory current routes, database migrations, profile isolation, answer submission, statistics, and reset behavior.
2. Add `requirements-dev.txt` (pytest, HTTPX/TestClient) without changing production runtime behavior.
3. Neutralize the hazards above with the smallest change to `create_app`/`db_conn` that keeps route behavior identical.
4. Create isolated temporary-database fixtures and deterministic clock/random helpers.
5. Add characterization tests for current routes, migrations 1–7 (empty and populated legacy database), profile isolation, answer persistence, bank behavior, and statistics.
6. Characterize these current behaviors explicitly so later tasks can prove their changes:
   - The legacy day follows the container timezone (UTC by default in `python:3.12-slim` unless `TZ` is set), so rollover is currently 07:00 Asia/Jakarta. Record the deployed container's timezone.
   - A question served before rollover and answered after it returns the out-of-sync error, because `SessionService.get_or_create` resets the session and `cleanup_expired_question_data` deletes the prior day's bank.
   - `/api/stats` returns both children's seven-day recap to any session.
   - `/api/admin/clear` deletes all legacy data for both children and runs `VACUUM`; the password defaults to `masukaja`.
   - Duplicate concurrent `/api/answer` submissions can double-count today. Record this as a known defect fixed by KQ-003, for example as an expected-failure test.
7. Document the canonical local test command and supported Python version in `Readme.md`.

## Deliverables

- `requirements-dev.txt` and test configuration.
- Reusable application/client/database fixtures.
- Legacy behavior test suite and testing instructions.

## Acceptance criteria

- [x] A clean checkout on Python 3.12 can install test dependencies and run the suite with one documented command.
- [x] Tests never read or mutate a developer's database: importing the app under test creates no `math_app.sqlite3` in the working directory.
- [x] Migrations 1–7 apply from an empty database, apply to a populated legacy fixture without losing counters, and are idempotent.
- [x] Core quiz, answer, statistics, profile-isolation, and reset behaviors are characterized, including every item in scope step 6.
- [x] Existing application behavior is unchanged except for testability hooks.

## Verification

- Run the documented full test command twice against fresh temporary databases.
- Confirm that no `math_app.sqlite3` exists in the repository root after the run.
- Record test count, pass/fail result, and any intentionally preserved legacy behavior.

## Out of scope

- KidQuest schema, UI, economy, or product behavior changes.
- Fixing any characterized defect (clock → KQ-002, answer race → KQ-003, admin secret → KQ-002).

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Task packet created. |
| 2026-11-21 | planning | NOT_STARTED | Added import-time DB, working-directory, Python-version, day-boundary, cross-child stats, and admin-clear characterization requirements. |
| 2026-11-21 | senior-dev | IN_PROGRESS | Claimed task. No dependencies. Worktree has unrelated user edits in `Readme.md` (Product planning section) and untracked `docs/`; both preserved. |
| 2026-11-21 | senior-dev | IN_PROGRESS | Inventory: 17 app routes (`/`, `/start`, `/home`, `/home/{child}`, `/quiz`, `/quiz/{quiz_type}`, `/stats`, `/api/stats`, `/api/question`, `POST /api/answer`, `POST /api/admin/clear`, `/manifest.json`, `/manifest.webmanifest`, `/health`, `/favicon.ico`, `/.well-known/{path}`) plus FastAPI docs routes and the `/static` mount; migrations 1–7 in `app/db/migrations.py`; per-child `child_daily`, per-(session, child, quiz type) `session_current_questions`; `Repo.clear_database` deletes five tables then `VACUUM`. `POST /api/logout` does not exist (matches PRD §3.5). |
| 2026-11-21 | senior-dev | IN_PROGRESS | Decision: testability hooks kept to 17 inserted / 5 deleted lines in `app/`. (1) `app/config.py` adds `DEFAULT_DB_PATH` and `get_db_path()`; `app/db/sqlite.py::db_conn` calls it, so `DB_PATH` resolves at connection time. Same default and same env var, so production is unchanged. `config.DB_PATH` is kept for compatibility. (2) `StaticFiles` and `Jinja2Templates` use absolute paths derived from `__file__`. They resolve to the same directories when run from the repo root (`run.sh`) or `/app` (Docker). Original CRLF/LF line endings were preserved byte-for-byte to keep the diff minimal. |
| 2026-11-21 | senior-dev | IN_PROGRESS | Decision: `tests/conftest.py` sets `DB_PATH` to a `tempfile.mkdtemp()` file and pops `ADMIN_CLEAR_PASSWORD` before any `app.*` import. The import-time `app.main.app` migrates that temp file, which is removed in `pytest_unconfigure`. Each test gets `tmp_path` DB (`db_path` fixture), a `FrozenClock` patched into `session_service`, `question_service`, `stats_service`, and `routes` (default 2026-11-21 10:00 Asia/Jakarta, UTC container), and a seeded `random.Random` replacing `question_service.random`. `tests/` is a package so `tests.support` imports explicitly. No `pytest.ini`/`pyproject.toml` was added; the root is outside my edit area and pytest defaults suffice. |
| 2026-11-21 | senior-dev | IN_PROGRESS | Deployed container timezone: **not directly observed.** The repo is not linked to a Railway project (`railway status` → "No linked project found") and no Docker daemon is available locally. Repo config: the `Dockerfile` (`python:3.12-slim`) and `railway.toml` set no `TZ`, so the container runs in the image default UTC. That means legacy rollover at 07:00 Asia/Jakarta. **Operator to confirm** with `railway ssh` → `date +%Z` (or check `TZ` in Railway service variables). |
| 2026-11-21 | senior-dev | IN_PROGRESS | Known defect recorded, not fixed: `test_concurrent_duplicate_answer_counts_once` is `xfail(strict=True, raises=AssertionError)`. A barrier wrapped around `QuestionService.evaluate_answer` holds two same-session requests after the active-question check. With `--runxfail` it fails with `assert (2, 2, 100) == (1, 1, 50)`: answered, correct, and earned are double-counted. Strict mode makes KQ-003 remove the marker once fixed. |
| 2026-11-21 | senior-dev | IN_PROGRESS | Intentionally preserved legacy behavior pinned by tests: legacy day = process-local `date.today()` (verified with real `TZ` switching between Pacific/Kiritimati and Pacific/Pago_Pago); UTC container rolls over at 07:00 WIB, not 00:00 WIB; a question served at 06:58 WIB and answered at 07:00 WIB returns 400 `Soal tidak sinkron. Klik Next lagi.` (session reset, active question dropped); the next issuance deletes the prior day's bank and served history; `/api/stats` returns both children's `recap7` to any session, including one with no child; `/api/admin/clear` accepts default `masukaja` (whitespace-stripped), deletes all five legacy tables for both children, keeps `schema_migrations`, runs `VACUUM` (traced) and returns 401 `Password salah.` otherwise; `sessions` counters are shared across children within one browser session (UI reads `child_daily`); a quota-rejected answer (409) leaves the question active; cookie is `HttpOnly; SameSite=lax` with no `Secure`/`Max-Age`; `/api/stats.generated_at` is naive container-local time. |
| 2026-11-21 | senior-dev | IN_PROGRESS | Note: the suite emits 7 pre-existing `DeprecationWarning`s: Starlette `TemplateResponse(name, ...)` argument order in `routes.py`, and anyio's `BlockingPortal` alias inside Starlette 0.41's TestClient. These are legacy and dependency warnings, left untouched because the packet allows no behavior change. |
| 2026-11-21 | senior-dev | IN_REVIEW | Verification: `rtk .venv/bin/python -m pytest -q` run twice → `105 passed, 1 xfailed` both times (~11 s). `test -e math_app.sqlite3` → absent; `find . -name '*.sqlite3*' -not -path './.venv/*'` → none. Clean-checkout simulation: rsync worktree (no `.venv`/`.git`) to scratchpad, `python3 -m venv .venv` (3.12.7), `pip install -r requirements-dev.txt`, `python -m pytest -q` twice → `105 passed, 1 xfailed` both; no `math_app.sqlite3` created. Runtime smoke: `uvicorn app.main:app` with temp `DB_PATH` → `/health` `{"ok":true}`, `/static/css/base.css` 200, `/home` 200. Counts per file: routes 29, known behaviors 17 (incl. 1 xfail), migrations 8, profile isolation 6, import safety 4, question bank 26, question service 16. |
| 2026-11-21 | lead | DONE | Lead review passed. Re-ran full suite: 105 passed, 1 xfailed; `test_known_legacy_behaviors.py` 5× consecutive: stable (strict xfail holds); no `math_app.sqlite3` created. `app/` diff limited to 17-line testability hooks (call-time `DB_PATH`, absolute static/template paths); conftest isolates `DB_PATH` before any `app.*` import; `Readme.md` user Product-planning section preserved; dev deps separate from runtime. Follow-up: operator confirms Railway container TZ (`railway ssh` → `date +%Z`). |

## Completion handoff

- **Summary:** Added a repeatable pytest characterization suite (106 tests: 105 pass, 1 strict xfail for the KQ-003 race). It isolates every test on a temporary SQLite database with a frozen clock and seeded randomness. Import-time hazards are neutralized with two minimal hooks: call-time `DB_PATH` resolution and absolute static/template paths. Readme now documents Python 3.12 and `python -m pytest`.
- **Files changed:** `app/config.py`, `app/db/sqlite.py`, `app/main.py`, `app/web/templates.py` (testability hooks only); `requirements-dev.txt` (new); `tests/__init__.py`, `tests/conftest.py`, `tests/support.py`, `tests/unit/__init__.py`, `tests/unit/test_question_bank.py`, `tests/unit/test_question_service.py`, `tests/integration/__init__.py`, `tests/integration/test_legacy_routes.py`, `tests/integration/test_legacy_migrations.py`, `tests/integration/test_profile_isolation.py`, `tests/integration/test_known_legacy_behaviors.py`, `tests/integration/test_import_safety.py` (new); `Readme.md` (Requirements, Testing, structure; the user's Product planning section preserved); this packet and the tracker row.
- **Migrations/data impact:** None. No schema, migration, or response-shape change.
- **Verification performed:** See the IN_REVIEW execution-log entry: full suite twice (105 passed, 1 xfailed each), clean-checkout install and run twice, no `math_app.sqlite3` in the repo root, uvicorn smoke test.
- **Commit:** pending lead commit
- **Follow-ups:** (1) Operator to confirm the deployed container timezone (`railway ssh` → `date +%Z`). Expected UTC. (2) KQ-002 must update the day-boundary characterizations (`test_in_a_utc_container_*`, `test_question_served_before_rollover_*`) and `FrozenClock` when the injectable clock lands; `get_db_path()` already provides call-time `DB_PATH`. (3) KQ-003 removes the `xfail` from `test_concurrent_duplicate_answer_counts_once`. (4) Optional: add a root `pytest.ini` (outside the backend edit area) to filter the legacy deprecation warnings.
