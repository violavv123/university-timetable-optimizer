from dataclasses import replace

from app.models.enums import TimeConstraintType
from app.scheduling.domain import SessionTimeConstraint, SolverAssignment
from app.scheduling.metrics import calculate_metrics, placement_penalty
from tests.scheduling.factories import occurrence, room, scheduling_input, slot, start


def test_master_session_outside_evening_window_is_measured() -> None:
    time_slot = slot(1, day=1, index=0, start_minute=8 * 60, week_index=0)
    classroom = room(1, "611", 100)
    session = occurrence(
        1,
        start(time_slot),
        classroom,
        demand=50,
        level_code="MSc",
    )
    data = scheduling_input(
        slots=(time_slot,),
        rooms=(classroom,),
        occurrences=(session,),
    )
    assignment = SolverAssignment(
        course_session_id=1,
        occurrence_number=1,
        room_id=classroom.id,
        start_slot_id=time_slot.id,
    )

    metrics = calculate_metrics(data, (assignment,))

    assert metrics.master_outside_preferred_slots == 12
    assert metrics.soft_penalty == 62  # 12 evening slots + 50 unused seats


def test_multiple_day_preferences_are_alternatives_not_cumulative_penalties() -> None:
    time_slot = slot(1, day=1, index=0, start_minute=17 * 60, week_index=0)
    classroom = room(1, "611", 100)
    session = occurrence(
        1,
        start(time_slot),
        classroom,
        demand=50,
        level_code="MSc",
    )
    session = replace(
        session,
        time_constraints=(
            SessionTimeConstraint(
                day_of_week=1,
                start_minute=17 * 60,
                end_minute=20 * 60,
                constraint_type=TimeConstraintType.PREFERRED_WINDOW,
                preference_weight=5,
            ),
            SessionTimeConstraint(
                day_of_week=2,
                start_minute=17 * 60,
                end_minute=20 * 60,
                constraint_type=TimeConstraintType.PREFERRED_WINDOW,
                preference_weight=5,
            ),
        ),
    )
    data = scheduling_input(
        slots=(time_slot,),
        rooms=(classroom,),
        occurrences=(session,),
    )

    assert placement_penalty(data, session, start(time_slot), classroom) == 50
