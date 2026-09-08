from app.scheduling.domain import SolverAssignment
from app.scheduling.result_validator import validate_solver_result
from tests.scheduling.factories import make_input, make_occurrence, make_slots


def test_independent_validator_rejects_hierarchy_student_overlap() -> None:
    slots = make_slots(days=(1,), per_day=2)
    lecture = make_occurrence(session_id=1, slots=slots, room_ids=frozenset({1}))
    laboratory = make_occurrence(
        session_id=2,
        slots=slots,
        room_ids=frozenset({3}),
        staff_id=2,
        direct_group_ids=frozenset({4}),
        student_resource_ids=frozenset({4}),
    )
    data = make_input(lecture, laboratory, slots=slots)
    start_slot_id = slots[0].id

    result = validate_solver_result(
        data,
        (
            SolverAssignment(1, 1, 1, start_slot_id),
            SolverAssignment(2, 1, 3, start_slot_id),
        ),
    )

    assert "STUDENT_GROUP_OVERLAP" in {issue.code for issue in result.issues}
