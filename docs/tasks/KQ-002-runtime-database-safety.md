---
id: KQ-002
title: Harden runtime and database safety
status: DONE
owner: senior-dev
depends_on: [KQ-001]
milestone: M1
updated: 2026-11-21
---

# KQ-002 — Harden runtime and database safety

## Outcome

Runtime configuration and SQLite access are safe, deterministic, and transactional enough for KidQuest features.

## Source references

- [Implementation plan — §2 delivery rules, §5 M1](../KidQuest_Implementation_Plan.md)
- [PRD — §4.2 calendar, §15 configuration, §18 operational safety](../KidQuest_Build_Your_World_PRD_v1.4.md)

## Current-code facts

- `app/db/sqlite.py::db_conn` exists but sets only `row_factory`; there are no foreign keys, no busy timeout, and no transaction helper.
- Every `Repo` method opens its own connection and commits, so no multi-step operation can be atomic today.
- Time comes from `date.today()`/`datetime.now()` in `session_service.py`, `question_service.py`, `stats_service.py`, and `routes.py` (`quiz_page`, `api_stats`).
- The session cookie is set inline with `httponly=True, samesite="lax"` in at least five places, with no `Secure` flag, max age, or path.
- `ADMIN_CLEAR_PASSWORD` defaults to `masukaja` in `app/config.py`.

## Scope

1. Add `APP_TIMEZONE` (default `Asia/Jakarta`) and an injectable clock (`app/clock.py`) resolved through `zoneinfo`. Add `tzdata` to `requirements.txt`. Replace every direct `date.today()`/`datetime.now()` call.
2. Document the day-boundary cutover in `docs/Database_Operations.md`: if production ran in UTC, existing `child_daily` rows are UTC-day keyed; rollover moves from 07:00 to 00:00 WIB; historical rows are not rewritten; the cutover shortens one legacy day to 17–24 hours, and only a rollback to UTC-keyed code can create a 31-hour day.
3. Add `SESSION_COOKIE_SECURE` (true in production), explicit max age and path, and one cookie helper used everywhere a session cookie is set.
4. Make `db_conn` resolve `DB_PATH` at call time and set `PRAGMA foreign_keys = ON`, an explicit busy timeout, and `row_factory` on every connection. Enable WAL only after volume and backup tests pass.
5. Add a unit-of-work helper (for example `transaction(immediate=True)` in `app/db/sqlite.py`) that opens one connection, issues `BEGIN IMMEDIATE`, yields it, and commits or rolls back. Repository methods used in transactions get an optional connection parameter. KQ-003 and all KidQuest mutations use it.
6. Refuse startup in production (for example when `RAILWAY_ENVIRONMENT` is set) when `ADMIN_CLEAR_PASSWORD` is unset or equals `masukaja`.
7. Add `scripts/backup_db.py` (`sqlite3.Connection.backup()` + `PRAGMA integrity_check`) and `scripts/verify_backup.py`; document the backup → verify → migrate → deploy → smoke → rollback sequence and a manual retention procedure.
8. Add tests for clock boundaries, pragmas, transaction commit/rollback, cookie modes, and the production secret check.

## Deliverables

- `app/clock.py`, updated `app/config.py`, and the cookie helper.
- Connection factory with pragmas and the unit-of-work helper.
- Backup/verify scripts and `docs/Database_Operations.md`.
- Safety regression tests.

## Acceptance criteria

- [x] Every application database connection enables foreign keys and the configured busy timeout.
- [x] The unit-of-work helper commits all statements together and rolls back all of them on an exception (tested).
- [x] Frozen-clock tests prove rollover at 00:00 Asia/Jakarta regardless of the process `TZ`.
- [x] No direct `date.today()`/`datetime.now()` remains in application code.
- [x] The day-boundary cutover effect on existing `child_daily` rows is documented.
- [x] Local HTTP development still works; production cookies are `Secure` with explicit max age and path.
- [x] Production startup fails with an actionable message when the admin password is unset or the legacy default.
- [x] A backup restores into a fresh location and passes `PRAGMA integrity_check`.
- [x] KQ-001 tests remain green, apart from intentionally updated day-boundary characterizations recorded in the execution log.

## Verification

- Run the full test suite.
- Exercise backup, integrity check, and restore on a disposable database; record exact commands and results.
- Start the app with production environment variables and the default password; confirm it refuses to start.

## Out of scope

