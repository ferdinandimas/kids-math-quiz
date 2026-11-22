---
id: KQ-003
title: Make the legacy answer flow atomic
status: DONE
owner: senior-dev
depends_on: [KQ-001, KQ-002]
milestone: M2
updated: 2026-11-21
---

# KQ-003 — Make the legacy answer flow atomic

## Outcome

Submitting one legacy quiz answer updates counters exactly once under duplicate and concurrent requests, with no change to the `/api/answer` contract.

## Source references

- [Implementation plan §6 M2](../KidQuest_Implementation_Plan.md)
- [PRD §4.1 mutation safety, §3.4 rewards and limits, §3.5 compatibility surface](../KidQuest_Build_Your_World_PRD_v1.4.md)

## Current flow (to be replaced)

`POST /api/answer` in `app/api/routes.py` currently does these steps through separate `Repo` calls, each opening its own connection and committing:

1. Read the active question (`session_current_questions`) and compare it with `qid`.
2. Evaluate the answer. `evaluate_answer` → `get_daily_bank` → `cleanup_expired_question_data` also runs DELETEs.
3. Read today's `child_daily.answered_count` and check `answered + quota_cost <= DAILY_LIMIT`.
4. `inc_answered` → `upsert_daily`, `inc_session_answered`, `inc_daily_answered` (three commits).
5. If correct, `mark_correct` → `upsert_daily`, `inc_session_correct_earned`, `inc_daily_correct_earned` (three commits).
6. `set_current_qid(None)` clears `session_current_questions` and the legacy `sessions` columns.

Two concurrent requests can both pass steps 1 and 3 before step 6, so both count.

## Scope

1. Take `cleanup_expired_question_data` out of the evaluation path (run it on question issuance or at startup) so evaluation is read-only.
2. Evaluate the answer against the persisted daily bank before opening the write transaction.
3. Using the KQ-002 unit-of-work helper (`BEGIN IMMEDIATE`, one shared connection), do in one transaction:
   - re-check that the active question for (session, child, quiz type) still equals `qid`;
   - check quota against `child_daily.answered_count` plus quota cost (1 Math, 2 General Knowledge);
   - upsert `child_daily` and increment session and daily answered counts by the quota cost;
   - when correct, increment correct count and earned by the question reward (Rp50 Math, Rp100 General Knowledge);
   - clear the active question in `session_current_questions` and the legacy `sessions` columns.
4. Add connection-accepting variants of the `Repo` methods involved; leave the existing method signatures working for other callers.
5. Keep the request body (`qid`, `answer`, `quiz_type`) and the success response (`ok`, `correct`, `correct_answer`) identical. Do not add an idempotency key, header, migration, or stored response; `static/js/quiz.js` sends none.
6. The losing duplicate request returns the existing synchronization error: HTTP 400, `{"ok": false, "message": "Soal tidak sinkron. Klik Next lagi."}`.
7. A quota failure detected inside the transaction returns the existing HTTP 409 message and changes nothing.
8. Add sequential-duplicate, concurrent-duplicate, quota, and rollback tests.

## Deliverables

- Transactional answer path in the repository/service layer and the updated `api_answer` route.
- Regression tests for duplicates, concurrency, quota, and rollback.

## Acceptance criteria

- [x] Answered, correct, and earned counters (session and `child_daily`) and the active-question clear commit or roll back together.
- [x] Submitting the same `qid` twice in sequence counts once; the second request gets the 400 synchronization error.
- [x] Two concurrent submissions of the same `qid` count once; the loser gets the 400 synchronization error.
- [x] General Knowledge consumes exactly two quota units once; a submission that would exceed `DAILY_LIMIT` returns 409 and changes nothing.
- [x] An injected failure after the first counter update leaves every counter and the active question unchanged.
- [x] `/api/answer` request and success-response shapes are unchanged, and no new table or migration is added.
- [x] KQ-001 and KQ-002 tests remain green.

## Verification

- Run the full suite plus the concurrent duplicate-submission test at least 50 times.
- On a disposable database, compare `sessions` and `child_daily` counters and `session_current_questions` before and after a duplicate burst; there is no per-answer table to inspect.

## Out of scope

