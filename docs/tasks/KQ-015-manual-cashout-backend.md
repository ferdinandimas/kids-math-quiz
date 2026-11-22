---
id: KQ-015
title: Build manual cash-out workflow
status: NOT_STARTED
owner: unassigned
depends_on: [KQ-013, KQ-014]
milestone: M7
updated: 2026-11-21
---

# KQ-015 — Build manual cash-out workflow

## Outcome

Cash-out is trackable and auditable inside KidQuest while the parent pays outside the application; no bank or payment gateway integration is introduced.

## Scope

1. Implement child cash-out request creation with reservation of eligible cash-out-only balance.
2. Implement adult-gated approve, reject, cancel, and mark-paid transitions.
3. Enforce parent-configured limits, valid state transitions, idempotency, and profile isolation.
4. Release or settle reserved balances correctly for every terminal path.
5. Expose a complete audit timeline and reconciliation coverage without collecting payment credentials.

## Deliverables

- Cash-out state machine, services, APIs, audit events, and configuration.
- Adult authorization and child/parent read models.
- State-transition, concurrency, authorization, and reconciliation tests.

## Acceptance criteria

- [ ] Request creation reserves funds atomically and prevents double spending.
- [ ] Only an authorized adult can approve, reject, or mark a request paid.
- [ ] Paid means the parent attests to an external payment; the app never initiates one.
- [ ] Invalid or repeated transitions are harmless and precisely reported.
- [ ] All terminal states reconcile reserved and available balances.

## Verification

- Run the complete state-transition matrix, authorization tests, and concurrent-request tests.
- Reconcile ledgers for approved/paid, rejected, and cancelled examples.

## Out of scope

- Payment gateway, banking API, stored bank details, automated transfer, or financial-interest promises.

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