- New KidQuest tables or the answer-flow transaction itself (KQ-003).

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Task packet created. |
| 2026-11-21 | planning | NOT_STARTED | Added unit-of-work helper, call-time DB_PATH, tzdata, UTC→Jakarta cutover note, cookie helper, and production admin-secret check. |
| 2026-11-21 | senior-dev | IN_PROGRESS | Claimed after lead approval of KQ-001 (DONE). Lead review points recorded: single `app/clock.py` for all call sites incl. `generated_at`; FrozenClock targets the new clock; `tzdata` in runtime requirements; admin-secret check at app startup only (Docker build/entrypoint migrate must keep working, with a test); unit of work with rollback and writer-serialization tests; one cookie helper with `Secure` only when `SESSION_COOKIE_SECURE`; operations doc with cutover note, runbook, and retention; WAL deferred unless backup/restore is proven with it. |
| 2026-11-21 | senior-dev | IN_PROGRESS | Clock: added `app/clock.py` (`Clock` in `APP_TIMEZONE`, default `Asia/Jakarta`; `now()`, `today()`, `today_str()`, `now_str()`; `set_clock()`/`get_clock()` injection). Replaced every direct call site: `session_service.today_str`/`now_str`, `question_service.today_str`, `stats_service.last_n_days`, and `routes.py` `quiz_page` and `api_stats` (`generated_at` goes through `session_svc.now_str()` → clock). An invalid `APP_TIMEZONE` raises `ConfigError` at import. `tzdata==2026.6` added to runtime `requirements.txt` (and removed from `requirements-dev.txt`, which includes it via `-r`). |
| 2026-11-21 | senior-dev | IN_PROGRESS | Decision: `now_str()` keeps the legacy format `YYYY-MM-DDTHH:MM:SS` (no offset) but is now Jakarta wall time, so the `sessions.created_at` and `recap7.generated_at` shapes are unchanged. |
| 2026-11-21 | senior-dev | IN_PROGRESS | SQLite: `db_conn` now sets `timeout`, `PRAGMA foreign_keys = ON`, `PRAGMA busy_timeout = SQLITE_BUSY_TIMEOUT_MS` (default 5000), and `row_factory` on every connection. Added `transaction(immediate=True)` context manager: one connection, `isolation_level=None`, `BEGIN IMMEDIATE`, `COMMIT` or `ROLLBACK` on any exception (including a failed `COMMIT`). **WAL deferred**: journal mode stays `DELETE` (asserted in a test). Decision: no `conn=` parameters were added to `Repo` methods yet. No current code path runs inside a transaction, and KQ-003 scope item 4 owns the connection-accepting variants for the answer flow. Existing `Repo` methods are unchanged and still pass. |
| 2026-11-21 | senior-dev | IN_PROGRESS | Cookies: one helper `set_session_cookie()` in `app/services/session_service.py` replaces all 5 inline `set_cookie` calls (2 in `get_or_create`, `quiz_page`, `api_stats`, `api_question`). It keeps `HttpOnly` and `SameSite=Lax`, adds explicit `Path=/` and `Max-Age` (`SESSION_COOKIE_MAX_AGE`, default 365 days), and adds `Secure` only when `SESSION_COOKIE_SECURE` is true (default: true in production, false locally). Decision for lead: 365 days was chosen because the old cookie had no expiry (browser-session lifetime, long-lived on tablets/PWAs) and the cookie is not refreshed on later requests. A short max age would make children re-select their profile periodically. It is configurable. |
| 2026-11-21 | senior-dev | IN_PROGRESS | Production check: `validate_startup_config()` in `app/config.py` is called first thing in `create_app()` only. Production means `RAILWAY_ENVIRONMENT`, `RAILWAY_ENVIRONMENT_NAME`, or `RAILWAY_ENVIRONMENT_ID` is set. It raises `ConfigError` with an actionable message when `ADMIN_CLEAR_PASSWORD` is unset, blank, or `masukaja`. `scripts/migrate.py` and the Dockerfile seed step never call it. `docker-entrypoint.sh` got two overridable paths, `APP_DIR` (default `/app`) and `SEED_DB` (default `$APP_DIR/seed/kids-quiz.sqlite3`), so a test can run the real entrypoint. Container behavior is unchanged. |
| 2026-11-21 | senior-dev | IN_PROGRESS | Backup: `app/db/backup.py` (read-only source via `mode=ro` URI, `Connection.backup()`, integrity and foreign-key checks, row counts, SHA-256 schema+row digest) plus CLIs `scripts/backup_db.py` (defaults to `DB_PATH` → `<db dir>/backups/<name>-YYYYMMDD-HHMMSS.sqlite3` in `APP_TIMEZONE`; never overwrites) and `scripts/verify_backup.py` (integrity, schema_migrations present, test restore into a fresh location with exact digest match, optional `--restore-to` and `--compare-with`). Backups are never deleted automatically; there is no auto-backup in the entrypoint, so retention stays manual. |
| 2026-11-21 | senior-dev | IN_PROGRESS | Docs: `docs/Database_Operations.md` covers configuration, unit of work, WAL deferral, UTC→Jakarta cutover with a fill-in cutover log, backup/verify/restore commands, the backup → verify → migrate → deploy → smoke → rollback runbook, and a manual retention procedure. `Readme.md`: dependency list, a Notes pointer, and a corrected Railway section (it described Railpack/`run.sh`; the deploy actually uses the Dockerfile + entrypoint). The user's Product planning section is preserved. |
| 2026-11-21 | senior-dev | IN_PROGRESS | **Requirement discrepancy (documented, not blocking):** the packet says the cutover day "may hold up to 31 hours". For UTC→Jakarta, rollover moves 7 hours *earlier*, so one legacy day shrinks to 17–24 hours and no day exceeds 24 hours. 31 hours happens only when rolling back from Jakarta to UTC-keyed code. `docs/Database_Operations.md` states the correct numbers, quotes the packet wording, and recommends a 07:00–23:00 WIB deploy window. |
| 2026-11-21 | senior-dev | IN_PROGRESS | KQ-001 tests whose expectations changed, and why: (1) `test_legacy_day_follows_the_process_timezone` → `test_app_day_ignores_the_process_timezone`: the day no longer depends on process `TZ`; it equals the Jakarta date under both Pacific/Kiritimati and Pacific/Pago_Pago. (2) `test_in_a_utc_container_the_legacy_day_rolls_over_at_0700_jakarta` → `test_day_rolls_over_at_midnight_jakarta`: 00:00 and 06:59 WIB now map to 2026-11-22 (were 2026-11-21). (3) `test_in_a_jakarta_container_the_legacy_day_rolls_over_at_midnight` removed: there is no container-timezone concept any more; `tests/unit/test_clock.py` covers configured zones. (4) `test_question_served_before_rollover_is_rejected_after_it`: boundary moved from 06:58→07:00 WIB to 23:58→00:00 WIB; same 400 out-of-sync outcome. (5) `test_root_creates_a_session_cookie_and_redirects_to_start`: cookie now has `Max-Age=31536000` and `Path=/` (was asserted absent); still no `Secure` locally. (6) `test_api_stats_reports_today_and_a_seven_day_recap`: `generated_at` is `2026-11-21T10:00:00` Jakarta wall time (was `03:00:00` UTC). Support changes: `FrozenClock` now subclasses `app.clock.Clock` and installs by replacing `app.clock._clock` (no module patching); `conftest.py` also clears `APP_TIMEZONE`, `SESSION_COOKIE_*`, `SQLITE_BUSY_TIMEOUT_MS`, and `RAILWAY_ENVIRONMENT*` before import. |
| 2026-11-21 | senior-dev | IN_PROGRESS | New tests: `tests/unit/test_clock.py` (14: Jakarta default, midnight rollover, configured zone, invalid zone, env var via subprocess, static scan for direct `date.today`/`datetime.now`/`utcnow`/`time.localtime` in `app/` and `scripts/`), `tests/unit/test_config.py` (27: flag/int parsing, production markers, secret check matrix, `SESSION_COOKIE_SECURE` defaults via subprocess), `tests/integration/test_database_safety.py` (15: pragmas, traced pragmas on every connection of a full quiz flow, factory-only connections, migrations with FK on, commit, rollback on exception/failing statement/FK violation, immediate vs deferred locking, 10 parallel read-modify-write writers with no lost update, second writer waits, busy timeout honored), `tests/integration/test_session_cookie.py` (12: all 4 reachable call sites local and Secure modes, max age, no re-issue, local HTTP flow, no inline writers), `tests/integration/test_production_startup.py` (6: `create_app` refusal before touching the DB, success with secret, uvicorn import message, Dockerfile seed step without secret, real `docker-entrypoint.sh` migrates without secret then refuses app start, and starts with secret), `tests/integration/test_backup_restore.py` (10: exact restore via scripts, default path, temp restore, missing source, no overwrite, corrupted backup, non-app DB, changed DB, backup during an open write transaction). `tests/integration/test_database_safety.py` ran 3× → stable. |
| 2026-11-21 | senior-dev | IN_REVIEW | Verification: `rtk .venv/bin/python -m pytest -q` twice → `188 passed, 1 xfailed` both (~18.6 s; xfail is the KQ-003 race). 15 warnings, all the same two pre-existing deprecations (Starlette `TemplateResponse` argument order, anyio alias). No `math_app.sqlite3` in the repo root. Clean-checkout simulation (fresh 3.12.7 venv, `pip install -r requirements-dev.txt`, tzdata 2026.6 installed from runtime requirements) → `188 passed, 1 xfailed` twice. Production start: `RAILWAY_ENVIRONMENT=production ADMIN_CLEAR_PASSWORD=masukaja python -m uvicorn app.main:app` → `app.config.ConfigError: ADMIN_CLEAR_PASSWORD is unset or still the legacy default. …`; with it unset → exit 1, and no database file created. With `ADMIN_CLEAR_PASSWORD=strong-secret` → `/health 200 {"ok":true}`, cookie `HttpOnly; Max-Age=31536000; Path=/; SameSite=lax; Secure`, `day` = Jakarta date. Backup exercise on a disposable populated DB: `DB_PATH=live/kids-quiz.sqlite3 python scripts/backup_db.py` → `Backup written: live/backups/kids-quiz-20261121-185124.sqlite3`, `integrity_check: ok`, `schema version: 7`, rows `child_daily=2, daily_question_banks=4, schema_migrations=7, served_questions=6, session_current_questions=0, sessions=2` (exit 0); `python scripts/verify_backup.py <backup> --restore-to restored/kids-quiz.sqlite3 --compare-with live/kids-quiz.sqlite3` → `Backup verified`, `restore test: ok`, `matches`, digest `f03235ec…45acf` (exit 0); restored copy `PRAGMA integrity_check` → `ok`; re-running the backup to the same output → `Refusing to overwrite` (exit 1). |
| 2026-11-21 | lead | DONE | Lead review passed. Re-ran suite: 188 passed, 1 xfailed. Verified `app/clock.py` is the only time source (no `date.today`/`datetime.now` left in `app/`), `db_conn` pragmas, `transaction()` BEGIN IMMEDIATE/commit/rollback, single `set_session_cookie` helper, startup-only admin-secret check (migrate/Docker seed unaffected), entrypoint change is path-overridable only. Decisions: (a) 31-hour statement was wrong for UTC→Jakarta; packet and plan corrected to 17–24 h, the developer's ops doc is right. (b) 365-day cookie max age accepted (keeps profile selection sticky; configurable). (c) Production detection via `RAILWAY_ENVIRONMENT*` accepted; runbook's explicit `SESSION_COOKIE_SECURE`/`ADMIN_CLEAR_PASSWORD` step is the safeguard. |

