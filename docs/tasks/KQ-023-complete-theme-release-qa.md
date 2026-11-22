---
id: KQ-023
title: Complete theme assets and release QA
status: NOT_STARTED
owner: unassigned
depends_on: [KQ-018, KQ-019, KQ-020, KQ-021, KQ-022, KQ-029]
milestone: M8
updated: 2026-11-21
---

# KQ-023 — Complete theme assets and release QA

## Outcome

The complete MVP world is visually coherent, accessible, performant, culturally reviewed, and free of missing or geometrically inconsistent theme variants.

## Scope

1. Complete non-building environment, terrain, road, quest-board, feedback, icon, and shared UI assets required by the pipeline.
2. Integrate the extracted and validated theme sprite-map output from KQ-029 without reopening its ownership.
3. Validate manifests, naming, dimensions, anchors, footprints, exports, fallbacks, and licensing/source provenance.
4. Run the full viewport × theme × quest-state screenshot matrix.
5. Complete visual, cultural, accessibility, performance, and usability release reviews.

## Acceptance criteria

- [ ] No required logical asset ID or theme variant is missing.
- [ ] The sprite-map contract, three theme-generation tasks, and extraction task KQ-025–KQ-029 are `DONE` with evidence.
- [ ] Theme switching produces no coordinate, hitbox, footprint, or state drift.
- [ ] Visual QA and PRD acceptance criteria AC22–AC28 pass or have explicit approved waivers.
- [ ] AC-14 passes in full (the remainder deferred from the first-deliverable scope in PRD §23): all 168 theme assets including props, fences, plant variations, `stone` icon, and all 16 shore masks per theme.
- [ ] Asset budgets and target-device performance thresholds pass.

## Verification

- Run asset validators, automated screenshot comparisons, full end-to-end tests, accessibility audits, and target-device profiling.

## Out of scope

- Generating or extracting building sprites inside this task, new building types, and post-MVP visual expansion.

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Task packet created; building sprite generation is owned by KQ-025–KQ-029. |

## Completion handoff

- **Summary:** Pending
- **Files changed/artifacts:** Pending
- **Migrations/data impact:** None expected
- **Verification performed:** Pending
- **Commit/artifact revision:** Pending
- **Follow-ups:** Pending

