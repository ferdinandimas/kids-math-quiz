---
id: KQ-021
title: Deliver Q005 Bridge and expansion
status: NOT_STARTED
owner: unassigned
depends_on: [KQ-020, KQ-029]
milestone: M8
updated: 2026-11-21
---

# KQ-021 — Deliver Q005 Bridge and expansion

## Outcome

Q005 teaches subtraction and infrastructure planning by placing one Bridge in its special zone to connect roads and unlock the next configured build area.

## Scope

1. Implement Q005 challenge/progression content.
2. Implement special-zone Bridge preview and placement with two-end connectivity validation.
3. Update the road graph and unlock only the configured next area inside the MVP world boundary.
4. Integrate the approved Bridge assets in all themes.
5. Add special-zone, collision, connectivity, unlock, idempotency, and end-to-end tests.

## Acceptance criteria

- [ ] Bridge can be placed only in the defined bridge zone and correct orientation.
- [ ] Placement creates valid connection ends and unlocks the configured area once.
- [ ] AC-15 bridge connectivity (deferred from the first deliverable) passes: the bridge joins only its two declared ends.
- [ ] Bridge has no supply or income behavior.
- [ ] It cannot be moved outside its special zone.
- [ ] Theme switching preserves placement, connections, and unlocked area.

## Verification

- Test valid/invalid special-zone placements, graph updates, retry, and all theme variants.

## Out of scope

- Free-form bridge placement, world enlargement beyond the configured MVP area, and Q006 Market.

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

