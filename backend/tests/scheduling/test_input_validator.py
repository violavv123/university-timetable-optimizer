from dataclasses import replace

from app.scheduling.domain import SchedulingInput
from app.scheduling.input_validator import validate_scheduling_input
from tests.scheduling.factories import make_input, make_occurrence, make_slots


def _codes(data: SchedulingInput) -> set[str]:
    return {issue.code for issue in validate_scheduling_input(data).issues}


def test_unsplit_session_can_use_offering_attendance_fallback() -> None:
    occurrence = replace(
        make_occurrence(),
        direct_group_ids=frozenset(),
        student_resource_ids=frozenset(),
        calculated_attendance=0,
        offering_expected_students=20,
    )

    assert "MISSING_SESSION_ATTENDANCE" not in _codes(make_input(occurrence))


def test_parent_and_descendant_on_same_session_are_rejected() -> None:
    occurrence = replace(
        make_occurrence(),
        direct_group_ids=frozenset({2, 4}),
    )

    assert "AMBIGUOUS_SESSION_GROUP_HIERARCHY" in _codes(make_input(occurrence))


def test_repeated_occurrences_require_enough_distinct_days() -> None:
    slots = make_slots(days=(1,), per_day=4)
    occurrences = tuple(
        make_occurrence(
            occurrence_number=number,
            weekly_frequency=2,
            slots=slots,
        )
        for number in (1, 2)
    )

    assert "INSUFFICIENT_DAYS_FOR_REPEATED_SESSION" in _codes(make_input(*occurrences, slots=slots))
