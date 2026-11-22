"""Quest state machine: LOCKED -> AVAILABLE -> IN_PROGRESS -> READY_TO_BUILD -> COMPLETED.

Transitions move forward one step at a time and never backward (PRD section 9.1). A separate
repair command, not normal play, is the only way to correct an invalid state.
"""

from enum import Enum


class QuestStatus(str, Enum):
    LOCKED = "LOCKED"
    AVAILABLE = "AVAILABLE"
    IN_PROGRESS = "IN_PROGRESS"
    READY_TO_BUILD = "READY_TO_BUILD"
    COMPLETED = "COMPLETED"


# Must match the CHECK constraint on kidquest_child_quests.status in Migration 8.
QUEST_STATUS_ORDER = tuple(QuestStatus)


def next_status(current: QuestStatus) -> QuestStatus | None:
    index = QUEST_STATUS_ORDER.index(current)
    return QUEST_STATUS_ORDER[index + 1] if index + 1 < len(QUEST_STATUS_ORDER) else None


def can_transition(current: QuestStatus, new: QuestStatus) -> bool:
    return next_status(current) is new


def transition(current: QuestStatus, new: QuestStatus) -> QuestStatus:
    if not can_transition(current, new):
        raise ValueError(f"Quest cannot move from {current.value} to {new.value}")
    return new
