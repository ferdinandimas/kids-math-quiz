# KidQuest Implementation Plan

**PRD:** `docs/KidQuest_Build_Your_World_PRD_v1.4.md`  
**Visual pipeline:** `docs/KidQuest_Visual_Design_Asset_Pipeline.md`  
**Execution tracker:** `docs/KidQuest_Execution_Tasks.md`  
**Plan date:** 2026-11-21  
**Target:** Safe first-house vertical slice, followed by incremental MVP expansion  
**Current branch baseline:** FastAPI + Jinja/vanilla JS + SQLite + Railway

## 1. Outcome

The first implementation release will let either existing child:

1. Open an independent 8×8 Pulau Tunas world.
2. Start or resume Q001.
3. Submit the contextual subtraction challenge explicitly.
4. Receive hints and retry after mistakes.
5. Earn four wood and one starter-house blueprint exactly once.
6. Place a 2×2 house in the configured tutorial zone.
7. Refresh or restart and see the same completed state.
8. Preview and persist Kampung, Kingdom, or City without changing any logical progress.

Legacy Math, General Knowledge, statistics, rewards, and routes remain available. KidQuest is off by
default and enabled only for configured profiles during rollout.

## 2. Delivery rules

- Do not rewrite the frontend or introduce a game engine for the first slice.
- Do not repurpose or destructively alter existing tables.
- Every milestone is independently reviewable and testable.
- Database correctness precedes visual polish.
- All new mutation APIs are idempotent and transactional.
- A multi-statement mutation runs on one shared SQLite connection inside one explicit transaction.
  The current `Repo` opens and commits a new connection in every method, so transactional work must
  use the M1 unit-of-work helper rather than chaining existing `Repo` calls.
- Active child comes from the server session, never from request authority.
- Content definitions are data, validated at startup and in tests.
- New features remain behind flags until their milestone exit gate passes.
- Production building artwork uses a fixed shared sprite-map contract followed by one generation
  task per theme. Each theme task produces all six buildings together in one sprite-map image, in
  the same slot order and at the same slot resolution, so every building in every theme slices and
  anchors identically; a separate extraction/QA task validates per-building geometry across all
  three themes. Buildings are never generated as separate per-building tasks.

## 3. Milestone overview

| Milestone | Result | Depends on |
| --- | --- | --- |
| M0 | Test and tooling baseline | None |
| M1 | Time, session, backup, and SQLite safety | M0 |
| M2 | Atomic legacy answer compatibility | M0, M1 |
| M3 | KidQuest schema and validated Q001 content | M1 |
| M3A | UX architecture/prototype, design system, theme validation, and graybox/golden set | M3 logical catalog |
| M4 | Transactional Q001 and theme service/API | M2, M3 |
| M5 | Playable themed world/challenge/build frontend | M3A, M4 |
| M6 | Security, concurrency, accessibility, and deployment verification | M5 |
| M7 | Wallet, XP/blueprint, store, liability, and manual cash-out foundation | M6 |
| M8 | Q002–Q006, roads, supplies, productive buildings, and complete themes | M7 |
| M9 | Parent learning insights and skill adaptation | M6, pilot evidence |

M0–M6 form the first deliverable. Before M5, M3A must complete the golden non-building asset set
(terrain sample, quest board, 16 road masks, shared overlays) and the building sprite-map lane
(KQ-025 → KQ-026/027/028 → KQ-029) must deliver all six buildings in all three themes (18 sprites).
Buildings ship together because each theme's six buildings come from one sprite map. The remaining
non-building inventory (full terrain/shore packs, props, icons) is not required before M5. M7–M9 are separate follow-up projects; no cash-out or productive-building income
ships inside the first-house deliverable.

## 4. M0 — Characterization test foundation

### Objective

Freeze the behavior that must survive the migration and make future refactoring measurable.

### Files to add

- `requirements-dev.txt`
- `tests/conftest.py`
- `tests/unit/test_question_bank.py`
- `tests/unit/test_question_service.py`
- `tests/integration/test_legacy_routes.py`
- `tests/integration/test_legacy_migrations.py`
- `tests/integration/test_profile_isolation.py`

### Files to edit

- `Readme.md`
- `.gitignore` only if test artifacts need exclusions

### Work

1. Add pytest, pytest-asyncio if needed, and HTTPX/TestClient-compatible dependencies to
   `requirements-dev.txt`; keep runtime dependencies separate.
2. Create a temporary SQLite database fixture through `DB_PATH`.
3. Refactor `create_app` only as much as needed to inject a test database/configuration without
   changing route behavior. Current import-time hazards that must be neutralized first:
   - `app/config.py` reads `DB_PATH` at import and `app/db/sqlite.py` binds it with
     `from app.config import DB_PATH`, so changing the environment after import has no effect.
   - `app/main.py` executes `app = create_app()` at import, which runs migrations against
     `math_app.sqlite3` in the working directory. Tests must set `DB_PATH` before any `app.*`
     import, or `db_conn` must resolve the path at call time.
   - `StaticFiles(directory="static")` and `Jinja2Templates(directory="app/web/templates")` are
     working-directory relative; tests run from the repository root or the paths become absolute.
4. Pin the supported Python version. The code uses PEP 604 unions in evaluated signatures (for
   example `repo.py` and `question_service.py`), so it requires Python 3.10+, while `Readme.md`
   claims 3.9+. Docker uses 3.12; document 3.12 as the supported local version.
