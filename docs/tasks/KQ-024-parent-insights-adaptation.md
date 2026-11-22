---
id: KQ-024
title: Add parent insights and guarded adaptation
status: NOT_STARTED
owner: unassigned
depends_on: [KQ-011]
milestone: M9
updated: 2026-11-21
---

# KQ-024 — Add parent insights and guarded adaptation

## Outcome

After pilot evidence exists, parents receive concise learning insights and children may receive transparent, reversible difficulty suggestions without premature mastery claims.

## Preconditions

- KQ-011 is `DONE` and a documented pilot dataset/evidence review exists.
- If economy summaries are included, KQ-016 must also be `DONE`.

## Scope

1. Define privacy-minimized parent learning summaries: practiced skills, recent activity, hint/retry patterns, and quest progress.
2. Define deterministic, explainable suggestion rules with minimum evidence thresholds.
3. Implement parent-visible explanations and reversible child difficulty adjustments behind a feature flag.
4. Prevent sparse data from producing mastery or deficiency labels.
5. Validate isolation, correctness, accessibility, and usefulness with pilot evidence.

## Acceptance criteria

- [ ] Insights use only the selected child's data and disclose their evidence window.
- [ ] No recommendation is produced below the approved evidence threshold.
- [ ] Suggestions are explainable, reversible, and do not lock content.
- [ ] Parent views avoid stigmatizing language and unsupported mastery claims.
- [ ] Feature flags allow immediate disablement without data loss.

## Verification

- Run deterministic rule fixtures, profile-isolation tests, sparse-data cases, and parent usability review.

## Out of scope

- Machine-learning personalization, diagnosis, school grading, or autonomous curriculum decisions.

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Task packet created; task must wait for pilot evidence. |

## Completion handoff

- **Summary:** Pending
- **Files changed:** Pending
- **Migrations/data impact:** Pending
- **Verification performed:** Pending
- **Commit:** Pending
- **Follow-ups:** Pending