- Idempotency keys and response replay for the legacy endpoint (KidQuest endpoints get these in KQ-008/KQ-009).
- Making question issuance (`/api/question` reserve + `inc_served`) atomic.
- KidQuest challenge generation and the wallet economy.

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Task packet created. |
| 2026-11-21 | planning | NOT_STARTED | Aligned with plan M2: no idempotency key or migration; losing duplicate returns the existing 400 sync error; quota and GK cost moved inside the transaction; removed nonexistent streak reference. |
| 2026-11-21 | senior-dev | IN_PROGRESS | Claimed after lead approval of KQ-002 (DONE); dependencies KQ-001 and KQ-002 are DONE. Lead review points recorded: remove the strict xfail and run the concurrent test 50+ times; keep the barrier race and add a real-route two-thread same-cookie test; exact 400/409 contract and KQ-001 characterizations preserved (stop and ask before changing any); all writes in one `transaction()` with quota re-read inside; fault-injection test after the first counter update; cleanup stays on issuance, not evaluation; connection-accepting `Repo` variants that the old methods delegate to; no migration, table, idempotency key, or frontend change. |
| 2026-11-21 | senior-dev | IN_PROGRESS | Repo: added connection-accepting variants `get_profile_current_qid_in`, `set_current_qid_in`, `upsert_daily_in`, `get_daily_answered_in` (new read), `inc_session_answered_in`, `inc_daily_answered_in`, `inc_session_correct_earned_in`, `inc_daily_correct_earned_in`. Each takes `conn` first and never commits. The existing methods keep their exact signatures and now delegate through `Repo._connection()` (open → delegate → commit → close), so the SQL exists once. Callers (`session_service`, `stats_service.inc_served`/`inc_answered`/`mark_correct`) are untouched. |
| 2026-11-21 | senior-dev | IN_PROGRESS | Service: `StatsService.record_answer(...) -> AnswerOutcome` runs in one `transaction()` (`BEGIN IMMEDIATE`, one connection): re-reads the active question for (session, child, quiz type) and returns `OUT_OF_SYNC` if it is not `qid`; re-reads `child_daily.answered_count` and returns `OVER_QUOTA` if answered + cost > `DAILY_LIMIT` (the check happens before `upsert_daily`, so a rejection inserts nothing, as before); upserts `child_daily`; increments session and daily answered by the quota cost (1 Math, 2 GK); when correct, increments correct and earned by the question reward (Rp50/Rp100); clears both active-question stores via `set_current_qid_in`. `inc_answered`/`mark_correct` are kept but no longer called by the route. |
| 2026-11-21 | senior-dev | IN_PROGRESS | Evaluation: `QuestionService.evaluate_answer` is read-only. It reads the persisted bank via `repo.get_daily_question_bank` and, if missing, regenerates the same deterministic bank in memory (no insert). It no longer calls `get_daily_bank`, so `cleanup_expired_question_data` runs only on issuance (`get_question_payload`, `get_existing_question_payload`). New optional `day` argument: the route computes `today` once and uses it for both evaluation and the transaction (before, evaluation and the quota check each read the clock). Side-effect difference (not characterized, response identical): when the bank row is missing, evaluation no longer re-inserts it; the next issuance does. |
| 2026-11-21 | senior-dev | IN_PROGRESS | Route: `api_answer` keeps its pre-checks in the same order (profile → quiz type → active-question pre-check → evaluation → "Soal tidak ditemukan."), then calls `record_answer` and maps `OUT_OF_SYNC` → HTTP 400 `{"ok": false, "message": "Soal tidak sinkron. Klik Next lagi."}` and `OVER_QUOTA` → HTTP 409 `{"ok": false, "message": "Sisa kuota hari ini tidak cukup untuk soal ini."}`. The body (`qid`, `answer`, `quiz_type`) and success `{ok, correct, correct_answer}` are unchanged. No migration, table, idempotency key, header, or frontend change (`git diff -- static app/db/migrations.py` is empty). No KQ-001 characterized behavior changed: "quota-rejected answer leaves the question active" and "next issuance deletes the prior day's bank" still pass unmodified. |
| 2026-11-21 | senior-dev | IN_PROGRESS | Tests: removed the strict xfail from `test_concurrent_duplicate_answer_counts_once` (it went XPASS(strict) as soon as the fix landed) and tightened it to assert the exact winner shape, the exact loser 400 body, session counters, and the cleared active question. New `tests/integration/test_atomic_answer.py` (21): 15-round two-thread same-cookie real-route race; 8-request GK burst (2 units once); cross-session quota race at 398 (one 200, one exact 409, answered=400); 409 and 400 rejections change no row (full snapshot of `sessions`, `child_daily`, `session_current_questions`); incorrect answer counts once and clears both stores; fault injection after `inc_daily_answered_in` (right after the first counter update), `inc_daily_correct_earned_in`, and `set_current_qid_in` → HTTP 500, snapshot identical, retry counts once; all eight `_in` steps share one connection and run with `in_transaction` true (quota re-read included); evaluation issues only SELECTs; answering keeps old-day rows while the next issuance cleans them; missing bank is evaluated in memory without re-insert; plain repo methods delegate to the variants and still commit on their own. |
| 2026-11-21 | senior-dev | IN_REVIEW | Verification: (1) 50 separate pytest runs of the four concurrency tests (`test_concurrent_duplicate_answer_counts_once`, two-thread real-route race ×15 rounds, 8-request burst, quota race) → **50 passed, 0 failed**, i.e. 50 barrier races, 750 real-route duplicate pairs, 50 bursts, and 50 quota races. (2) `rtk .venv/bin/python -m pytest -q` twice → `210 passed` both (~20 s, 0 xfail; 15 warnings, the same two pre-existing deprecations). No `math_app.sqlite3` in the repo root. (3) Disposable DB + real `uvicorn` on port 8768, althafandra: burst of 10 concurrent duplicate HTTP submissions per quiz type with the same cookie. Math `v2_q0390`: statuses `[200, 400×9]`, losers all exactly the sync error; `child_daily` answered/correct/earned 0/0/0 → 1/1/50; session 0/0/0 → 1/1/50; `current_qid`/`current_math_qid` cleared; `session_current_questions` 1 row → 0. Knowledge `knowledge_pemula_024`: `[200, 400×9]`; `child_daily` 1/1/50 → 3/2/150 (two units, Rp100 once); session the same; `current_knowledge_qid` cleared; active rows 1 → 0. |
| 2026-11-21 | lead | DONE | Lead review passed. Re-ran suite: 210 passed (xfail removed). `test_atomic_answer.py` 3× consecutive: 21 passed each. Verified `StatsService.record_answer`: one `transaction()` (BEGIN IMMEDIATE) re-checks active qid and quota before any write, updates session + `child_daily` counters by quota cost, clears both active-question stores; route keeps exact 400 sync / 409 quota bodies; `evaluate_answer` read-only; no migration/static change. Follow-up accepted: remove now-unused `StatsService.inc_answered`/`mark_correct`; make question issuance transactional later. |

