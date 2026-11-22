---
id: KQ-022
title: Deliver Q006 Market and core completion
status: NOT_STARTED
owner: unassigned
depends_on: [KQ-021, KQ-029]
milestone: M8
updated: 2026-11-21
---

# KQ-022 — Deliver Q006 Market and core completion

## Outcome

Q006 completes core onboarding with addition/comparison, multi-resource planning, Market placement, and stock supply before optional blueprint systems appear.

## Scope

1. Implement Q006 addition/comparison challenges and multi-resource planning steps.
2. Implement Market Stall purchase/placement and stock supply.
3. Integrate approved Market Stall assets for all themes.
4. Mark core onboarding complete idempotently and only then unlock optional blueprint shop/discovery surfaces.
5. Add supply, income, unlock-order, retry, theme, and end-to-end tests.

## Acceptance criteria

- [ ] Optional discovery/shop systems remain hidden until Q006 completion.
- [ ] Market supply and bounded income follow KQ-017 and reconcile exactly.
- [ ] There is no child trading, advertising, automatic payment, or customer simulation promise.
- [ ] Core completion happens once and survives retries.
- [ ] Theme switching preserves Market state and footprint.

## Verification

- Complete Q006 in all themes; prove optional systems are locked before and available after completion.

## Out of scope

- Marketplace trading, dynamic pricing, advertising, and post-MVP buildings.

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

