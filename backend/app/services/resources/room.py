from app.core.exceptions import BusinessRuleError, ResourceInUseError
from app.models.course_offering import CourseOffering
from app.models.course_session import CourseSession
from app.models.course_session_group import CourseSessionGroup
from app.models.enums import (
    ComponentType,
    CourseOfferingStatus,
    RoomStatus,
    RoomType,
)
from app.models.faculty import Faculty
from app.models.program_room_preference import ProgramRoomPreference
from app.models.room import Room
from app.models.student_group import StudentGroup
from app.models.timetable_entry import TimetableEntry
from app.models.timetable_run import TimetableRun
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.room import RoomCreate, RoomRead, RoomUpdate
from app.services.common import (
    apply_changes,
    commit_and_refresh,
    ensure_unique,
    normalize_code,
    paginated_rows,
    require_active,
    require_by_id,
    validated_changes,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _validate_faculty_and_capacity(
    db: Session,
    *,
    faculty_id: int,
    capacity: int,
    status: RoomStatus,
) -> None:
    if capacity <= 0:
        raise BusinessRuleError("capacity must be greater than zero.")
    faculty = require_by_id(db, Faculty, faculty_id, "Faculty")
    if status != RoomStatus.INACTIVE:
        require_active(faculty, "Faculty")


def _required_student_count(db: Session, course_session_id: int) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(StudentGroup.student_count), 0))
            .select_from(CourseSessionGroup)
            .join(
                StudentGroup,
                StudentGroup.id == CourseSessionGroup.student_group_id,
            )
            .where(
                CourseSessionGroup.course_session_id == course_session_id,
                StudentGroup.is_active.is_(True),
            )
        )
        or 0
    )


def _validate_exact_room_requirements(
    db: Session,
    *,
    room_id: int,
    capacity: int,
    room_type: RoomType,
    status: RoomStatus,
) -> None:
    statement = (
        select(CourseSession)
        .join(
            CourseOffering,
            CourseOffering.id == CourseSession.course_offering_id,
        )
        .where(
            CourseSession.required_room_id == room_id,
            CourseSession.is_active.is_(True),
            CourseOffering.status.in_([CourseOfferingStatus.DRAFT, CourseOfferingStatus.READY]),
        )
    )
    for session in db.scalars(statement).all():
        if status != RoomStatus.ACTIVE:
            raise ResourceInUseError(
                "A room required by an open course session must remain active.",
                details={"room_id": room_id, "course_session_id": session.id},
            )
        if session.component_type == ComponentType.LABORATORY and room_type != RoomType.LABORATORY:
            raise BusinessRuleError(
                "A laboratory session's required room must be a laboratory.",
                details={"room_id": room_id, "course_session_id": session.id},
            )
        if session.required_room_type is not None and session.required_room_type != room_type:
            raise BusinessRuleError(
                "room_type does not satisfy an open session's required room type.",
                details={
                    "room_id": room_id,
                    "course_session_id": session.id,
                    "required_room_type": session.required_room_type,
                },
            )

        student_count = _required_student_count(db, session.id)
        if student_count > capacity:
            raise BusinessRuleError(
                "Room capacity is smaller than the active groups assigned to a required session.",
                details={
                    "room_id": room_id,
                    "course_session_id": session.id,
                    "required_capacity": student_count,
                    "room_capacity": capacity,
                },
            )


def _ensure_published_assignments_remain_valid(
    db: Session,
    *,
    room_id: int,
    capacity: int,
    status: RoomStatus,
) -> None:
    statement = (
        select(TimetableEntry.course_session_id)
        .join(
            TimetableRun,
            TimetableRun.id == TimetableEntry.timetable_run_id,
        )
        .where(
            TimetableEntry.room_id == room_id,
            TimetableRun.is_published.is_(True),
        )
        .distinct()
    )
    for course_session_id in db.scalars(statement).all():
        if status != RoomStatus.ACTIVE:
            raise ResourceInUseError(
                "A room used by a published timetable must remain active.",
                details={
                    "room_id": room_id,
                    "course_session_id": course_session_id,
                },
            )
        student_count = _required_student_count(db, course_session_id)
        if student_count > capacity:
            raise BusinessRuleError(
                "Room capacity cannot be reduced below a published assignment's group size.",
                details={
                    "room_id": room_id,
                    "course_session_id": course_session_id,
                    "required_capacity": student_count,
                    "room_capacity": capacity,
                },
            )


