---
id: KQ-012
title: Calibrate the economy with a simulator
status: NOT_STARTED
owner: unassigned
depends_on: [KQ-011, KQ-030, KQ-031]
milestone: M7
updated: 2026-11-21
---

# KQ-012 — Calibrate the economy with a simulator

## Outcome

Conversion, building, supply, income, blueprint, and cash-out parameters are evidence-based and explicitly approved before production economy code is enabled.

## Scope

1. Use and, where calibration evidence requires it, extend the deterministic KQ-030 simulator for light (5 correct/day), regular (15 correct/day), and heavy (50 correct/day) play over 7, 30, and 90 days, plus the all-building scenario.
2. Model both new-player progression and historical `legacy_rp` balances from the existing application.
3. Model the world-investment rule (each confirmed investment of `available_rp` moves exactly 25% to `savings_rp` and 75% to `builder_credit`), building prices, supply burn, daily income, limits, and blueprint paths.
4. Use KQ-031 to compare alternatives and detect runaway growth, trivial building, deadlocks, excessive waiting, and unaffordable cash-out outcomes.
5. Produce a recommended parameter table with alternatives and obtain recorded product/parent-safety approval.

## Deliverables

- An approved parameter set and scenario inputs for the versioned KQ-030 simulator.
- Calibration report with proposed constants and sensitivity analysis.
- Recorded approval or required revisions.

## Acceptance criteria

- [ ] All required activity/time cohorts and historical-balance cases are simulated.
- [ ] The report shows time-to-first-build, time-to-supply, income growth, and cash-out exposure.
- [ ] Parameters avoid negative balances, infinite growth, and progression deadlocks.
- [ ] Assumptions and rounding behavior are explicit.
- [ ] Final constants are approved before KQ-013 begins.

## Verification

- Run the simulator from a clean environment and reproduce the report.
- Record approved parameter version and approver in the execution log.

## Out of scope

- Production wallet tables, endpoints, or enabling real child economy behavior.

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Task packet created; production implementation is gated on explicit calibration approval. |

## Completion handoff

- **Summary:** Pending
- **Files changed:** Pending
- **Migrations/data impact:** None
- **Verification performed:** Pending
- **Approved parameter version:** Pending
- **Commit:** Pending
- **Follow-ups:** Pending

