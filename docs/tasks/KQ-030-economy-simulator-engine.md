---
id: KQ-030
title: Build the isolated economy simulator engine
status: DONE
owner: codex-core
depends_on: [KQ-004]
milestone: Core
updated: 2026-11-22
---

# KQ-030 — Build the isolated economy simulator engine

## Outcome

A deterministic, versioned command-line engine can exercise KidQuest economy scenarios without importing or changing production runtime code. It produces evidence for KQ-012 but does not select or approve production values.

## Scope

1. Model integer-Rupiah earnings, historical `legacy_rp`, exact 25/75 investment, Builder Credit spending, construction, building-specific supply, bounded daily income, and cash-out exposure.
2. Provide light (5), regular (15), and heavy (50) correct-answer cohorts over 7, 30, and 90 days.
3. Provide historical-balance and all-building scenarios.
4. Report time to first productive building, first supply, all buildings, income, balances, exposure, and illustrative payback.
5. Detect negative balances, progression deadlocks, trivial/excessive waits, cap violations, and self-funding behavior.
6. Load a clearly labelled draft parameter file; production code must not import it.

## Deliverables

- Isolated simulator package and CLI.
- Draft, non-production parameter set and scenario definitions.
- Determinism, split, cap, non-self-funding, scenario-matrix, validation, and CLI tests.
- Reproducible JSON and Markdown reports.

## Acceptance criteria

- [x] Default runs cover 5/15/50 correct answers per day and 7/30/90-day horizons.
- [x] Historical balances and an all-building goal are covered.
- [x] Every investment preserves integer equality: source debit = 25% Savings + 75% Builder Credit.
- [x] Building income is never available for investment or supply purchase.
- [x] Supply is consumed only on a successful bounded income credit.
- [x] Repeated runs with identical inputs are byte-for-byte deterministic.
- [x] Invalid, non-integer, or production-labelled parameter files fail with actionable errors.
- [x] No application runtime module imports simulator or draft parameter data.

## Verification

- Run the focused unit tests and the full suite.
- Run the CLI twice in JSON mode and compare output bytes.
- Run Markdown output and record scenario/warning counts.

## Out of scope

- Selecting final prices, rates, limits, or denominations; product/parent approval; production wallet schema, APIs, flags, ledgers, or UI.

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-22 | codex-core | IN_PROGRESS | Claimed as an isolated core task. KQ-004 is DONE. New tooling/tests only; no overlap with active KQ-006 asset or KQ-010 frontend files. KQ-012 now depends on this engine plus KQ-011/pilot evidence. |
| 2026-11-22 | codex-core | DONE | Implemented 14 deterministic default scenarios, exact 25/75 integer investment, construction/supply/income/liability modeling, draft validation, JSON/Markdown CLI, and 16 focused tests. Focused tests: 16 passed. Full suite: 887 passed, 3 skipped, 2 failures confined to Claude's active KQ-006 `test_asset_validation.py`; no edits made there. Full suite excluding that active module: 851 passed. Two JSON CLI runs were byte-identical (200,106 bytes). |
| 2026-11-22 | lead | DONE | Lead review of Codex's work: accepted. Independently verified: 16 focused tests pass; `PYTHONPATH=. scripts/simulate_kidquest_economy.py --format json` run twice is byte-identical (573,162 bytes with the current draft parameters; the 200,106-byte figure in the entry above is stale); Markdown report prints 14 scenarios and 12 warnings (11 `cashout_exposure_above_monthly_limit`, 1 `progression_deadlock_first_productive`) under a 'DRAFT SIMULATION ONLY' banner; only `scripts/simulate_kidquest_economy.py` imports `tools.kidquest_economy`, so no `app/` module can load the simulator or draft parameters. The script needs `PYTHONPATH=.` like the other project scripts. The full suite's only failures are the two in-progress KQ-006 asset-validator tests. KQ-012 must use these draft findings: cash-out exposure above the monthly limit in 11 of 14 scenarios, and the light 7-day cohort never reaching a productive building. |

## Completion handoff

- **Summary:** Added a draft-only deterministic economy simulator covering required cohorts, horizons, historical balances, all buildings, investment, construction, supply, bounded income, payback, cash-out exposure, and diagnostic warnings. It cannot load production-labelled parameters.
- **Files changed:** `tools/__init__.py`, `tools/kidquest_economy/{__init__,simulator}.py`, `scripts/simulate_kidquest_economy.py`, `simulation/kidquest/economy/{README,draft_v1.json}`, `tests/unit/kidquest/test_economy_simulator.py`, PRD/plan/task documentation.
- **Migrations/data impact:** None
- **Verification performed:** 16 focused tests passed; 851 non-KQ-006 tests passed; full run reached 887 passed/3 skipped with 2 unrelated failures in Claude's active KQ-006 asset-validator tests; JSON output was byte-identical across two runs.
- **Commit:** Pending
- **Follow-ups:** KQ-012 must run sensitivity analysis with M6/pilot evidence, select and approve final parameters, and keep production implementation blocked until parent-funded liability approval. Draft output already flags high cash-out exposure and the light 7-day cohort not reaching the first productive building.

