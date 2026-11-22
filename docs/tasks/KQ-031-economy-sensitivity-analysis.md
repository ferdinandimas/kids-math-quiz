---
id: KQ-031
title: Build deterministic economy sensitivity analysis
status: DONE
owner: codex-core
depends_on: [KQ-030]
milestone: Core
updated: 2026-11-22
---

# KQ-031 — Build deterministic economy sensitivity analysis

## Outcome

KQ-012 can compare transparent draft parameter alternatives using reproducible rankings, target penalties, and warning evidence without treating any candidate as production-approved.

## Scope

1. Sweep explicit axes for investment denomination, resource prices, supply prices, daily income, and parent monthly liability.
2. Apply integer, documented scaling to the KQ-030 draft baseline.
3. Evaluate every candidate against the required scenario matrix.
4. Score progression timing, all-building completion, illustrative payback, structural safety, warning volume, and cash-out exposure.
5. Produce deterministic JSON, Markdown, and CSV rankings with the baseline candidate identified.

## Acceptance criteria

- [x] The axis Cartesian product is complete, unique, stable, and bounded by configured safety limits.
- [x] Every candidate remains `draft_not_approved`, validates through KQ-030, and preserves exact 25/75 investment.
- [x] Scores disclose every penalty component and use stable tie-breaking.
- [x] The unmodified baseline is identifiable and reproduces KQ-030 baseline metrics.
- [x] Reports expose candidate count, axes, rounding, targets, top candidates, and baseline rank.
- [x] Repeated runs are byte-for-byte deterministic in JSON, Markdown, and CSV.
- [x] No production runtime module imports sensitivity tooling or its input file.

## Verification

- Run focused sensitivity and simulator tests.
- Run JSON, Markdown, and CSV CLI output twice and compare bytes.
- Run the repository suite excluding any independently failing active Claude module and record it.

## Out of scope

- Selecting or approving the winning parameters, using pilot evidence, production configuration, wallet/schema/API/UI implementation, or changing Claude's asset/frontend work.

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-22 | codex-core | IN_PROGRESS | Claimed after KQ-030 DONE. Scope is limited to `tools/kidquest_economy`, one new CLI, simulation inputs, focused tests, and task documentation. No production, asset, or frontend files. |
| 2026-11-22 | codex-core | DONE | Implemented a bounded 162-candidate Cartesian sweep with stable IDs, integer half-up scaling, six disclosed penalty components, baseline comparison, JSON/Markdown/CSV output, and stable ranking. Focused KQ-030/KQ-031 tests: 29 passed. Repository suite excluding Claude's independently failing active asset-validator module: 864 passed. Asset module remains 36 passed, 3 skipped, 2 failed; it was not edited. Default baseline ranks 76/162 (score 707); 88 candidates pass core timing/payback/safety targets. The rank-1 draft scores 561 but remains explicitly unapproved. |

## Completion handoff

- **Summary:** Added reproducible parameter sensitivity analysis over investment denomination, resource prices, supply prices, income rates, and monthly liability. Rankings expose all axes, rounding, targets, penalties, warnings, outcomes, and baseline position without approving a candidate.
- **Files changed:** `tools/kidquest_economy/sensitivity.py`, `tools/kidquest_economy/__init__.py`, `scripts/analyze_kidquest_economy.py`, `simulation/kidquest/economy/{README,sensitivity_v1.json}`, `tests/unit/kidquest/test_economy_sensitivity.py`, PRD/plan/task documentation.
- **Migrations/data impact:** None
- **Verification performed:** 29 focused economy tests passed; 864 repository tests passed with Claude's active asset-validator module excluded; deterministic JSON/Markdown/CSV verified by repeated CLI runs; source asset validator still has its pre-existing 2 failures and was not touched.
- **Commit:** Pending
- **Follow-ups:** KQ-012 must combine this ranking with M6/pilot evidence and parent-funded liability approval. Rank is not approval; high heavy-cohort cash-out exposure remains visible even in the current top candidate.

