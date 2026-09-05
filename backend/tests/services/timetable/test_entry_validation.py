from dataclasses import replace
from datetime import time

import pytest
from app.core.exceptions import (
    BusinessRuleError,
    DuplicateResourceError,
    ResourceInUseError,
)
from app.models.enums import (
    AvailabilityType,
    CourseOfferingStatus,
    TimeConstraintType,
)
from app.schemas.course_offering import CourseOfferingUpdate
from app.services.scheduling_input.course_offering import update_course_offering
from app.services.timetable.publication import publish_timetable_run
from app.services.timetable.timetable_entry import delete_timetable_entry
from sqlalchemy.orm import Session
from tests.services.academic.factories import make_academic_term, make_academic_year
from tests.services.resources.factories import (
    ResourceContext,
    make_room,
    make_room_availability,
    make_staff_availability,
)
from tests.services.scheduling_input.factories import (
    attach_group,
    attach_staff,
    make_course_session,
    make_scheduling_context,
    make_scheduling_profile,
    make_time_constraint,
    make_time_slot,
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


def test_occurrence_number_must_not_exceed_weekly_frequency(
    db: Session,
) -> None:
    context = make_ready_timetable_context(db, weekly_frequency=1)

    with pytest.raises(BusinessRuleError) as exc_info:
        make_manual_entry(db, context, occurrence_number=2)

    assert exc_info.value.details["conflict_code"] == ("INVALID_OCCURRENCE_NUMBER")


def test_same_session_occurrence_is_unique_within_run(db: Session) -> None:
    context = make_ready_timetable_context(db)
    make_manual_entry(db, context)

    with pytest.raises(DuplicateResourceError):
        make_manual_entry(db, context)


def test_only_ready_offerings_can_be_scheduled(db: Session) -> None:
    scheduling = make_scheduling_context(db)
    slots = make_profile_slots(db, scheduling, count=2)
    session = make_course_session(db, scheduling)
    attach_group(db, session, scheduling.cohort)
    attach_staff(db, session, scheduling.staff_member)
    run = make_timetable_run(db, scheduling)
    context = TimetableContext(scheduling, session, slots, run)

    with pytest.raises(BusinessRuleError) as exc_info:
        make_manual_entry(db, context)

    assert exc_info.value.details["conflict_code"] == "OFFERING_NOT_READY"


def test_session_and_run_must_belong_to_same_term(db: Session) -> None:
    context = make_ready_timetable_context(db)
    other_year = make_academic_year(db, start_year=2202)
    other_term = make_academic_term(db, other_year)
    other_resources = ResourceContext(
        context.scheduling.resources.hierarchy,
        other_term,
        context.scheduling.resources.course,
    )
    other_scheduling = replace(
        context.scheduling,
        resources=other_resources,
    )
    other_run = make_timetable_run(db, other_scheduling)
    other_context = replace(context, run=other_run)

    with pytest.raises(BusinessRuleError) as exc_info:
        make_manual_entry(db, other_context)

    assert exc_info.value.details["conflict_code"] == "SESSION_TERM_MISMATCH"


def test_start_slot_must_belong_to_run_profile(db: Session) -> None:
    context = make_ready_timetable_context(db)
    other_profile = make_scheduling_profile(
        db,
        context.scheduling.resources.hierarchy.faculty.id,
    )
    other_slot = make_time_slot(db, other_profile)

    with pytest.raises(BusinessRuleError) as exc_info:
        make_manual_entry(db, context, start_slot_id=other_slot.id)

    assert exc_info.value.details["conflict_code"] == ("START_SLOT_PROFILE_MISMATCH")


def test_session_duration_cannot_cross_a_slot_gap(db: Session) -> None:
    context = make_ready_timetable_context(db, break_after_index=0)

    with pytest.raises(BusinessRuleError) as exc_info:
        make_manual_entry(db, context)

    assert exc_info.value.details["conflict_code"] == "SLOT_TIME_GAP"


def test_assigned_room_must_match_specific_session_room(db: Session) -> None:
    context = make_ready_timetable_context(db, require_specific_room=True)
    other_room = make_room(
        db,
        context.scheduling.resources.hierarchy.faculty.id,
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        make_manual_entry(db, context, room_id=other_room.id)

    assert exc_info.value.details["conflict_code"] == "REQUIRED_ROOM_MISMATCH"


def test_assigned_room_must_hold_all_session_students(db: Session) -> None:
    context = make_ready_timetable_context(db)
    small_room = make_room(
        db,
        context.scheduling.resources.hierarchy.faculty.id,
        capacity=20,
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        make_manual_entry(db, context, room_id=small_room.id)

    assert exc_info.value.details["conflict_code"] == ("ROOM_CAPACITY_EXCEEDED")


@pytest.mark.parametrize(
    ("resource", "expected_code"),
    [
        ("staff", "STAFF_UNAVAILABLE"),
        ("room", "ROOM_UNAVAILABLE"),
    ],
)
def test_entry_respects_hard_resource_availability(
    db: Session,
    resource: str,
    expected_code: str,
) -> None:
    context = make_ready_timetable_context(db)
    term = context.scheduling.resources.academic_term
    if resource == "staff":
        make_staff_availability(
            db,
            context.scheduling.staff_member,
            term,
            start_time=time(8, 0),
            end_time=time(10, 0),
            availability_type=AvailabilityType.UNAVAILABLE,
        )
    else:
        make_room_availability(
            db,
            context.scheduling.room,
            term,
            start_time=time(8, 0),
            end_time=time(10, 0),
            availability_type=AvailabilityType.UNAVAILABLE,
        )

    with pytest.raises(BusinessRuleError) as exc_info:
        make_manual_entry(db, context)

    assert exc_info.value.details["conflict_code"] == expected_code


def test_entry_respects_forbidden_session_window(db: Session) -> None:
    scheduling = make_scheduling_context(db)
    slots = make_profile_slots(db, scheduling, count=2)
    session = make_course_session(db, scheduling)
    attach_group(db, session, scheduling.cohort)
    attach_staff(db, session, scheduling.staff_member)
    make_time_constraint(
        db,
        session,
        constraint_type=TimeConstraintType.FORBIDDEN_WINDOW,
        start_time=time(8, 0),
        end_time=time(10, 0),
    )
    update_course_offering(
        db,
        scheduling.offering.id,
        CourseOfferingUpdate(status=CourseOfferingStatus.READY),
    )
    run = make_timetable_run(db, scheduling)
    context = TimetableContext(scheduling, session, slots, run)

    with pytest.raises(BusinessRuleError) as exc_info:
        make_manual_entry(db, context)

    assert exc_info.value.details["conflict_code"] == ("FORBIDDEN_SESSION_TIME")


def test_locked_entry_must_be_unlocked_before_deletion(db: Session) -> None:
    context = make_ready_timetable_context(db)
    entry = make_manual_entry(db, context, is_locked=True)

    with pytest.raises(ResourceInUseError, match="Unlock"):
        delete_timetable_entry(db, entry.id)


def test_published_entries_are_immutable(db: Session) -> None:
    context = make_ready_timetable_context(db)
    entry = make_manual_entry(db, context)
    complete_valid_manual_run(db, context)
    publish_timetable_run(db, context.run.id)

    with pytest.raises(ResourceInUseError, match="Published"):
        delete_timetable_entry(db, entry.id)
