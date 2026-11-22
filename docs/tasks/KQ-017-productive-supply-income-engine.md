---
id: KQ-017
title: Build supply and productive-income engine
status: NOT_STARTED
owner: unassigned
depends_on: [KQ-012, KQ-013, KQ-015]
milestone: M8
updated: 2026-11-21
---

# KQ-017 — Build supply and productive-income engine

## Outcome

Productive buildings generate bounded cash-out-only income while supplied, with deterministic accrual and no duplicate daily grants.

## Scope

1. Implement building operational state, three-day supply lots, and explicit resupply using quiz-funded in-game resources.
2. Implement deterministic daily accrual in Asia/Jakarta time with one unique event per building/day.
3. Enforce funded limits, maximum accrual/catch-up, pause behavior, and feature-mode combinations.
4. Route building-generated value exclusively to the cash-out-only bucket.
5. Preserve supply/accrual state when a building moves and test long offline periods.

## Deliverables

- Supply, operation, accrual, and income services/jobs/APIs.
- Feature-flag modes and reconciliation events.
- Time-boundary, concurrency, offline, move, and pause tests.

## Acceptance criteria

- [ ] An operating supplied building earns at most once per eligible day.
- [ ] Paused or unsupplied buildings neither earn nor incorrectly consume supply.
- [ ] Accrual is bounded and deterministic across restart, retry, and Jakarta midnight.
- [ ] Income cannot be converted into building resources and only enters cash-out flow.
- [ ] Every supply debit and income credit is ledger-reconcilable.

## Verification

- Run a time-travel matrix for normal days, midnight, downtime, retry, pause, and moving.
- Reconcile all modeled supply and income events against KQ-012 expectations.

## Out of scope

- Garden/Bakery/Market quest UI and external payment.

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Task packet created. |

## Completion handoff

- **Summary:** Pending
- **Files changed:** Pending
- **Migrations/data impact:** Uses Migration 9
- **Verification performed:** Pending
- **Commit:** Pending
- **Follow-ups:** Pending