## Completion handoff

- **Summary:** Day boundaries now come from one injectable `app/clock.py` in `APP_TIMEZONE` (default Asia/Jakarta, `tzdata` in runtime requirements). Every SQLite connection gets foreign keys and an explicit busy timeout. A `BEGIN IMMEDIATE` unit-of-work helper is ready for KQ-003. One session-cookie helper adds explicit `Path`/`Max-Age` and `Secure` when `SESSION_COOKIE_SECURE` is on (production default). Production startup refuses an unset or default admin password, without affecting the Docker build or entrypoint migrations. Backup and verify/restore scripts are added, and the cutover, runbook, and retention are documented. WAL is deferred.
- **Files changed:** `app/clock.py` (new), `app/config.py`, `app/db/sqlite.py`, `app/db/backup.py` (new), `app/main.py`, `app/api/routes.py`, `app/services/session_service.py`, `app/services/question_service.py`, `app/services/stats_service.py`, `scripts/backup_db.py` (new), `scripts/verify_backup.py` (new), `docker-entrypoint.sh`, `requirements.txt`, `requirements-dev.txt`, `docs/Database_Operations.md` (new), `Readme.md`, `tests/conftest.py`, `tests/support.py`, `tests/integration/test_known_legacy_behaviors.py`, `tests/integration/test_legacy_routes.py`, new `tests/unit/test_clock.py`, `tests/unit/test_config.py`, `tests/integration/test_database_safety.py`, `tests/integration/test_session_cookie.py`, `tests/integration/test_production_startup.py`, `tests/integration/test_backup_restore.py`; this packet and the tracker row.
- **Migrations/data impact:** No schema change and no migration. Configuration only. Existing `child_daily` rows stay UTC-day keyed. The cutover day is 17–24 hours long (see `docs/Database_Operations.md`), and `created_at`/`generated_at` become Jakarta wall time in the same format.
- **Verification performed:** See the IN_REVIEW execution-log entry: full suite twice (188 passed, 1 xfailed), clean checkout twice, production refusal with default/unset password, secure cookie with a real secret, backup → verify → restore on a disposable database with exact digest match.
- **Commit:** pending lead commit
- **Follow-ups:** (1) Operator: confirm a `RAILWAY_ENVIRONMENT*` variable is present in the deployed container and set `SESSION_COOKIE_SECURE=true` and a strong `ADMIN_CLEAR_PASSWORD` before deploying. If no marker is present, both production protections stay off. (2) Operator: fill the cutover log in `docs/Database_Operations.md` at deploy time (deploy 07:00–23:00 WIB). (3) KQ-003: adopt `transaction()` and add connection-accepting `Repo` variants; remove the xfail. (4) Lead: confirm the 365-day cookie max age and the correction to the packet's "31 hours" statement. (5) WAL remains deferred until backup/restore is proven with WAL files on the Railway volume.
