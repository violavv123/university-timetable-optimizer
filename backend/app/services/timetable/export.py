import csv
from io import StringIO

from app.core.exceptions import TimetablePublishError
from app.models.enums import DayOfWeek, TimetableRunStatus
from app.models.time_slot import TimeSlot
from app.models.timetable_entry import TimetableEntry
from app.services.timetable.timetable_run import get_timetable_run
from app.services.timetable.validation import validate_timetable_run
from sqlalchemy import select
from sqlalchemy.orm import Session


def export_published_timetable_csv(
    db: Session,
    timetable_run_id: int,
) -> tuple[str, str]:
    run = get_timetable_run(db, timetable_run_id)

    if (
        run.status != TimetableRunStatus.SUCCEEDED
        or not run.is_published
    ):
        raise TimetablePublishError(
            "Only a successful published timetable can be downloaded."
        )

    validation = validate_timetable_run(db, run.id)
    if not validation.is_valid:
        raise TimetablePublishError(
            "A timetable with hard conflicts cannot be downloaded.",
            details={
                "timetable_run_id": run.id,
                "hard_conflicts": validation.hard_conflict_count,
            },
        )

    entries = tuple(
        db.scalars(
            select(TimetableEntry)
            .join(TimeSlot, TimeSlot.id == TimetableEntry.start_slot_id)
            .where(TimetableEntry.timetable_run_id == run.id)
            .order_by(
                TimeSlot.day_of_week,
                TimeSlot.slot_index,
                TimetableEntry.id,
            )
        ).all()
    )

    slots = tuple(
        db.scalars(
            select(TimeSlot).where(
                TimeSlot.scheduling_profile_id
                == run.scheduling_profile_id
            )
        ).all()
    )
    slot_by_position = {
        (slot.day_of_week, slot.slot_index): slot
        for slot in slots
    }

    output = StringIO(newline="")
    writer = csv.writer(output)

    writer.writerow(
        [
            "Course code",
            "Course name",
            "Session",
            "Component",
            "Occurrence",
            "Day",
            "Start time",
            "End time",
            "Room",
            "Student groups",
            "Staff",
        ]
    )

    for entry in entries:
        session = entry.course_session
        course = session.course_offering.curriculum_course.course
        start_slot = entry.start_slot
        end_slot = slot_by_position[
            (
                start_slot.day_of_week,
                start_slot.slot_index + session.duration_slots - 1,
            )
        ]

        groups = ", ".join(
            assignment.student_group.name
            for assignment in session.group_assignments
        )
        staff = ", ".join(
            (
                f"{assignment.staff_member.first_name} "
                f"{assignment.staff_member.last_name}"
            )
            for assignment in session.staff_assignments
        )

        writer.writerow(
            [
                course.code,
                course.name,
                session.name,
                session.component_type.value,
                entry.occurrence_number,
                DayOfWeek(start_slot.day_of_week).name.title(),
                start_slot.start_time.isoformat(timespec="minutes"),
                end_slot.end_time.isoformat(timespec="minutes"),
                entry.room.code,
                groups,
                staff,
            ]
        )

    filename = f"timetable-run-{run.id}.csv"
    return filename, output.getvalue()