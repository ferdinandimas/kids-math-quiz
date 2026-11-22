# KidQuest Execution Task Tracker

This is the canonical execution board for the KidQuest roadmap. Detailed, agent-ready task packets live in [`docs/tasks/`](tasks/README.md).

## Status contract

Allowed values are `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `IN_REVIEW`, and `DONE`.

- An agent must claim only one task at a time by setting both this table and the task packet to `IN_PROGRESS` and recording its name as owner.
- A task whose dependencies are not `DONE` must not be started unless the task explicitly documents an approved exception.
- `BLOCKED` requires the exact blocker, attempted resolution, and required decision in the task execution log.
- `IN_REVIEW` means implementation and self-verification are complete, but independent review or product approval remains.
- `DONE` requires every acceptance criterion to be checked and verification evidence to be recorded in the task packet.
- The detailed task packet is canonical if this table and a task packet ever disagree. The next agent must repair the table before continuing.

## Master tracker

| ID | Task | Milestone | Depends on | Status | Owner |
|---|---|---|---|---|---|
| [KQ-001](tasks/KQ-001-test-baseline.md) | Establish test and characterization baseline | M0 | — | DONE | senior-dev |
| [KQ-002](tasks/KQ-002-runtime-database-safety.md) | Harden runtime and database safety | M1 | KQ-001 | DONE | senior-dev |
| [KQ-003](tasks/KQ-003-atomic-legacy-answer.md) | Make the legacy answer flow atomic | M2 | KQ-001, KQ-002 | DONE | senior-dev |
| [KQ-004](tasks/KQ-004-kidquest-domain-content-migration.md) | Add KidQuest domain, content, and Migration 8 | M3 | KQ-002 | DONE | senior-dev |
| [KQ-005](tasks/KQ-005-ux-foundation-prototype.md) | Produce UX foundation and prototype | M3A | KQ-004 | IN_REVIEW | ui-ux-designer |
| [KQ-006](tasks/KQ-006-asset-system-graybox-golden-set.md) | Build asset system, graybox, and golden set | M3A | KQ-004, KQ-005 | IN_REVIEW | ui-ux-designer |
| [KQ-007](tasks/KQ-007-q001-state-theme-api.md) | Implement Q001 state and theme APIs | M4 | KQ-003, KQ-004 | DONE | senior-dev |
| [KQ-008](tasks/KQ-008-q001-challenge-answer.md) | Implement Q001 challenge and answer flow | M4 | KQ-003, KQ-004, KQ-007 | DONE | senior-dev |
| [KQ-009](tasks/KQ-009-q001-placement.md) | Implement Q001 building placement | M4 | KQ-008 | DONE | senior-dev |
| [KQ-010](tasks/KQ-010-first-house-frontend.md) | Deliver the first-house frontend slice | M5 | KQ-005–KQ-009, KQ-029 | IN_REVIEW | senior-dev |
| [KQ-011](tasks/KQ-011-adult-gate-pilot-hardening.md) | Add adult gate and pilot hardening | M6 | KQ-010 | IN_PROGRESS | codex-core |
| [KQ-012](tasks/KQ-012-economy-simulator-calibration.md) | Calibrate the economy with a simulator | M7 | KQ-011, KQ-030, KQ-031 | NOT_STARTED | unassigned |
| [KQ-013](tasks/KQ-013-wallet-xp-migration-reconciliation.md) | Add wallet, XP, ledger migration and reconciliation | M7 | KQ-012 | NOT_STARTED | unassigned |
| [KQ-014](tasks/KQ-014-investment-store-blueprint-backend.md) | Build investment, store, and blueprint backend | M7 | KQ-013 | NOT_STARTED | unassigned |
| [KQ-015](tasks/KQ-015-manual-cashout-backend.md) | Build manual cash-out workflow | M7 | KQ-013, KQ-014 | NOT_STARTED | unassigned |
| [KQ-016](tasks/KQ-016-wallet-parent-economy-ux.md) | Build child wallet and parent economy UX | M7 | KQ-005, KQ-014, KQ-015 | NOT_STARTED | unassigned |
| [KQ-017](tasks/KQ-017-productive-supply-income-engine.md) | Build supply and productive-income engine | M8 | KQ-012, KQ-013, KQ-015 | NOT_STARTED | unassigned |
| [KQ-018](tasks/KQ-018-q002-garden-onboarding.md) | Deliver Q002 Garden onboarding | M8 | KQ-016, KQ-017, KQ-029 | NOT_STARTED | unassigned |
| [KQ-019](tasks/KQ-019-q003-bakery-roads.md) | Deliver Q003 Bakery and roads | M8 | KQ-018, KQ-029 | NOT_STARTED | unassigned |
| [KQ-020](tasks/KQ-020-q004-park-patterns.md) | Deliver Q004 Park and patterns | M8 | KQ-019, KQ-029 | NOT_STARTED | unassigned |
| [KQ-021](tasks/KQ-021-q005-bridge-expansion.md) | Deliver Q005 Bridge and expansion | M8 | KQ-020, KQ-029 | NOT_STARTED | unassigned |
| [KQ-022](tasks/KQ-022-q006-market-core-completion.md) | Deliver Q006 Market and core completion | M8 | KQ-021, KQ-029 | NOT_STARTED | unassigned |
| [KQ-023](tasks/KQ-023-complete-theme-release-qa.md) | Complete theme assets and release QA | M8 | KQ-018–KQ-022, KQ-029 | NOT_STARTED | unassigned |
| [KQ-024](tasks/KQ-024-parent-insights-adaptation.md) | Add parent insights and guarded adaptation | M9 | KQ-011, pilot evidence | NOT_STARTED | unassigned |
| [KQ-025](tasks/KQ-025-building-sprite-map-contract.md) | Define the shared building sprite-map contract | Asset | KQ-006 | IN_REVIEW | codex-core |
| [KQ-026](tasks/KQ-026-kingdom-building-sprite-map.md) | Generate the Kingdom building sprite map | Asset | KQ-025 | IN_REVIEW | codex-core |
| [KQ-027](tasks/KQ-027-city-building-sprite-map.md) | Generate the City building sprite map | Asset | KQ-025 | IN_PROGRESS | codex-core |
| [KQ-028](tasks/KQ-028-kampung-building-sprite-map.md) | Generate the Kampung building sprite map | Asset | KQ-025 | IN_REVIEW | codex-core |
| [KQ-029](tasks/KQ-029-building-sprite-extraction-qa.md) | Extract, manifest, and validate all building sprites | Asset | KQ-026, KQ-027, KQ-028 | IN_REVIEW | codex-core |
| [KQ-030](tasks/KQ-030-economy-simulator-engine.md) | Build the isolated economy simulator engine | Core | KQ-004 | DONE | codex-core |
| [KQ-031](tasks/KQ-031-economy-sensitivity-analysis.md) | Build deterministic economy sensitivity analysis | Core | KQ-030 | DONE | codex-core |

## Recommended execution lanes

1. **Safety lane:** KQ-001 → KQ-002 → KQ-003.
2. **Asset lane:** KQ-004 → KQ-005 → KQ-006 → KQ-025. After the fixed sprite-map contract is approved, KQ-026, KQ-027, and KQ-028 may run in parallel; KQ-029 extracts and validates them together.
3. **First playable lane:** KQ-007 → KQ-008 → KQ-009 may run alongside the asset lane; both KQ-009 and KQ-029 feed KQ-010 → KQ-011.
4. **Economy lane:** KQ-030 builds the draft-only simulator engine, then KQ-031 adds deterministic parameter comparison. KQ-012 combines both with M6/pilot evidence and requires explicit calibration approval before KQ-013 starts; then KQ-013 → KQ-014 → KQ-015 → KQ-016.
5. **World expansion lane:** KQ-017 and the validated sprite output from KQ-029 feed the sequential quests KQ-018 → KQ-019 → KQ-020 → KQ-021 → KQ-022; KQ-023 performs final release QA.
6. **Insights lane:** KQ-024 starts only after pilot evidence exists and must not block the M8 world expansion.

## Source of truth

Agents must use these documents together:

- [Product requirements](KidQuest_Build_Your_World_PRD_v1.4.md)
- [Implementation plan](KidQuest_Implementation_Plan.md)
- [Visual design and asset pipeline](KidQuest_Visual_Design_Asset_Pipeline.md)
- [Task execution protocol](tasks/README.md)

## Worker assignment

Product-owner decision (2026-11-22): KQ-006 and KQ-010 are the last tasks executed by Claude subagents. Every later task is executed by Codex (`codex-core`). The lead (Claude session) assigns each task to Codex with a written brief, tracks its progress in this tracker and the task packet, independently verifies the result (full suite, task-specific checks, regression and byte-identity tests), and only the lead sets `DONE`. Workers never commit; the product owner commits reviewed snapshots.

Assignment queue (a task starts only when its dependencies are `DONE`, or when the lead records an approved exception in the packet):

| Order | Task | Starts when |
|---|---|---|
| Done (lead-accepted 2026-11-22) | KQ-011 backend slice | Stays `IN_PROGRESS` overall; remainder waits for KQ-010 `DONE` |
| 1 | KQ-025 sprite-map contract | KQ-006 `IN_REVIEW` (lead exception recorded in the KQ-006 packet; KQ-025 cannot be `DONE` before KQ-006) |
| 1b | Small backend task: per-theme `assets` map in `GET /api/kidquest/themes` (KQ-010 follow-up) | After KQ-025 is assigned; additive only |
| 2 | KQ-026, KQ-027, KQ-028 sprite maps | KQ-025 `DONE` and an image-generation tool is available to the worker |
| 3 | KQ-029 sprite extraction and validation | KQ-026, KQ-027, KQ-028 `DONE` |
| 4 | KQ-011 remainder, KQ-010 asset swap | KQ-010 and KQ-029 `DONE` |
| 5 | KQ-012 economy calibration | KQ-011 `DONE`, KQ-030 `DONE`; needs product-owner approval of parameters |
| 6 | KQ-013, KQ-014, KQ-015, KQ-016, KQ-017 | In dependency order after KQ-012 approval |
| 7 | KQ-018 to KQ-022, then KQ-023 | In dependency order after KQ-016, KQ-017, KQ-029 |
| 8 | KQ-024 | KQ-011 `DONE` and pilot evidence exists |
