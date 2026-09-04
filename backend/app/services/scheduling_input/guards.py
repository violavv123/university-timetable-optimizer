from app.core.exceptions import ResourceInUseError
from app.models.course_offering import CourseOffering
from app.models.course_session import CourseSession
from app.models.enums import CourseOfferingStatus
from app.models.timetable_entry import TimetableEntry
from app.services.common import require_active, require_by_id
from sqlalchemy import select
from sqlalchemy.orm import Session


def require_editable_session(
    db: Session,
    course_session_id: int,
) -> CourseSession:
    session = require_by_id(
        db,
        CourseSession,
        course_session_id,
        "Course session",
    )
    require_active(session, "Course session")
    offering = require_by_id(
        db,
        CourseOffering,
        session.course_offering_id,
        "Course offering",
    )
    if offering.status != CourseOfferingStatus.DRAFT:
        raise ResourceInUseError(
            "Session inputs can only be changed while the offering is DRAFT.",
            details={
                "course_session_id": session.id,
                "course_offering_id": offering.id,
                "course_offering_status": offering.status,
            },
        )
    timetable_entry_id = db.scalar(
        select(TimetableEntry.id).where(TimetableEntry.course_session_id == session.id).limit(1)
    )
    if timetable_entry_id is not None:
        raise ResourceInUseError(
            "Session inputs cannot change after timetable entries exist.",
            details={
                "course_session_id": session.id,
                "timetable_entry_id": timetable_entry_id,
            },
        )
    return session
