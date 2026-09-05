import pytest
from app.core.exceptions import BusinessRuleError
from app.models.enums import CourseOfferingStatus, DependencyType, RoomStatus
from app.schemas.course_offering import CourseOfferingUpdate
from app.services.scheduling_input.course_offering import update_course_offering
from app.services.timetable.publication import publish_timetable_run
from app.services.timetable.validation import validate_timetable_run
from sqlalchemy.orm import Session
from tests.services.resources.factories import (
    make_room,
    make_staff_course,
    make_staff_member,
    make_student_group,
)
from tests.services.scheduling_input.factories import (
    attach_group,
    attach_staff,
    make_course_session,
    make_dependency,
    make_scheduling_context,
)
from tests.services.timetable.factories import (
    TimetableContext,
    complete_valid_manual_run,
    make_manual_entry,
    make_profile_slots,
    make_ready_timetable_context,
    make_timetable_run,
)

pytestmark = pytest.mark.integration


def test_whole_run_validation_enforces_session_dependencies(db: Session) -> None:
    scheduling = make_scheduling_context(db, lecture_periods=2)
    slots = make_profile_slots(db, scheduling, count=4)
    predecessor = make_course_session(db, scheduling, duration_slots=1)
    successor = make_course_session(db, scheduling, duration_slots=1)
    other_room = make_room(
        db,
        scheduling.resources.hierarchy.faculty.id,
    )
    other_staff = make_staff_member(
        db,
        scheduling.resources.hierarchy.faculty.id,
    )
    make_staff_course(db, other_staff, scheduling.resources.course)
    other_group = make_student_group(db, scheduling.resources)
    attach_group(db, predecessor, scheduling.cohort)
    attach_staff(db, predecessor, scheduling.staff_member)
    attach_group(db, successor, other_group)
    attach_staff(db, successor, other_staff)
    make_dependency(
        db,
        predecessor,
        successor,
        dependency_type=DependencyType.PRECEDES,
    )
    update_course_offering(
        db,
        scheduling.offering.id,
        CourseOfferingUpdate(status=CourseOfferingStatus.READY),
    )
    run = make_timetable_run(db, scheduling)
    predecessor_context = TimetableContext(
        scheduling,
        predecessor,
        slots,
        run,
    )
    successor_context = TimetableContext(
        scheduling,
        successor,
        slots,
        run,
    )
    make_manual_entry(
        db,
        predecessor_context,
        start_slot_id=slots[2].id,
    )
    make_manual_entry(
        db,
        successor_context,
        room_id=other_room.id,
        start_slot_id=slots[0].id,
    )

    result = validate_timetable_run(db, run.id)

    assert result.is_valid is False
    assert "DEPENDENCY_VIOLATION" in {conflict.code for conflict in result.hard_conflicts}


def test_publication_revalidates_instead_of_trusting_stored_conflict_count(
    db: Session,
) -> None:
    context = make_ready_timetable_context(db)
    make_manual_entry(db, context)
    complete_valid_manual_run(db, context)

    # Simulate an external/imported change after the run was completed.
    context.scheduling.room.status = RoomStatus.MAINTENANCE
    context.run.hard_conflicts = 0
    db.commit()

    with pytest.raises(BusinessRuleError, match="zero hard conflicts") as exc_info:
        publish_timetable_run(db, context.run.id)

    assert "ROOM_INACTIVE" in exc_info.value.details["conflict_codes"]