def _ensure_preferences_remain_valid(
    db: Session,
    *,
    room_id: int,
    faculty_id: int,
    status: RoomStatus,
) -> None:
    preference = db.scalar(
        select(ProgramRoomPreference)
        .where(
            ProgramRoomPreference.room_id == room_id,
            ProgramRoomPreference.is_active.is_(True),
        )
        .limit(1)
    )
    if preference is None:
        return
    if status != RoomStatus.ACTIVE:
        raise ResourceInUseError(
            "A preferred room must remain active.",
            details={
                "room_id": room_id,
                "program_room_preference_id": preference.id,
            },
        )
    if preference.study_program.faculty_id != faculty_id:
        raise ResourceInUseError(
            "A room with an active same-faculty preference cannot change faculty.",
            details={
                "room_id": room_id,
                "program_room_preference_id": preference.id,
            },
        )


def get_room(db: Session, room_id: int) -> Room:
    return require_by_id(db, Room, room_id, "Room")


def list_rooms(
    db: Session,
    pagination: PaginationParams,
    *,
    faculty_id: int | None = None,
    room_type: RoomType | None = None,
    status: RoomStatus | None = None,
    include_unavailable: bool = False,
) -> PaginatedResponse[RoomRead]:
    filters = []
    if faculty_id is not None:
        require_by_id(db, Faculty, faculty_id, "Faculty")
        filters.append(Room.faculty_id == faculty_id)
    if room_type is not None:
        filters.append(Room.room_type == room_type)
    if status is not None:
        filters.append(Room.status == status)
    elif not include_unavailable:
        filters.append(Room.status == RoomStatus.ACTIVE)

    statement = select(Room).where(*filters).order_by(Room.faculty_id, Room.code)
    count_statement = select(func.count()).select_from(Room).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[RoomRead](
        items=[RoomRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_room(db: Session, payload: RoomCreate) -> Room:
    _validate_faculty_and_capacity(
        db,
        faculty_id=payload.faculty_id,
        capacity=payload.capacity,
        status=payload.status,
    )
    values = payload.model_dump()
    values["code"] = normalize_code(payload.code)
    values["name"] = " ".join(payload.name.split())
    if not values["name"]:
        raise BusinessRuleError("name cannot be blank.")
    ensure_unique(
        db,
        Room,
        "Room",
        ["faculty_id", "code"],
        Room.faculty_id == payload.faculty_id,
        func.upper(Room.code) == values["code"],
    )

    room = Room(**values)
    db.add(room)
    return commit_and_refresh(db, room)


def update_room(
    db: Session,
    room_id: int,
    payload: RoomUpdate,
) -> Room:
    room = get_room(db, room_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "faculty_id",
            "code",
            "name",
            "capacity",
            "room_type",
            "status",
        ),
    )
    faculty_id = changes.get("faculty_id", room.faculty_id)
    capacity = changes.get("capacity", room.capacity)
    room_type = changes.get("room_type", room.room_type)
    status = changes.get("status", room.status)
    if "code" in changes:
        changes["code"] = normalize_code(changes["code"])
    if "name" in changes:
        changes["name"] = " ".join(changes["name"].split())
        if not changes["name"]:
            raise BusinessRuleError("name cannot be blank.")
    code = changes.get("code", room.code)

    _validate_faculty_and_capacity(
        db,
        faculty_id=faculty_id,
        capacity=capacity,
        status=status,
    )
    ensure_unique(
        db,
        Room,
        "Room",
        ["faculty_id", "code"],
        Room.faculty_id == faculty_id,
        func.upper(Room.code) == code,
        exclude_id=room.id,
    )
    _validate_exact_room_requirements(
        db,
        room_id=room.id,
        capacity=capacity,
        room_type=room_type,
        status=status,
    )
    _ensure_published_assignments_remain_valid(
        db,
        room_id=room.id,
        capacity=capacity,
        status=status,
    )
    _ensure_preferences_remain_valid(
        db,
        room_id=room.id,
        faculty_id=faculty_id,
        status=status,
    )

    apply_changes(room, changes)
    return commit_and_refresh(db, room)


def delete_room(db: Session, room_id: int) -> MessageResponse:
    room = get_room(db, room_id)
    _validate_exact_room_requirements(
        db,
        room_id=room.id,
        capacity=room.capacity,
        room_type=room.room_type,
        status=RoomStatus.INACTIVE,
    )
    _ensure_published_assignments_remain_valid(
        db,
        room_id=room.id,
        capacity=room.capacity,
        status=RoomStatus.INACTIVE,
    )
    _ensure_preferences_remain_valid(
        db,
        room_id=room.id,
        faculty_id=room.faculty_id,
        status=RoomStatus.INACTIVE,
    )
    room.status = RoomStatus.INACTIVE
    commit_and_refresh(db, room)
    return MessageResponse(message="Room deactivated successfully.")
