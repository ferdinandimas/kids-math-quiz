"""Quest statuses move forward one step at a time and never backward."""

import pytest

from app.domain.kidquest.content import load_catalog
from app.domain.kidquest.state import QUEST_STATUS_ORDER, QuestStatus, can_transition, next_status, transition

L, A, P, R, C = (QuestStatus.LOCKED, QuestStatus.AVAILABLE, QuestStatus.IN_PROGRESS,
                 QuestStatus.READY_TO_BUILD, QuestStatus.COMPLETED)


def test_order():
    assert QUEST_STATUS_ORDER == (L, A, P, R, C)
    assert [next_status(s) for s in QUEST_STATUS_ORDER] == [A, P, R, C, None]


@pytest.mark.parametrize("current", QUEST_STATUS_ORDER)
@pytest.mark.parametrize("new", QUEST_STATUS_ORDER)
def test_only_the_next_step_is_allowed(current, new):
    allowed = QUEST_STATUS_ORDER.index(new) == QUEST_STATUS_ORDER.index(current) + 1

    assert can_transition(current, new) is allowed


def test_transition_raises_on_backward_or_skipped_moves():
    assert transition(P, R) is R
    with pytest.raises(ValueError, match="cannot move from COMPLETED to AVAILABLE"):
        transition(C, A)
    with pytest.raises(ValueError):
        transition(A, R)


def test_initial_statuses_from_content():
    quests = load_catalog().quests

    assert {qid: q.initial_status for qid, q in quests.items()} == {
        "Q001": A, "Q002": L, "Q003": L, "Q004": L, "Q005": L, "Q006": L,
    }
