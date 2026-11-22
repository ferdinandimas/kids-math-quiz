# KidQuest Task Execution Protocol

This directory contains independently executable task packets derived from the KidQuest PRD, implementation plan, and visual asset pipeline.

## Before starting a task

1. Read the complete task packet and every linked source section.
2. Confirm every dependency is `DONE` in the [master tracker](../KidQuest_Execution_Tasks.md).
3. Check the repository worktree and preserve unrelated changes.
4. Set `status: IN_PROGRESS`, set `owner`, and update `updated` in the task frontmatter.
5. Update the corresponding row in the master tracker.
6. Append a timestamped execution-log entry before changing implementation files.

## While working

- Stay inside the task's scope and out-of-scope boundaries.
- Record material decisions, migrations, feature-flag choices, and deviations in the execution log.
- If blocked, set `BLOCKED` in both places and state the exact blocker, what was tried, and the decision or access needed.
- If requirements conflict, stop and record the conflict rather than silently inventing product behavior.
- Keep all schema and API work backward-compatible unless the packet explicitly authorizes a breaking change.
- Do not mark generated or placeholder visual assets as production-complete.

## Completing a task

1. Check every acceptance criterion in the task packet.
2. Run every listed verification step and record the command and result.
3. Fill in the completion handoff: summary, files changed, migration effects, tests, commit hash if available, and follow-ups.
4. Set `IN_REVIEW` if external review or product approval remains; otherwise set `DONE`.
5. Update the master tracker to the same status, owner, and date.

`DONE` without recorded evidence is invalid and must be moved back to `IN_REVIEW`.

## Status values

| Status | Meaning |
|---|---|
| `NOT_STARTED` | No implementation work has begun. |
| `IN_PROGRESS` | One named owner is actively implementing the task. |
| `BLOCKED` | Progress cannot continue without a recorded dependency, decision, or access change. |
| `IN_REVIEW` | Implementation and self-verification are complete; review or approval remains. |
| `DONE` | All acceptance criteria and verification evidence are complete. |

Use [`_TASK_TEMPLATE.md`](_TASK_TEMPLATE.md) for any new task. New task IDs must be sequential and added to the master tracker.

