---
id: KQ-018
title: Deliver Q002 Garden onboarding
status: NOT_STARTED
owner: unassigned
depends_on: [KQ-016, KQ-017, KQ-029]
milestone: M8
updated: 2026-11-21
---

# KQ-018 — Deliver Q002 Garden onboarding

## Outcome

Q002 teaches grouping, the first world investment (exact 25% Savings / 75% Builder Credits preview), a known wood purchase with Builder Credits, Garden placement, and the productive-building supply concept without creating a progression deadlock.

## Scope

1. Implement `COUNT_GROUPS` challenge content and Q002 progression.
2. Guide the child through the investment preview, known wood purchase with Builder Credits, and Garden placement.
3. Integrate the approved Garden assets for all three themes.
4. When income is enabled, grant exactly one starter seeds/water pack after first Garden placement; otherwise defer that grant once until eligible.
5. Add resume, mode-combination, idempotency, and end-to-end tests.

## Acceptance criteria

- [ ] Q002 unlocks only after its documented prerequisites.
- [ ] Conversion, purchase, construction, and supply effects are atomic and understandable.
- [ ] The starter supply pack is credited at most once and never disappears because a feature is disabled.
- [ ] Practice remains available when production is disabled or empty.
- [ ] Garden visuals switch themes without state or geometry changes.

## Verification

- Run the full Q002 journey in each economy/income feature-mode combination and all three themes.

## Out of scope

- Q003 roads/Bakery and optional blueprint discovery.

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