5. Cover:
   - App creation and current route inventory.
   - Both profile-to-bank assignments.
   - 400 unique questions per Math bank and nonnegative subtraction.
   - Whole-number positive division.
   - 200 General Knowledge questions and four options.
   - Question payload never includes the answer.
   - Refresh returns the active unfinished question.
   - Out-of-sync question is rejected.
   - Current daily statistics and seven-day aggregation.
   - Existing migration versions 1–7 from an empty and representative legacy database.
   - Child daily data isolation.
   - Current day-boundary behavior: `date.today()` follows the container timezone (UTC in the
     default `python:3.12-slim` image unless `TZ` is set), so the legacy day currently rolls over at
     07:00 Asia/Jakarta. Record the deployed container timezone.
   - A question served before rollover and answered after it is rejected as out of sync, because
     `SessionService.get_or_create` resets the session and `cleanup_expired_question_data` deletes
     the prior day's bank.
   - `/api/stats` returns both children's seven-day recap to any session.
   - `/api/admin/clear` deletes all sessions and statistics for both children and runs `VACUUM`;
     the password defaults to `masukaja` when `ADMIN_CLEAR_PASSWORD` is unset.

### Exit gate

- Baseline tests pass without changing intentional legacy response structures.
- Test command is documented.
- A populated legacy fixture can migrate without losing counters.

## 5. M1 — Infrastructure and operational safety

### Objective

Establish deterministic time, secure cookie configuration, backup/restore, and predictable SQLite
behavior before adding player state.

### Files to add

- `app/clock.py`
- `scripts/backup_db.py`
- `scripts/verify_backup.py`
- `docs/Database_Operations.md`
- `tests/unit/test_clock.py`
- `tests/integration/test_backup_restore.py`

### Files to edit

- `app/config.py`
- `app/db/sqlite.py`
- `app/services/session_service.py`
- `app/services/question_service.py`
- `app/services/stats_service.py`
- `app/api/routes.py`
- `docker-entrypoint.sh`
- `Readme.md`

### Work

1. Add explicit `APP_TIMEZONE`, default `Asia/Jakarta`, resolved through `zoneinfo`. Add the
   `tzdata` package to `requirements.txt` so the zone resolves even if the slim image lacks system
   zoneinfo files.
2. Replace direct `date.today()`/`datetime.now()` calls with a small injectable clock. Current call
   sites include `session_service.py`, `question_service.py`, `stats_service.py`, and `routes.py`
   (`quiz_page`, `api_stats`).
3. Document the day-boundary cutover: if production currently runs in UTC, existing `child_daily`
   rows are keyed by UTC day, and switching to Jakarta moves rollover from 07:00 to 00:00 WIB.
   Historical rows are not rewritten; the cutover shortens one legacy day to 17–24 hours (no day
   exceeds 24 hours; a rollback to UTC-keyed code can create a 31-hour day) and is
   recorded in `docs/Database_Operations.md`.
4. Add `SESSION_COOKIE_SECURE`, explicit cookie max age, path, and one cookie helper. The cookie is
   currently set inline in at least five places in `routes.py` and `session_service.py`; all must use
   the helper.
5. Configure every SQLite connection in one factory with:
   - `PRAGMA foreign_keys = ON`.
   - Explicit busy timeout.
   - Row factory.
   - WAL only after volume behavior and backup tests pass.
6. Add a unit-of-work helper (for example a `transaction(immediate=True)` context manager in
   `app/db/sqlite.py`) that opens one connection, issues `BEGIN IMMEDIATE`, yields the connection,
   and commits or rolls back. Repository methods that participate in transactions accept an optional
   connection instead of opening their own.
7. Refuse to start in production (for example when `RAILWAY_ENVIRONMENT` is set) if
   `ADMIN_CLEAR_PASSWORD` is unset or equals the legacy default.
8. Add a Python backup command using `sqlite3.Connection.backup()` followed by
   `PRAGMA integrity_check`.
9. Document deployment sequence: backup, verify, migrate, deploy, smoke test, rollback flag.
10. Do not automatically delete backups; define an explicit retention procedure.

### Exit gate

- Frozen-clock tests prove Jakarta day rollover.
- Backup can restore a representative populated database exactly.
- Current migrations still pass with foreign keys enabled.
- Production configuration cannot silently use an insecure default parent/admin secret.

## 6. M2 — Atomic legacy answer consumption

### Objective

Close the current duplicate-answer race without breaking `/api/answer` compatibility.

### Files to edit

- `app/db/repo.py`
- `app/services/question_service.py`
- `app/services/stats_service.py`
- `app/api/routes.py`
- `tests/integration/test_legacy_routes.py`

### Work

1. Load the persisted daily bank and evaluate the submitted answer before the write transaction.
   Move `cleanup_expired_question_data` out of the answer path (it currently runs DELETEs on every
   `get_daily_bank` call, including during evaluation) to question issuance or startup.
2. Introduce one repository transaction, using the M1 unit-of-work helper, that atomically:
   - Verifies the active session/child/quiz question still matches the submitted `qid`.
   - Verifies daily quota against `child_daily.answered_count` plus the quiz quota cost.
   - Increments session and `child_daily` answered values by the quota cost (1 Math, 2 General
     Knowledge).
   - Increments correct count and earned reward when correct.
   - Clears the active question in `session_current_questions` and the legacy `sessions` columns.
3. Use `BEGIN IMMEDIATE` so two requests cannot both consume the same active question.
4. Preserve the existing request body (`qid`, `answer`, `quiz_type`) and successful response shape
   (`ok`, `correct`, `correct_answer`). No idempotency key, request header, migration, or stored
   response is added in M2; the current client (`static/js/quiz.js`) sends none.
5. The losing duplicate request returns the established synchronization error (HTTP 400,
   `Soal tidak sinkron. Klik Next lagi.`), not a replay of the winning response.
6. A quota failure inside the transaction returns the existing HTTP 409 message and changes nothing.

### Tests

- Duplicate sequential answer counts once.
- Two concurrent answers count once.
- Incorrect answer counts once and clears legacy active question as before.
- Correct answer updates session and child daily aggregates together.
- General Knowledge consumes two quota units once; a request that would exceed the quota changes
  nothing.