## Completion handoff

- **Summary:** `/api/answer` now consumes the active question and updates every counter in one `BEGIN IMMEDIATE` transaction (`StatsService.record_answer`). The active question and quota are re-read inside it, both active-question stores are cleared in it, and evaluation is read-only. Duplicate and concurrent submissions count once; the loser gets the existing 400 sync error; quota overflow gets the existing 409 and writes nothing. The request and response contract is unchanged.
- **Files changed:** `app/db/repo.py` (connection-accepting `_in` variants; existing methods delegate), `app/services/stats_service.py` (`AnswerOutcome`, `record_answer`), `app/services/question_service.py` (read-only `evaluate_answer` with optional `day`), `app/api/routes.py` (`api_answer` uses `record_answer`), `tests/integration/test_known_legacy_behaviors.py` (xfail removed, assertions tightened), `tests/integration/test_atomic_answer.py` (new); this packet and the tracker row.
- **Migrations/data impact:** None. No schema change, table, or migration.
- **Verification performed:** See the IN_REVIEW execution-log entry: four concurrency tests 50/50 runs, full suite twice (210 passed), and a disposable-DB duplicate burst against a real uvicorn server with before/after counters.
- **Commit:** pending lead commit
- **Follow-ups:** (1) Question issuance (`reserve_question` + `inc_served` + `set_current_qid`) is still multi-commit; it is out of scope here and can adopt `transaction()` later. (2) `StatsService.inc_answered`/`mark_correct` no longer have callers; they could be removed in a cleanup task. (3) KQ-007/KQ-008 should build KidQuest mutations on `transaction()` and the `_in` repository pattern.
