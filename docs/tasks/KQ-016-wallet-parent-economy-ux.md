---
id: KQ-016
title: Build child wallet and parent economy UX
status: NOT_STARTED
owner: unassigned
depends_on: [KQ-005, KQ-014, KQ-015]
milestone: M7
updated: 2026-11-21
---

# KQ-016 — Build child wallet and parent economy UX

## Outcome

Children understand earning, investing into the world (25% Savings / 75% Builder Credits), buying materials with Builder Credits, and cash-out requests, while parents can safely review limits, requests, and ledger history.

## Scope

1. Build the child Wallet with a clear explanation of each balance: Available Rp, Savings, Builder Credits, Building Income (cash-out only), and legacy Rp when present. Do not show "investment" as a balance.
2. Build the investment review (exact Rp → Savings + Builder Credits split) and confirmation, known-item store, blueprint sources, and request timeline.
3. Build adult-gated parent views for limits, requests, approvals, paid confirmation, and ledger history.
4. Test comprehension of the 25% Savings / 75% Builder Credits split and the difference between in-game Builder Credits and external cash-out.
5. Release behind separate feature flags; do not expose Wallet before the Q002 onboarding point defined by the PRD.

## Deliverables

- Responsive child Wallet/store/cash-out UI.
- Parent economy controls and audit views.
- UX copy, accessibility states, tests, and comprehension findings.

## Acceptance criteria

- [ ] The child sees the exact Savings and Builder Credits amounts and resulting balances before confirming an investment.
- [ ] Copy labels the 25% as automatic Savings and never presents it, or the investment, as a bank deposit, interest, a fee, or an automatic cash payment.
- [ ] Parent actions require a valid adult session and show irreversible consequences clearly.
- [ ] Loading, empty, locked, failure, duplicate, and pending states are implemented.
- [ ] Comprehension tests meet PRD thresholds or documented revisions are completed.

## Verification

- Run frontend and end-to-end tests for investment, store, request, and every parent transition.
- Complete child/parent comprehension and accessibility walkthroughs and link evidence.

## Out of scope

- Payment integration, productive income engine, and Q002 gameplay implementation.

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Task packet created. |

## Completion handoff

- **Summary:** Pending
- **Files changed:** Pending
- **Migrations/data impact:** None beyond Migration 9
- **Verification performed:** Pending
- **Commit:** Pending
- **Follow-ups:** Pending