- Failure between operations rolls back all changes.
- Evidence is the legacy counters (`sessions`, `child_daily`) and active-question rows; there is no
  per-answer table to inspect.

### Exit gate

- Existing compatibility tests pass.
- Concurrency tests cannot produce duplicate legacy counters or rewards.

## 7. M3 — KidQuest domain, schema, and content

### Objective

Create additive authoritative storage and validate the exact Q001 content contract without exposing
new routes yet.

### Files to add

- `app/domain/kidquest/__init__.py`
- `app/domain/kidquest/content.py`
- `app/domain/kidquest/geometry.py`
- `app/domain/kidquest/roads.py`
- `app/domain/kidquest/theme.py`
- `app/domain/kidquest/state.py`
- `app/db/kidquest_repo.py`
- `content/kidquest/quests.json`
- `content/kidquest/buildings.json`
- `content/kidquest/themes.json`
- `content/kidquest/roads.json`
- `content/kidquest/assets.schema.json`
- `content/kidquest/layouts/pulau_tunas_v1.json`
- `tests/unit/kidquest/test_content.py`
- `tests/unit/kidquest/test_geometry.py`
- `tests/unit/kidquest/test_roads.py`
- `tests/unit/kidquest/test_theme_manifest.py`
- `tests/unit/kidquest/test_state_machine.py`
- `tests/integration/kidquest/test_migration.py`

### Files to edit

- `app/config.py`
- `app/db/migrations.py`
- `app/db/sqlite.py`
- `app/main.py`

### Migration 8 tables

- `kidquest_worlds`
- `kidquest_buildings`
- `kidquest_paths`
- `kidquest_child_quests`
- `kidquest_challenges`
- `kidquest_attempts`
- `kidquest_resource_balances`
- `kidquest_resource_ledger`
- `kidquest_blueprints`
- `kidquest_idempotency`
- `kidquest_daily_usage`

### Required database constraints

- World child primary key restricted by application to configured profiles.
- Unique `(child, quest_id)` quest state.
- Valid quest status `CHECK` constraint.
- Unique logical attempt/idempotency source.
- Unique resource ledger source for each reward or spend.
- Nonnegative resource balance.
- Foreign keys from buildings, challenges, attempts, and ledger records.
- Partial unique `(child, type)` constraint for the six core building types; optional future
  structures require explicit instance-limit content rather than bypassing this rule.
- World `theme_id` restricted to a supported manifest ID and defaulted to `perkampungan`.
- Unique `(child, x, y)` path cell; paths remain theme-neutral logical state.
- Useful indexes for child/quest/status and challenge lookup.

### Content validation

Validate:

- Schema/content version.
- Unique quest and building IDs.
- Known skill/resource/challenge types.
- Acyclic and reachable quest prerequisites.
- Footprints and coordinates inside the layout.
- Building entrances and rotations compatible with footprints.
- Theme parity for every required logical asset.
- All 16 N-E-S-W masks for both roads and shore transitions in each theme.
- Q001 reward equals its first required placement cost.
- Tutorial placement zone has at least one valid 2×2 location.
- All child-facing strings are nonempty.
- Numeric answer and visual operands agree.

### Exit gate

- Migration 8 is additive and idempotent.
- Legacy rows remain byte-for-byte/logically unchanged in migration tests.
- Invalid content fails with actionable messages.
- World initialization is idempotent and isolated by child.
- Theme selection is stored once per world; buildings and paths contain no presentation skin state.

## 7A. M3A — Visual foundation and asset pipeline

### Objective

Prove the child experience and theme architecture before bulk illustration. Deliver approved
information architecture, Q001/theme/build responsive flows, a tested clickable prototype, reusable
component/state specifications, neutral graybox, validated manifests, the cross-theme Q001 golden
asset set, and a repeatable design-to-engineering workflow.

### Files to add

- `design/kidquest/README.md`
- `design/kidquest/flows/` for approved child/parent task and state diagrams
- `design/kidquest/wireframes/` or exported review artifacts for phone/desktop transformations
- `design/kidquest/components/README.md` mapping design names/tokens/states to engineering components
- `design/kidquest/usability/decision-log.md` with de-identified findings and revisions
- `design/kidquest/templates/` for footprint, anchor, entrance, overhang, and preview guides
- `design/kidquest/source-metadata.json`
- `scripts/validate_kidquest_assets.py`
- `static/images/kidquest/shared/` for semantic overlays and neutral fallback
- `static/images/kidquest/themes/{perkampungan,kingdom,city}/`
- `tests/unit/kidquest/test_asset_validation.py`
- `tests/browser/kidquest/test_visual_gallery.py` when browser screenshot tooling is selected

### Work

1. Freeze user roles, terminology, screen inventory, logical catalog, geometry requirements, and
   first-house success/comprehension criteria from the visual pipeline.
2. Approve child navigation, screen inventory, Q001/theme/build task flows, one-primary-objective
   rule, locked reasons, session-resume checkpoint, and responsive low-fidelity wireframes.
3. Test a clickable phone prototype with the household child/parent and revise failed comprehension
   before polished art; store only de-identified decisions.
4. Approve foundation/semantic/theme/component tokens and the first-house component state matrix,
   including keyboard, screen reader, focus return, reduced motion, errors, and stale/retry behavior.
5. Approve the three art bibles/shared geometry, then build a neutral 8×8 graybox using real
   footprints, entrances, water, obstacles, quest board, tutorial zone, road layer, and semantic
   placement overlays.
6. Implement manifest/schema validation for paths, file dimensions, alpha, byte budgets, checksums,
   anchors, all required theme variants, and logical geometry parity.
7. Add a development-only component/asset gallery for every theme, road mask, component/building
   state, long Indonesian string, and responsive proof size.
