---
id: KQ-011
title: Add adult gate and pilot hardening
status: IN_PROGRESS
owner: codex-core
depends_on: [KQ-010]
milestone: M6
updated: 2026-11-22
---

# KQ-011 — Add adult gate and pilot hardening

## Outcome

The first playable slice is safe, observable, recoverable, and ready for a controlled family pilot, and it passes the first-deliverable acceptance scope defined in PRD §23.

## Source references

- [Implementation plan §10 M6, §14 admin clear, §15 rollout and rollback](../KidQuest_Implementation_Plan.md)
- [PRD §4.4 adult authorization, AC-09, §15 configuration, §23 first-deliverable acceptance scope](../KidQuest_Build_Your_World_PRD_v1.4.md)

## Current-code facts this task must handle

- `/api/stats` returns both children's seven-day recap to any session (`app/api/routes.py`, `api_stats`). Per PRD AC-09's pilot-scope note, it stays unchanged; do not alter its response fields.
- `/api/admin/clear` (`app/services/admin_service.py`, `Repo.clear_database`) deletes all sessions, statistics, served questions, daily banks, and active questions for **both** children, then runs `VACUUM`. The stats page calls it with only a password.
- The legacy password comes from `ADMIN_CLEAR_PASSWORD`; KQ-002 makes production refuse the `masukaja` default.

## Scope

1. Implement the adult gate: PBKDF2 verification against `PARENT_PIN_HASH`, an HMAC-signed (`SESSION_SIGNING_KEY`), `HttpOnly`, `SameSite=Strict`, `Secure`-in-production, short-lived adult session cookie.
2. Protect all new KidQuest parent reporting, parent settings, and scoped resets with the adult session.
3. Keep `/api/admin/clear` working with its existing request/response contract and legacy-only scope. It must never delete `kidquest_*` tables. Add a test proving KidQuest data survives a legacy clear.
4. Add an adult-gated per-child scoped reset with three scopes (legacy learning history only, KidQuest world/progress only, all child data). Each scope needs a separate confirmation value and an audit event.
5. Add privacy-conscious structured logs (operation, request ID, content version, result, latency, error code) that exclude raw answers, secrets, and unnecessary child PII.
6. Rehearse backup → migration → allowlisted-profile smoke → `KIDQUEST_ENABLED=false` rollback on a copy of production data.
7. Run browser (current mobile Safari/Chrome-class), accessibility, performance, and three-theme screenshot checks at phone, tablet, and desktop widths.
8. Produce the pilot deployment runbook (`docs/KidQuest_Deployment_Runbook.md`) and rollback checklist.

## Deliverables

- Adult-gate session plus protected parent/reset endpoints and UI.
- Scoped reset with audit events; legacy-clear compatibility test.
- Audit/logging safeguards.
- First-deliverable acceptance report mapped to the PRD §23 scope table, the deployment runbook, and the rollback checklist.

## Acceptance criteria

- [x] Child-accessible routes cannot invoke KidQuest parent reporting, parent settings, or scoped resets without a valid adult session.
- [x] Adult authorization expires and a tampered or expired cookie is rejected.
- [x] A scoped reset affects only the selected child and scope, needs that scope's confirmation value, and writes an audit event.
- [x] `/api/admin/clear` keeps its contract, clears only legacy tables, and leaves every `kidquest_*` row intact.
- [x] `/api/stats` response fields are unchanged (legacy compatibility).
- [ ] Backup/restore and forward/rollback rehearsals succeed on production-like data copies, and `KIDQUEST_ENABLED=false` restores legacy-only behavior without data loss.
- [ ] First-deliverable acceptance passes as scoped in PRD §23:
  - [ ] AC-01 – AC-13 in full (AC-09 with its pilot-scope note).
  - [ ] AC-14 first-house scope: the release manifest has every first-house asset (golden terrain with the shore masks `pulau_tunas_v1` uses, `quest_board`, 16 road masks, six buildings, `wood` icon, theme thumbnail, shared overlays) in all three themes, and CI fails on a missing or geometry-incompatible asset.
  - [ ] AC-15 first-house scope: all 16 road masks render and join in a 3×3 gallery scene per theme; adjacency-to-mask resolution is unit-tested; theme switching leaves stored path rows unchanged.
  - [ ] AC-16 in full: six building silhouettes verified in the gallery at 38/48/64 px; in-world states verified for the starter house, quest board, and placement overlays; no horizontal overflow at 360 px; nothing requires animation under reduced motion.
  - [ ] AC-22, AC-23, AC-25 for first-house screens and tasks.
- [ ] Each AC above links to recorded evidence, or to an approved waiver with approver and date.

## Verification

- Run security, isolation, regression, accessibility, browser, and performance checks.
- Execute the runbook on a disposable production-like environment and record results.
- Fill in the PRD §23 scope table with pass/waiver evidence per criterion.

## Out of scope

