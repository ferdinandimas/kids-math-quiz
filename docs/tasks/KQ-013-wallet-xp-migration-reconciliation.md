---
id: KQ-013
title: Add wallet, XP, ledger migration and reconciliation
status: NOT_STARTED
owner: unassigned
depends_on: [KQ-012]
milestone: M7
updated: 2026-11-21
---

# KQ-013 — Add wallet, XP, ledger migration and reconciliation

## Outcome

The approved economy has auditable, reconcilable persistence for wallet balances, XP, blueprints, supplies, building operations, income, and cash-out.

## Scope

1. Design Migration 9 using the approved KQ-012 parameter version.
2. Add immutable ledger entries and balance/projection constraints for each currency bucket.
3. Add XP/level, blueprint ownership/discovery, supply inventory, building operation/accrual, and cash-out request structures.
4. Snapshot historical balances without silently converting or spending them.
5. Build reconciliation and repair-report tooling that detects but does not hide discrepancies.

## Deliverables

- Migration 9 and schema documentation.
- Ledger/reconciliation services and read-only reconciliation command/report.
- Migration, constraint, idempotency, and historical-data tests.

## Acceptance criteria

- [ ] Existing and empty databases migrate safely and idempotently.
- [ ] Every balance mutation requires an immutable, uniquely keyed ledger event.
- [ ] Database constraints prevent invalid negative/reserved states.
- [ ] Historical values are traceable before and after migration.
- [ ] Reconciliation reports zero unexplained variance for test fixtures.

## Verification

- Run migration tests against empty, legacy, and high-balance fixtures.
- Run reconciliation before/after representative transactions and attach results.

## Out of scope

- Child conversion UI, store purchases, parent cash-out actions, and income accrual behavior.

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Task packet created. |

## Completion handoff

- **Summary:** Pending
- **Files changed:** Pending
- **Migrations/data impact:** Migration 9
- **Verification performed:** Pending
- **Commit:** Pending
- **Follow-ups:** Pending

