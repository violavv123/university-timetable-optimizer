from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

from app.models.course_session import CourseSession
from app.models.enums import (
    AssignmentSource,
    CourseOfferingStatus,
    DayOfWeek,
    SchedulingAlgorithm,
    TimetableRunStatus,
    TimetableSourceType,
)
from app.models.time_slot import TimeSlot
from app.models.timetable_entry import TimetableEntry
from app.models.timetable_run import TimetableRun
from app.schemas.course_offering import CourseOfferingUpdate
from app.schemas.timetable_entry import TimetableEntryCreate
from app.schemas.timetable_run import TimetableRunCreate
from app.services.scheduling_input.course_offering import update_course_offering
from app.services.timetable.timetable_entry import create_timetable_entry
from app.services.timetable.timetable_run import (
    complete_timetable_run,
    create_timetable_run,
    start_timetable_run,
)
from sqlalchemy.orm import Session
from tests.services.scheduling_input.factories import (
    SchedulingContext,
    attach_group,
    attach_staff,
    make_course_session,
    make_scheduling_context,
    make_time_slot,
)


@dataclass(frozen=True)
class TimetableContext:
    scheduling: SchedulingContext
    session: CourseSession
    slots: tuple[TimeSlot, ...]
    run: TimetableRun


def _add_minutes(value: time, minutes: int) -> time:
    combined = datetime.combine(datetime.min.date(), value)
    return (combined + timedelta(minutes=minutes)).time()


def make_profile_slots(
    db: Session,
    scheduling: SchedulingContext,
    *,
    count: int = 6,
    start_time: time = time(8, 0),
    day_of_week: DayOfWeek = DayOfWeek.MONDAY,
    break_after_index: int | None = None,
) -> tuple[TimeSlot, ...]:
    current_start = start_time
    slots: list[TimeSlot] = []
    for index in range(count):
        current_end = _add_minutes(
            current_start,
            scheduling.profile.slot_minutes,
        )
        slots.append(
            make_time_slot(
                db,
                scheduling.profile,
                slot_index=index,
                start_time=current_start,
                end_time=current_end,
                day_of_week=day_of_week,
            )
        )
        current_start = current_end
        if break_after_index == index:
            current_start = _add_minutes(current_start, 15)
    return tuple(slots)


def make_timetable_run(
    db: Session,
    scheduling: SchedulingContext,
    *,
    name: str | None = None,
    source_type: TimetableSourceType = TimetableSourceType.MANUAL,
    algorithm: SchedulingAlgorithm | None = None,
    parameters: dict[str, object] | None = None,
) -> TimetableRun:
    selected_algorithm = algorithm
    if selected_algorithm is None and source_type in {
        TimetableSourceType.GENERATED,
        TimetableSourceType.REOPTIMIZED,
    }:
        selected_algorithm = SchedulingAlgorithm.CP_SAT
    return create_timetable_run(
        db,
        TimetableRunCreate(
            academic_term_id=scheduling.resources.academic_term.id,
            scheduling_profile_id=scheduling.profile.id,
            name=name or f"Run {uuid4().hex[:8]}",
            source_type=source_type,
            algorithm=selected_algorithm,
            parameters=parameters or {},
        ),
    )


def make_ready_timetable_context(
    db: Session,
    *,
    weekly_frequency: int = 1,
    duration_slots: int = 2,
    slot_count: int = 6,
    break_after_index: int | None = None,
    source_type: TimetableSourceType = TimetableSourceType.MANUAL,
    require_specific_room: bool = False,
) -> TimetableContext:
    scheduling = make_scheduling_context(
        db,
        lecture_periods=weekly_frequency * duration_slots,
    )
    slots = make_profile_slots(
        db,
        scheduling,
        count=slot_count,
        break_after_index=break_after_index,
    )
    session = make_course_session(
        db,
        scheduling,
        weekly_frequency=weekly_frequency,
        duration_slots=duration_slots,
        required_room_id=(scheduling.room.id if require_specific_room else None),
    )
    attach_group(db, session, scheduling.cohort)
    attach_staff(db, session, scheduling.staff_member)
    update_course_offering(
        db,
        scheduling.offering.id,
        CourseOfferingUpdate(status=CourseOfferingStatus.READY),
    )
    run = make_timetable_run(db, scheduling, source_type=source_type)
    return TimetableContext(scheduling, session, slots, run)


def make_manual_entry(
    db: Session,
    context: TimetableContext,
    *,
    session: CourseSession | None = None,
    occurrence_number: int = 1,
    room_id: int | None = None,
    start_slot_id: int | None = None,
    is_locked: bool = False,
) -> TimetableEntry:
    return create_timetable_entry(
        db,
        TimetableEntryCreate(
            timetable_run_id=context.run.id,
            course_session_id=(session or context.session).id,
            occurrence_number=occurrence_number,
            room_id=room_id or context.scheduling.room.id,
            start_slot_id=start_slot_id or context.slots[0].id,
            is_locked=is_locked,
            assignment_source=AssignmentSource.MANUAL,
        ),
    )


def complete_valid_manual_run(
    db: Session,
    context: TimetableContext,
    *,
    objective_score: Decimal = Decimal("0"),
) -> TimetableRun:
    start_timetable_run(db, context.run.id)
    return complete_timetable_run(
        db,
        context.run.id,
        status=TimetableRunStatus.SUCCEEDED,
        objective_score=objective_score,
        soft_penalty=Decimal("0"),
        execution_time_ms=1,
    )
