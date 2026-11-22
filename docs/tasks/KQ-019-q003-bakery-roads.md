---
id: KQ-019
title: Deliver Q003 Bakery and roads
status: NOT_STARTED
owner: unassigned
depends_on: [KQ-018, KQ-029]
milestone: M8
updated: 2026-11-21
---

# KQ-019 — Deliver Q003 Bakery and roads

## Outcome

Q003 introduces stone, mixed construction costs, Bakery supply, and understandable road editing without making road layout an income penalty.

## Scope

1. Implement Q003 addition/subtraction challenge content and unlock rules.
2. Add stone purchase and mixed-resource Bakery construction.
3. Implement road placement/removal, automatic 16-mask resolution, persistence, and connectivity guidance.
4. Integrate the approved Bakery assets and theme-specific roads.
5. Add Bakery supply, practice access, road-boundary, mask, persistence, and end-to-end tests.

## Acceptance criteria

- [ ] Every road neighborhood resolves to the correct mask in each theme.
- [ ] AC-15 road-editing parts deferred from the first deliverable pass: placement, removal, neighbor updates, 48-segment limit, collision, and building-entrance connectivity.
- [ ] Road editing cannot change or multiply balances and never controls income eligibility.
- [ ] Bakery construction and supply reconcile with the ledger.
- [ ] Empty supply never blocks math practice.
- [ ] Theme switching preserves the road graph and Bakery geometry.

## Verification

- Exercise all 16 road masks and the full Q003 flow in all three themes.

## Out of scope

- Road-based income optimization and Q004 Park content.

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Task packet created. |

## Completion handoff

- **Summary:** Pending
- **Files changed:** Pending
- **Migrations/data impact:** Pending
- **Verification performed:** Pending
- **Commit:** Pending
- **Follow-ups:** Pending