8. Produce the golden non-building set in all three themes: terrain sample including every shore
   mask used by `pulau_tunas_v1`, quest board, all 16 road masks, `wood` resource icon, theme
   selector thumbnail, and shared focus/selection/validity/connectivity overlays. Buildings,
   including `starter_house`, are not produced here; they come only from the per-theme sprite maps
   (KQ-025 → KQ-026/027/028 → KQ-029).
9. Review side by side at 38, 48, and 64 px per cell, using a non-production graybox building study
   to prove the geometry; correct geometry before the building sprite-map contract (KQ-025) is
   frozen.
10. Record ownership/license and reproducible export metadata for each source.

### Exit gate

- Graybox proves world interaction at 360 px before final decoration.
- Revised Q001/theme/build prototype passes four of five representative tasks without adult
  correction; theme is understood as free and progress-preserving.
- Phone and desktop-capacity handoff specifies every first-house component/state and focus behavior.
- The golden set has identical logical footprints, entrances, and anchors across themes.
- All 16 road masks join correctly in a 3×3 test scene for every theme.
- The graybox building study proves the anchor/footprint rules that KQ-025 freezes for the
  building sprite map.
- Missing, oversized, opaque, or geometry-incompatible assets fail validation with an actionable
  message.
- Art, product, engineering, accessibility, and cultural review approve the golden set.

## 8. M4 — Q001 transactional service and API

### Objective

Implement the complete backend state machine and invariant theme selection before building the new
UI.

### Files to add

- `app/services/kidquest_service.py`
- `app/api/kidquest_routes.py`
- `app/api/schemas.py` or `app/api/kidquest_schemas.py`
- `tests/integration/kidquest/test_state_api.py`
- `tests/integration/kidquest/test_q001_flow.py`
- `tests/integration/kidquest/test_idempotency.py`
- `tests/integration/kidquest/test_concurrency.py`
- `tests/integration/kidquest/test_theme_api.py`

### Files to edit

- `app/main.py`
- `app/config.py`
- `app/services/session_service.py` only for shared active-child helpers

### Service operations

1. `get_or_create_state(child)`
2. `start_quest(child, quest_id)`
3. `issue_or_resume_challenge(child, quest_id)`
4. `submit_answer(child, challenge_id, answer, hint_count, idempotency_key)`
5. `place_building(child, request, idempotency_key)`
6. `list_themes()`
7. `change_theme(child, theme_id, world_version, idempotency_key)`

### API rules

- Return `PROFILE_REQUIRED` when no selected child exists.
- Enforce `KIDQUEST_ENABLED` and profile allowlist on every route.
- Never accept a child identifier as mutation authority.
- Require and length-limit `Idempotency-Key` on answer and placement.
- Store request hash and full successful/error response for deterministic replay.
- Use typed request models with coordinate, answer, rotation, and key limits.
- Use structured error codes from the PRD.
- Do not return the correct answer on an incorrect attempt.
- Theme changes accept only manifest-backed IDs and may update only theme metadata and world
  optimistic version.

### Answer transaction tests

- First incorrect attempt: one attempt, one daily usage, no reward, challenge remains active.
- Retry correct: one additional attempt, quest ready, one wood credit source, one blueprint.
- Same key replay: identical response, no mutation.
- Same key/different request: 409.
- Concurrent correct submissions: one reward.
- Daily cap: accepted attempts blocked after configured limit; replay still works.

### Placement transaction tests

- Valid placement spends four wood once and completes Q001.
- Collision, out-of-bounds, blocked cell, tutorial-zone violation, missing blueprint, insufficient
  balance, stale world version, and disabled profile all fail without mutation.
- Concurrent placement requests cannot overlap or overspend.
- Same key replay returns the same building.

### Theme transaction tests

- A new world starts as `perkampungan` and reports the three supported themes.
- Switching to Kingdom or City persists after refresh.
- A serialized before/after comparison proves buildings, paths, inventory, balances, blueprints,
  quests, attempts, and learning totals are unchanged.
- Same-key replay returns the same response without another world-version increment.
- Unsupported theme, conflicting key reuse, stale world version, and incomplete manifest fail
  without mutation.

### Exit gate

- The entire Q001 backend flow passes through HTTP integration tests.
- Duplicate/concurrency cases are deterministic.
- Feature disabled mode exposes no usable KidQuest mutation surface.

## 9. M5 — First-house frontend

### Objective

Deliver a child-usable end-to-end experience with the current Jinja and vanilla JavaScript stack.

### Files to add

- `app/web/templates/kidquest_world.html`
- `static/css/kidquest-tokens.css`
- `static/css/kidquest.css`
- `static/js/kidquest.js`
- approved golden world/building/road assets under `static/images/kidquest/`
- `tests/integration/kidquest/test_pages.py`

### Files to edit

- `app/web/templates/home.html`
- `app/web/templates/base.html` if shared navigation is appropriate
- `app/api/kidquest_routes.py`
- `app/api/routes.py` only for a visible, compatibility-safe entry point if needed
- `Readme.md`

### UI states

- Loading and recoverable network error.
- Calm returning-session summary with authoritative changes, current objective, and Resume.
- Empty initialized island with Q001 available.
- Theme selector with local preview, cancel, confirmed persistence, and recoverable error.
- Q001 story/detail.
- Active numeric challenge with explicit Submit.
- Incorrect hint/retry.
- Correct reward and ready-to-build state.
- Placement preview: valid, invalid, stale-world retry.
- Completed house and session checkpoint.
- Post-house contextual theme introduction without a forced selection.
- Daily cap reached while world remains interactive.

### Interaction requirements

- Use CSS Grid for the 8×8 map.
- Implement the approved Dunia/Misi/Bangun child shell, one recommended objective, explicit locked
  reasons, and component names/states from the visual pipeline; do not introduce Dompet before its
  parent-enabled economy milestone.