- Payment integration, economy expansion, and adaptive learning.
- Wrong-PIN throttling or lockout: not required for the household pilot (product owner decision, 2026-11-21). Revisit in the public-launch authentication review (PRD §4.4).
- Road placement/removal, segment limit, entrance connectivity, and bridge connectivity (AC-15 remainder → KQ-019, KQ-021).
- Full 168-asset inventory: props, fences, plant variations, `stone` icon, and the complete shore set (AC-14 remainder → KQ-023).
- Gating the legacy cross-child recap (open decision, PRD §22).

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Task packet created. |
| 2026-11-21 | planning | NOT_STARTED | Scoped acceptance to PRD §23 first-deliverable table (AC-14/15 subset); defined legacy clear/stats compatibility and per-child scoped reset. |
| 2026-11-22 | lead | NOT_STARTED | **Approved split and start-before-dependency exception:** the backend slice of KQ-011 (scope items 1–3 and 5: adult gate session, adult-only reporting/settings/scoped reset, legacy-clear compatibility, structured logs, the backend part of the runbook) may start before KQ-010 is `DONE`, because it touches no frontend file. Assigned to Codex (`codex-core`). Scope items 4 and 6–7 of the packet (browser/accessibility/performance/screenshot checks, the adult-area UI, and the first-deliverable AC evidence table) stay open until KQ-010 is `DONE`. Consequence: KQ-011 may reach at most `IN_REVIEW` for the backend slice and stays `IN_PROGRESS` overall until the remaining items are done. Lead verifies the backend slice independently before any status is accepted. |
| 2026-11-22 | codex-core | IN_PROGRESS | Claimed the approved backend slice; preserving KQ-010/KQ-006 frontend and asset areas. Baseline, implementation, regression, security, isolation, logging, migration, and runbook evidence to follow. |
| 2026-11-22 | codex-core | IN_REVIEW | **Backend slice IN_REVIEW.** Added PBKDF2 adult gate, durable signed-session logout, read-only Ringkasan, atomic audited/idempotent per-child reset, Migration 9, KidQuest-only redacted JSON logs, legacy-clear/stats/byte compatibility coverage, and backend deployment runbook. Final full suite: 992 passed, 3 skipped in 72.37s. Overall task and tracker remain IN_PROGRESS for KQ-010-dependent UI/browser/accessibility/performance/screenshot and first-deliverable evidence work; commit pending lead commit. |
| 2026-11-22 | lead | IN_PROGRESS | **Backend slice accepted by lead.** Independently verified: read `adult_session.py`, `parent_auth_service.py`, adult service/routes, reset repo methods, Migration 9, logging middleware, PIN-hash script (PIN never from argv). Re-ran full suite (992 passed, 3 skipped), adult gate/reset/gating/migration suites (115 passed), reset concurrency 3 x 50 runs (all passed). Confirmed: constant-time signature and PIN compare, expiry via the Jakarta clock, durable logout revocation, per-child/per-scope deletes inside one transaction with audit row, audit and revocation tables never touched by resets, legacy routes unchanged, logs carry only operation/request id/content version/result/latency/error code. Overall KQ-011 stays `IN_PROGRESS` (items 4 UI and 6-7 plus the PRD §23 evidence table wait for KQ-010 `DONE`). Lead snapshot commit pending. |

## Completion handoff

- **Summary:** Backend slice IN_REVIEW. Adult routes are registered only with KidQuest + dashboard flags and valid secrets; adult session, overview, scoped reset, audit, logging, compatibility, and backend runbook are complete. KQ-011 remains IN_PROGRESS overall.
- **Files changed:** Added `app/security/adult_session.py`, adult auth/reset services and routes, KidQuest logging middleware, PIN hash script, backend runbook, and adult security/reset tests. Updated config/startup wiring, KidQuest repo, migrations, database/implementation docs, migration expectations, and legacy compatibility tests. No KQ-010/KQ-006 frontend, browser, design, content, or asset file was changed.
- **Migrations/data impact:** Migration 9 additively creates append-only-by-policy `kidquest_audit_events` and durable `kidquest_adult_session_revocations`; no legacy table changes. Reset confirmation values: `HAPUS-KUIS`, `HAPUS-DUNIA`, `HAPUS-SEMUA`. Audit-backed reset replay stores only a digest of the idempotency key and survives deletion of ordinary child KidQuest idempotency rows.
- **Verification performed:** Baseline full suite `902 passed, 3 skipped`; reset concurrency `50 passed, 7 deselected`; focused final security/regression suite `178 passed`; affected legacy/migration suite `78 passed`; sandbox-authorized browser check `1 passed`; final full suite `992 passed, 3 skipped` in 72.37s. Failure injection proved reset+audit rollback; tests cover PIN/hash script, token tamper/expiry/wrong key/truncation/logout restart replay, cookie attributes, every protected route, disabled/missing-secret 404, scope snapshots for both children and every table, replay/conflict, audit content, legacy clear/stats/response bytes, redacted one-line logs, and Migration 9 empty/v8/re-run/FK cases.
- **Commit:** pending lead commit
- **Follow-ups:** Lead independent review. After KQ-010 is DONE, complete the adult-area UI plus production-like runbook rehearsal, current-browser/accessibility/performance/three-theme screenshot matrix, and PRD §23 evidence table; only then may overall KQ-011 advance beyond IN_PROGRESS.
