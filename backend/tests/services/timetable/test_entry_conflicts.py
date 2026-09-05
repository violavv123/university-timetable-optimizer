import pytest
from app.core.exceptions import BusinessRuleError
from app.models.enums import CourseOfferingStatus
from app.schemas.course_offering import CourseOfferingUpdate
from app.services.scheduling_input.course_offering import update_course_offering
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
    make_scheduling_context,
)
from tests.services.timetable.factories import (
    TimetableContext,
    make_manual_entry,
    make_profile_slots,
    make_timetable_run,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("shared_resource", "expected_code"),
    [
        ("room", "ROOM_OVERLAP"),
        ("staff", "STAFF_OVERLAP"),
        ("group", "STUDENT_GROUP_OVERLAP"),
    ],
)
def test_overlapping_room_staff_and_group_assignments_are_rejected(
    db: Session,
    shared_resource: str,
    expected_code: str,
) -> None:
    scheduling = make_scheduling_context(db, lecture_periods=4)
    slots = make_profile_slots(db, scheduling, count=4)
    first_session = make_course_session(db, scheduling)
    second_session = make_course_session(db, scheduling)

    second_room = make_room(
        db,
        scheduling.resources.hierarchy.faculty.id,
    )
    second_staff = make_staff_member(
        db,
        scheduling.resources.hierarchy.faculty.id,
    )
    make_staff_course(db, second_staff, scheduling.resources.course)
    second_group = make_student_group(db, scheduling.resources)

    attach_group(db, first_session, scheduling.cohort)
    attach_staff(db, first_session, scheduling.staff_member)
    attach_group(
        db,
        second_session,
        scheduling.cohort if shared_resource == "group" else second_group,
    )
    attach_staff(
        db,
        second_session,
        scheduling.staff_member if shared_resource == "staff" else second_staff,
    )
    update_course_offering(
        db,
        scheduling.offering.id,
        CourseOfferingUpdate(status=CourseOfferingStatus.READY),
    )
    run = make_timetable_run(db, scheduling)
    first_context = TimetableContext(
        scheduling,
        first_session,
        slots,
        run,
    )
    second_context = TimetableContext(
        scheduling,
        second_session,
        slots,
        run,
    )
    make_manual_entry(db, first_context)

    with pytest.raises(BusinessRuleError) as exc_info:
        make_manual_entry(
            db,
            second_context,
            room_id=(scheduling.room.id if shared_resource == "room" else second_room.id),
        )

    assert exc_info.value.details["conflict_code"] == expected_code