- Reuse the existing Kids Math App colors and layout anatomy for all application UI: dark-navy
  shell, current header/workspace/tab/card/button/dialog patterns, typography, breakpoints, and the
  active child's blue or purple accent. Keep the natural illustrated theme only inside the world
  canvas; theme selection must not repaint the surrounding shell.
- Resolve every visual through the selected theme manifest; do not branch on theme IDs for
  individual assets.
- Render in terrain, shore/water, road, shadow, building/prop, semantic overlay, and UI layers with
  row-based object ordering.
- Use tap/click selection; no drag dependency.
- Generate idempotency keys once per logical submit and retain them across network retry.
- Disable buttons only while the current request is in flight; restore actionable errors.
- Do not optimistically alter authoritative balance or building state before server success.
- Include keyboard controls, ARIA labels, visible focus, 44×44 targets, and reduced-motion behavior.
- Show at most one priority badge per world object; move lower-priority state into the inspector.
- Use no push notification, streak, limited-time, live-ops, or guilt-based return treatment.
- Lazy-load only the selected full theme pack; theme selector thumbnails remain within the visual
  pipeline budget.

### Exit gate

- Q001 can be completed manually at 360 px width and desktop width.
- Refresh works at every state transition.
- Network retry after server success does not duplicate state.
- Existing quiz and statistics navigation remains obvious and functional.
- Each theme renders the same Q001 world state, and switching theme changes no logical snapshot
  field except theme metadata and optimistic version.
- Applicable AC-22, AC-23, and AC-25 usability/comprehension gates pass on the implemented UI, not
  only the prototype.

## 10. M6 — Pilot hardening and deployment

### Objective

Prove migration safety, authorization, accessibility, rollback, and production operability.

### Files to add

- `app/security/adult_session.py`
- `app/services/parent_auth_service.py`
- `tests/integration/test_parent_auth.py`
- `tests/integration/kidquest/test_end_to_end.py`
- `docs/KidQuest_Deployment_Runbook.md`

### Files to edit

- `app/config.py`
- `app/api/kidquest_routes.py`
- `app/api/routes.py`
- `app/services/admin_service.py`
- `app/db/repo.py`
- `docker-entrypoint.sh`
- `Readme.md`

### Work

1. Add PBKDF2 PIN verification and signed, expiring adult session cookie.
2. Protect cross-child and destructive operations. New KidQuest parent reporting, parent settings,
   and scoped resets require the adult session. The legacy household recap (`/stats`,
   `/api/stats`, which returns both children) stays unchanged as a compatibility surface for the
   pilot; gating it is a separate product decision recorded in PRD AC-09.
3. Separate legacy clear from KidQuest clear (see section 14). The existing `/api/admin/clear`
   keeps its request/response shape and its legacy-only scope: it never deletes `kidquest_*`
   tables. It remains password-protected with the non-default production password enforced in M1.
   New per-child scoped resets live behind the adult session with explicit scope and confirmation.
4. Add structured logs for operation, request ID, content version, result, latency, and error code,
   excluding raw answers and unnecessary child PII.
5. Run backup → migration → enabled-profile smoke → disable-flag rollback rehearsal.
6. Test on current mobile Safari/Chrome-class browsers where available.
7. Verify world load target and asset sizes under representative network throttling.
8. Review content with a parent and child before enabling more quests.
9. Run the three-theme screenshot matrix at phone, tablet, and desktop widths, including missing
   asset fallback, keyboard focus, 200% zoom, and reduced motion.

### Exit gate

