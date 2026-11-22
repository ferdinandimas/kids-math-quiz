# KidQuest Adult-Gate Deployment Runbook

Backend runbook for the controlled household pilot. The safe order is **backup → verify → migrate
→ deploy disabled → smoke → allowlist → enable adult gate → rollback if needed**. Run during
household downtime, preferably 07:00–23:00 WIB.

## Required variables

Keep `KIDQUEST_ENABLED=false`, `KIDQUEST_PARENT_DASHBOARD_ENABLED=false`, and an empty
`KIDQUEST_PROFILE_ALLOWLIST` for the first deploy. Set the existing production requirements
(`ADMIN_CLEAR_PASSWORD`, `APP_TIMEZONE=Asia/Jakarta`, `SESSION_COOKIE_SECURE=true`, `DB_PATH`) plus:

| Variable | Pilot value / rule |
| --- | --- |
| `PARENT_PIN_HASH` | Generate locally with `PYTHONPATH=. .venv/bin/python scripts/hash_parent_pin.py`; enter the PIN at the hidden prompt or pipe it on stdin. The script never accepts a PIN argument. Copy only the resulting self-describing PBKDF2 hash. |
| `SESSION_SIGNING_KEY` | Independent random secret of at least 32 bytes. Never use the PIN or PIN hash. |
| `KIDQUEST_ADULT_SESSION_MAX_AGE` | `900` unless the product owner approves another short positive lifetime. |
| `KIDQUEST_PARENT_DASHBOARD_ENABLED` | `false` until backend smoke passes; then `true`. Production startup refuses an enabled dashboard with missing/malformed/weak secrets. |
| `KIDQUEST_ENABLED` | `false` for deploy and rollback; enable only after legacy smoke. |
| `KIDQUEST_PROFILE_ALLOWLIST` | Start empty, then one stable child ID, then both only after each smoke passes. |

Do not paste the plaintext PIN into Railway logs, shell history, tickets, or chat. Rotate
`SESSION_SIGNING_KEY` to invalidate every adult cookie immediately; changing the PIN hash affects
new logins but does not invalidate an already signed cookie before its short expiry.

## Deploy sequence

1. **Backup.** Run `python /app/scripts/backup_db.py` in the service and record its path, size,
   schema version, integrity result, and row counts.
2. **Verify and rehearse.** Run `python /app/scripts/verify_backup.py <backup>`. Restore to a new
   disposable file, point `DB_PATH` at it, and run `PYTHONPATH=. python scripts/migrate.py`. Require
   `integrity_check: ok`, an empty `foreign_key_check`, schema version 9, and a second migration run
   reporting that the schema is current.
3. **Deploy flags off.** Deploy reviewed code with KidQuest and the parent dashboard disabled.
   Require `/health`, `/home`, Math, Knowledge, answer submission, `/stats`, and `/api/stats` to
   match the pre-deploy behavior.
4. **Smoke KidQuest.** Set `KIDQUEST_ENABLED=true` with an empty allowlist. Confirm legacy traffic,
   then allowlist one child. Complete state load, Q001 start/challenge/retry/reward/build, refresh,
   theme change, and restart persistence. Verify the other child remains blocked and unchanged.
5. **Smoke the adult gate.** With valid secrets present, set
   `KIDQUEST_PARENT_DASHBOARD_ENABLED=true`. Confirm a wrong PIN is generic, a child `math_sess`
   alone gets `ADULT_AUTH_REQUIRED`, the right PIN sets a `Secure; HttpOnly; SameSite=Strict;
   Path=/` cookie with the configured max age, Ringkasan shows only stable configured child IDs and
   the prototype fields, logout rejects a copied cookie, and expiry asks for the PIN again.
6. **Reset rehearsal on the disposable restore.** For each scope and each child, snapshot every
   legacy/KidQuest table, perform the documented confirmation, and prove only that child/scope
   changed. Replay the same request key and require identical bytes and one audit event. Confirm
   `GET /api/kidquest/state` recreates Q001 after a KidQuest reset. Never rehearse destructive
   reset against the live household database without the product owner's explicit choice.
7. **Expand allowlist.** Add the second child only after the first child's smoke and isolation
   checks pass. Preserve the backup and evidence record.

## Logs and audit review

Every `/api/kidquest/*` request emits one JSON line containing only `operation`, `request_id`,
`content_version`, `result`, `latency_ms`, and `error_code`. `X-Request-ID` is returned only for this
API prefix. Logs never include raw answers, PINs, hashes, cookies, idempotency keys, or display
names. Investigate repeated `ADULT_AUTH_REQUIRED`, `IDEMPOTENCY_CONFLICT`, reset failures, or 5xx
results by request ID without asking for secrets.

Review reset evidence read-only in `kidquest_audit_events`: stable child ID, scope, time, result,
and deletion counts. The key column is a digest, not the submitted key. The audit table is retained
by every reset and `/api/admin/clear`; do not update or delete its rows during normal operations.

## Rollback

1. Set `KIDQUEST_PARENT_DASHBOARD_ENABLED=false`, then `KIDQUEST_ENABLED=false`. This removes the
   adult and KidQuest routes while retaining worlds, progress, audit, and revocation data.
2. Re-run `/health`, both legacy quiz types, answer submission, `/stats`, and `/api/stats`.
3. Roll back application code only if necessary. Migration 9 is additive, so older code ignores its
   tables. Preserve the database and logs for diagnosis.
4. Restore the verified backup only for confirmed data corruption. A restore loses all writes since
   the backup: restore to a new path, verify it, stop writes, swap paths, restart, and repeat smoke.

## Still blocked on KQ-010

This backend runbook does **not** complete the adult-area UI or the required browser/accessibility/
performance evidence. After KQ-010 is `DONE`, run current mobile Safari and Chrome-class checks,
keyboard and screen-reader checks, 200% zoom, reduced motion, phone/tablet/desktop widths, network
throttling, and the three-theme screenshot matrix before KQ-011 can move from overall
`IN_PROGRESS` to final review/completion.