- Adult-only tests pass.
- First-house acceptance passes as scoped in PRD section 23 ("First-deliverable acceptance
  scope"): AC-01 through AC-13 and AC-16 in full; AC-14 and AC-15 in their first-house scope; and
  AC-22, AC-23, and AC-25 for first-house screens. The full AC-14 inventory and the road-editing
  and bridge parts of AC-15 are verified in M8 (KQ-019, KQ-021, KQ-023), not here.
- Backup restores successfully after migration.
- `KIDQUEST_ENABLED=false` restores legacy-only behavior without data loss.
- Deployment runbook has been rehearsed on a copy of production data.

## 11. M7 — Economy and manual cash-out foundation

Begin only after M6, Q001 observation, an approved parent-funded liability policy, and a completed
economy simulation. Ship behind independent economy and cash-out flags.

### Files to add

- `app/domain/kidquest/economy.py`
- `app/domain/kidquest/blueprints.py`
- `app/db/kidquest_economy_repo.py`
- `app/services/kidquest_economy_service.py`
- `app/api/kidquest_economy_routes.py`
- `content/kidquest/economy.json`
- `content/kidquest/levels.json`
- `content/kidquest/blueprints.json`
- `content/kidquest/supplies.json`
- `scripts/simulate_kidquest_economy.py`
- `scripts/reconcile_kidquest_economy.py`
- `tests/unit/kidquest/test_economy_rules.py`
- `tests/integration/kidquest/test_wallet_ledger.py`
- `tests/integration/kidquest/test_investment.py`
- `tests/integration/kidquest/test_blueprint_sources.py`
- `tests/integration/kidquest/test_cashout.py`
- `tests/integration/kidquest/test_economy_reconciliation.py`
- `tests/browser/kidquest/test_wallet_and_cashout_ux.py`

### Migration 9 tables

Migration numbering note: KQ-011 uses Migration 9 for adult-reset audit/session revocation, so the M7 economy migration uses the next migration number after it.

- `kidquest_wallet_balances`
- `kidquest_wallet_ledger`
- `kidquest_xp_progress`
- `kidquest_blueprint_discovery`
- `kidquest_supply_inventory`
- `kidquest_building_operations`
- `kidquest_building_daily_income`
- `kidquest_cashout_requests`
- `kidquest_cashout_sources`
- `kidquest_cashout_events`

Historical aggregate Rp is snapshotted once as `legacy_rp`; it is conversion-only unless a parent
explicitly approves migration to cash-out eligibility. Never reconstruct active wallet balances from
mutable statistics after migration.

### Work

1. Build the deterministic, draft-only simulator engine as isolated core task KQ-030. It may be
   completed before M6 because it imports no production runtime code and selects no final values.
   KQ-031 may add deterministic sensitivity analysis and draft candidate ranking without choosing
   final values. After M6 and Q001 observation, KQ-012 uses both tools to simulate light, regular,
   heavy, historical-balance, and all-building scenarios over 7, 30, and 90 days before selecting
   conversion denominations, prices, income rates, and funded limits.
2. Credit unique eligible answer earnings and XP inside the accepted-answer transaction when the
   economy flag is enabled.
3. Implement exact 25% Savings / 75% Builder Credit investment with server quotes, immutable linked
   ledger entries, idempotency, and concurrency tests.
4. Add known-item store purchases for materials and eligible blueprints; no random purchase.
5. Add quest, level-choice, fixed-price, and guaranteed Discovery Meter blueprint sources with
   duplicate prevention; core blueprint grants exist immediately, but optional Shop/Discovery
   mutations reject until Q006/core onboarding is complete.
6. Prototype and comprehension-test child Wallet/investment/request and adult queue/mark-paid flows;
   revise until Savings versus Builder Credits and Requested/Approved/Paid are understood.
7. Implement the approved child Wallet, exact split review, known-item Store, Savings, and request
   timeline behind flags. Do not release Wallet to the child until the Q002 tutorial in M8; do not
   expose optional blueprint Shop/Discovery UI until Q006/core onboarding completes. Keep
   child/adult shells and actions distinct.
8. Implement cash-out reservation and the `REQUESTED → APPROVED → PAID` state machine with
   rejection/cancellation release paths. Payment remains external and adult-recorded.
9. Add parent limits, reserved/paid/projected liability views, source-labelled history, economy
   pause controls, and reconciliation/backup procedures.

### Exit gate

- Ledger sums, balances, reservations, paid requests, and legacy opening snapshots reconcile exactly.
- Duplicate/concurrent earnings, investment, purchase, and request transitions mutate once.
- Approval cannot be confused with payment; no code invokes a bank or payment gateway.
- Parent-funded daily/monthly limits cannot be exceeded by earning or approval paths.
- Progression-critical blueprints never depend on chance; discovery is non-purchasable, guaranteed
  by a published threshold, and duplicate-safe.
- AC-24 passes: tested children understand the split, tested pairs distinguish request/approval/paid,
  and approval never displays payment completion.
- Economy-on/cash-out-off removes payout actions without empty navigation, broken promises, or hidden
  links to adult-only endpoints.
- Invalid feature combinations fail startup/readiness: building income requires economy, cash-out,
  adult authorization, and funded limits.
- Disabling economy/cash-out preserves existing histories and returns Q001/legacy behavior safely.

## 12. M8 — Six-quest, road, supply, and productive-building expansion

Begin only after M7 reconciliation and parent liability gates pass.

- Add Q002–Q006 content and all three visual variants for each remaining building.
- Add inventory view, quest dependency rendering, building movement, and session summary.
- Add free `basic_road` placement/removal after Q003, the 48-segment limit, adjacency masks,
  entrance connectivity guidance, and Q005 bridge graph connection.
- Add `place_path`, `remove_path`, and affected-component connectivity service operations plus
  idempotent `POST /api/kidquest/paths` and `DELETE /api/kidquest/paths/{path_id}` routes.
- Complete the 168-asset MVP inventory, source/license metadata, gallery, and manifest validation.
- Add COUNT_GROUPS and PATTERN_BASIC only with curated content and accessible controls.
- Add Garden seeds/water, Bakery ingredients, and Market stock as fixed known supply items purchasable
  only with quiz-funded Builder Credits.
- Implement staged teaching: Q002 investment/material/Garden plus one free starter supply when
  funded building income is enabled (otherwise defer that unique credit); Q003 stone and roads; Q004
  nonproductive Park; Q005 special Bridge/new area; Q006 Market and multi-resource planning. Defer
  optional XP shop/discovery UI until core onboarding completes.
- Add three-active-day supply capacity, three-day income accumulation, production pause reasons,
  collection UI, and daily unique income ledger sources.
- Keep Starter House, Park, and Bridge nonproductive while preserving their world/learning benefits.
- Enforce one instance per core building. Construction is instant; MVP has no demolition, upgrade,
  or repair. Free movement retains loaded supply; road connectivity is guidance and does not change
  income.
- When building income is disabled, productive buildings render as practice/world destinations with
  no stranded supply or income controls.
- Keep each quest, store item, supply rule, and production rule in versioned content and dedicated
  tests. Do not make a 20–30 quest library a launch dependency.

### M8 road, theme, supply, and income tests

- Every road mask 0–15 is generated from N/E/S/W adjacency and updates with its neighbors.
- Road placement rejects buildings, fixed obstacles, water, and the segment limit without mutation.
- The bridge joins only its two declared ends; disconnected buildings remain usable for learning.
- Switching themes preserves graph, coordinates, economy, supply, income, and quest state.
- Q002–Q006 cannot ship if any required theme variant is missing.
- A productive building credits at most once per eligible Jakarta day and consumes supply only when
  the matching income credit commits.
- Q001–Q006 unlock only in the configured linear sequence; Q002 starter supply and each core building
  are credited/created at most once under duplicate and concurrent requests.
- Empty, parent-paused, or liability-limited production creates no income and consumes no supply.
- Building Income cannot be invested, spent, or converted into supplies; it can only be reserved for
  manual cash-out.
- Moving a productive building retains operation/supply/history and creates no new income; road and
  theme changes do not alter production eligibility or rate.
- Visual/browser tests enforce one priority badge per world object and verify lower-priority states
  remain understandable in the inspector.

## 13. M9 — Parent insights and adaptation

Begin only after attempt data exists and the reporting rules can be validated.

- Add adult-only overview and child detail pages.
- Report attempts, accuracy, hint usage, quest completion, and last practiced time by skill.
- Add deterministic practice suggestions.
- Reuse the M7 parent economy view for wallet sources, Savings, Building Income, requests, funded
  limits, and external-payment audit rather than creating a second balance authority.
- Introduce `kidquest_skill_progress` only when its derivation and repair strategy are defined.
- Enable per-skill adaptation behind `KIDQUEST_ADAPTIVE_ENABLED`.
- Never label mastery from one or two successes.

## 14. Compatibility policy

### Routes

Legacy route paths and successful response fields remain stable. New KidQuest errors use the
structured KidQuest envelope without changing legacy error responses during the first slice.

### Statistics

Before M7, KidQuest accepted attempts may update `child_daily` answered/correct counters but Q001
uses its starter kit and does not create a cash wallet. After the economy is explicitly enabled, an
eligible correct answer creates one unique wallet earning source inside the same transaction while
legacy aggregate statistics remain compatible. The wallet is never reconstructed by summing legacy
aggregates, and compatibility tests prove one answer cannot be counted as two wallet credits.

### Admin clear

Existing clear behavior must be explicitly characterized. Today `/api/admin/clear` deletes all
sessions, statistics, served questions, daily banks, and active questions for both children, then
runs `VACUUM`. That endpoint keeps its request/response contract and legacy-only scope; new game
data is not silently added to it. A new adult-gated scoped reset takes one child and one of:

- Legacy learning history only.
- KidQuest world/progress only.
- All child data.

Each scope uses a separate confirmation value and audit event.
Financial history has stricter rules: pending reservations must be resolved, a reconciliation/export
must pass, and paid cash-out events remain audit records rather than being silently erased by a
normal world or learning reset.

## 15. Database rollout and rollback

### Before deployment

1. Disable writes or deploy during household downtime.
2. Run `scripts/backup_db.py` against the Railway volume.
3. Verify backup integrity and record file size/hash.
4. Run migrations on a restored copy first.
5. Run the legacy compatibility suite against the migrated copy.

### Deploy

1. Deploy code with `KIDQUEST_ENABLED=false`.
2. Verify `/health`, Math, General Knowledge, answer, and statistics.
3. Enable KidQuest for one profile through `KIDQUEST_PROFILE_ALLOWLIST`.
4. Complete the Q001 smoke path.
5. Enable the second profile after verification.
6. For M7+, deploy with economy, cash-out, Savings Bonus, and building-income flags false; run ledger
   reconciliation before enabling one funded profile at a time.

### Rollback

1. Set `KIDQUEST_ENABLED=false`.
2. Roll back application code if necessary; leave additive tables intact.
3. Restore the backup only for confirmed migration/data corruption, not ordinary application
   rollback.
4. Preserve logs and the failed database copy for diagnosis.

## 16. Required verification commands

Exact commands may be adjusted when the dev dependencies are added.

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/pytest -q
.venv/bin/python scripts/migrate.py
.venv/bin/python scripts/backup_db.py --help
./run.sh
```

Manual smoke checks:

1. Select each profile and answer one legacy Math question.
2. Answer one General Knowledge question.
3. Verify `/stats` historical values.
4. Complete Q001 with one wrong answer, hint, correct retry, and placement.
5. Refresh before and after each transition.
6. Retry the same answer and placement requests with the same keys.
7. Preview, cancel, then persist each theme and compare logical-state snapshots.
8. Render every road mask and placement/connectivity overlay in each theme.
9. Verify the other child's world is unchanged.
10. Reach/temporarily configure the KidQuest daily cap and confirm building inspection remains.
11. Disable KidQuest and verify the legacy app remains usable.
12. For M7+, invest a quoted amount and verify the exact 25/75 split and duplicate replay.
13. Create, approve, reject, cancel, and externally mark-paid cash-out requests; reconcile every
    source reservation and balance.
14. For M8+, supply each productive building, accrue three eligible Jakarta days, test the cap, and
    prove paused income consumes no supply.

## 17. Initial change sequence

Keep commits and reviews small:

1. Add dev test harness and legacy characterization tests.
2. Add Jakarta clock and cookie configuration.
3. Add backup/restore tooling and database connection pragmas.
4. Make legacy answer consumption atomic.
5. Freeze logical building, entrance, road, and theme manifests.
6. Add migration 8 and Q001 content validation.
7. Add graybox, asset validator/gallery, and three-theme golden set.
8. Add world initialization and read-only state API.
9. Add idempotent theme selection and invariant tests.
10. Add quest start/challenge APIs.
11. Add idempotent transactional answer/reward flow.
12. Add idempotent transactional placement flow.
13. Add themed world/quest/build UI.
14. Add adult gate and scoped deletion.
15. Run migration, concurrency, visual, accessibility, and deployment verification.
16. Add the economy simulator and approve versioned prices/limits before wallet schema or UI.
17. Add Migration 9, immutable wallet/XP ledgers, opening legacy snapshot, and reconciliation.
18. Add 25/75 investment, fixed store, blueprint sources, and duplicate/concurrency tests.
19. Add manual cash-out reservations, parent state transitions, external-payment marking, and audit.
20. Add Q002–Q006, supplies, productive daily income, road expansion, and complete theme packs.

No commit should combine schema, transaction behavior, and frontend redesign into one review unit.

## 18. Known risks

| Risk | Mitigation |
| --- | --- |
| Duplicate reward or spend | Immediate transactions, unique sources, idempotency records, concurrency tests |
| Legacy regression | Characterization suite before refactor; feature flag off by default |
| Data loss | Verified backup, additive migrations, no destructive down migration |
| SQLite contention | Short transactions, explicit busy timeout, single process, retryable error handling |
| Profile data exposure | Active-child server authority and adult gate for cross-child views |
| Scope expansion | Q001 exit gate before Q002–Q006 or advanced puzzles |
| Child frustration | Explicit submit, hints, retry, restricted tutorial placement |
| Content mismatch | Versioned definitions and startup/CI validation |
| Theme forks gameplay | Theme-neutral logical state and before/after invariant snapshots |
| Asset-set explosion | Fixed 56-per-theme MVP inventory, golden-set gate, manifest validation |
| Theme geometry drift | Shared templates, side-by-side building reviews, immutable logical geometry |
| Road seam/connectivity bugs | Fixed 4-bit masks, gallery, all-mask and graph tests |
| Cultural caricature | Art bible, prohibited motifs, and Indonesian cultural review gate |
| Mobile payload growth | Per-file/theme budgets, selected-pack lazy loading, CI size checks |
| Frontend rewrite delay | CSS Grid and existing Jinja/JS stack |
| Misleading learning claims | Evidence reporting first; mastery/adaptation behind flags |
| Unfunded real-money liability | Parent-funded daily/monthly limits enforced before credit; economy off by default |
| Double credit or payout | Immutable unique ledger sources, reservations, idempotency, reconciliation |
| Child confuses saving with interest | Label 25% as automatic Savings; Savings Bonus separate and parent-funded |
| Self-funding production loop | Building Income cash-out only; supplies require quiz-funded Builder Credits |
| Random blueprint frustration | Core guarantees, published Discovery threshold, no duplicates or paid chance |
| Daily-pressure habit | Three-day supply/accrual, no streak loss, neutral pause behavior |
| Onboarding overload | One new system per Q001–Q006 step; optional blueprint systems after Q006 |
| Wrong resume/next action | Server-derived objective priority and persisted-state integration tests |
| Feature-mode dead end | Dependency validation plus complete economy/cash-out/income UI matrix |
| Productive-building farming | One instance per core type and unique building/day income source |
| Unreviewed retention mechanics | No push, streak, expiring offer, or remote live-ops surface in MVP |

## 19. First-deliverable checklist

- [ ] Legacy test baseline exists and passes.
- [ ] Jakarta clock is deterministic in tests.
- [ ] Backup and restore are verified.
- [ ] Legacy answer race is closed.
- [ ] Migration 8 is additive and tested on populated legacy data.
- [ ] Q001 and starter content validate.
- [ ] Theme, road, and asset manifests validate with complete cross-theme parity.
- [ ] Child navigation, Q001/theme/build flows, responsive wireframes, component state matrix, and
      de-identified prototype decision log are approved.
- [ ] Graybox and golden non-building set pass 360 px and accessibility review.
- [ ] Six buildings × three themes are generated as three fixed-layout sprite maps and extracted
      with identical anchors and footprints (KQ-025–KQ-029).
- [ ] Each child gets an independent world exactly once.
- [ ] Incorrect retry records no reward.
- [ ] Correct retry grants one reward and blueprint.
- [ ] Valid house placement spends once and persists.
- [ ] Invalid/concurrent placement is mutation-free.
- [ ] Duplicate keys replay safely; conflicting reuse returns 409.
- [ ] Theme selection is idempotent and changes no logical state.
- [ ] All 16 golden road masks join correctly in all three themes.
- [ ] World UI works at 360 px and with keyboard focus.
- [ ] Implemented first-house UI passes applicable AC-22, AC-23, and AC-25 gates.
- [ ] Legacy quiz/statistics remain visible and functional.
- [ ] KidQuest can be disabled without deleting data.
- [ ] Deployment runbook is rehearsed.

## 20. Minimum-playable-economy checklist

- [ ] Economy simulator covers light, regular, heavy, historical, and all-building scenarios.
- [ ] Parent has approved and configured funded daily/monthly liability limits.
- [ ] Migration 9 snapshots legacy Rp once and reconciles without changing legacy statistics.
- [ ] Every eligible answer earning and XP source is unique and transactional.
- [ ] Investment quotes and commits always produce the exact 25% Savings / 75% Builder Credit split.
- [ ] Wood, stone, supply, and blueprint purchases are fixed, known, and duplicate-safe.
- [ ] Core blueprints are guaranteed; level/shop/discovery paths enforce eligibility and duplicates.
- [ ] Q002–Q006 onboarding introduces only its scheduled concept; optional blueprint systems wait
      until core onboarding completes.
- [ ] AC-26 passes for the core teaching ladder, one-time Q002 starter supply, and every supported
      feature-mode combination.
- [ ] Cash-out request, approval, rejection, cancellation, and paid transitions reconcile exactly.
- [ ] Wallet split and payout prototypes plus implementation pass AC-24 comprehension gates.
- [ ] No application code sends money or integrates a bank/payment gateway.
- [ ] Garden, Bakery, and Market daily income consumes supply only with a committed income credit.
- [ ] Starter House, Park, and Bridge remain nonproductive and retain their learning/world benefits.
- [ ] Core buildings are unique; move retains supply; no demolition/upgrade/repair is exposed.
- [ ] AC-27 proves unique core buildings, instant construction, state-preserving movement, and no
      road/theme production effect.
- [ ] Economy-off, cashout-off, and building-income-off combinations have coherent navigation and no
      stranded controls.
- [ ] Building Income cannot fund supplies or any game purchase.
- [ ] Paused/limited production consumes no supply and produces no hidden liability.
- [ ] AC-28 proves calm return behavior and absence of push, streak, expiring offer, or remote
      live-operations paths.
- [ ] Backup/restore, rollback, and feature-disable preserve all wallet and payout audit history.

