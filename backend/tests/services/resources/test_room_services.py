import pytest
from app.core.exceptions import (
    BusinessRuleError,
    DuplicateResourceError,
    InvalidReferenceError,
    ResourceInUseError,
)
from app.models.enums import RoomStatus, RoomType
from app.schemas.program_room_preference import ProgramRoomPreferenceCreate
from app.schemas.room import RoomCreate
from app.services.resources.program_room_preference import (
    create_program_room_preference,
)
from app.services.resources.room import create_room, delete_room
from sqlalchemy.orm import Session
from tests.services.academic.factories import make_hierarchy, unique_code
from tests.services.resources.factories import (
    make_program_room_preference,
    make_resource_context,
    make_room,
)

pytestmark = pytest.mark.integration


def test_room_capacity_must_be_positive_even_if_schema_is_bypassed(
    db: Session,
) -> None:
    context = make_resource_context(db)
    payload = RoomCreate.model_construct(
        faculty_id=context.hierarchy.faculty.id,
        code=unique_code("ROOM"),
        name="Invalid room",
        capacity=0,
        room_type=RoomType.GENERAL_ROOM,
        status=RoomStatus.ACTIVE,
    )

    with pytest.raises(BusinessRuleError, match="greater than zero"):
        create_room(db, payload)


def test_room_code_is_normalized_and_unique_per_faculty(
    db: Session,
) -> None:
    context = make_resource_context(db)
    faculty_id = context.hierarchy.faculty.id
    first = make_room(db, faculty_id, code="  lab-615  ")

    assert first.code == "LAB-615"

    with pytest.raises(DuplicateResourceError):
        make_room(db, faculty_id, code="Lab-615")


def test_same_room_code_is_allowed_in_a_different_faculty(
    db: Session,
) -> None:
    first_context = make_resource_context(db)
    second_hierarchy = make_hierarchy(db, created_semesters=())
    first = make_room(
        db,
        first_context.hierarchy.faculty.id,
        code="A-101",
    )
    second = make_room(
        db,
        second_hierarchy.faculty.id,
        code="A-101",
    )

    assert first.faculty_id != second.faculty_id
    assert first.code == second.code


def test_room_preference_requires_same_faculty(db: Session) -> None:
    context = make_resource_context(db)
    other_hierarchy = make_hierarchy(db, created_semesters=())
    other_room = make_room(db, other_hierarchy.faculty.id)
    payload = ProgramRoomPreferenceCreate(
        study_program_id=context.hierarchy.study_program.id,
        room_id=other_room.id,
        penalty_weight=2,
        is_active=True,
    )

    with pytest.raises(InvalidReferenceError, match="program's faculty"):
        create_program_room_preference(db, payload)


def test_active_room_preference_requires_active_room(db: Session) -> None:
    context = make_resource_context(db)
    inactive_room = make_room(
        db,
        context.hierarchy.faculty.id,
        status=RoomStatus.INACTIVE,
    )
    payload = ProgramRoomPreferenceCreate(
        study_program_id=context.hierarchy.study_program.id,
        room_id=inactive_room.id,
        penalty_weight=1,
        is_active=True,
    )

    with pytest.raises(BusinessRuleError, match="active room"):
        create_program_room_preference(db, payload)


def test_room_preference_penalty_cannot_be_negative(db: Session) -> None:
    context = make_resource_context(db)
    room = make_room(db, context.hierarchy.faculty.id)
    payload = ProgramRoomPreferenceCreate.model_construct(
        study_program_id=context.hierarchy.study_program.id,
        room_id=room.id,
        penalty_weight=-1,
        is_active=True,
    )

    with pytest.raises(BusinessRuleError, match="cannot be negative"):
        create_program_room_preference(db, payload)


def test_room_with_active_program_preference_cannot_deactivate(
    db: Session,
) -> None:
    context = make_resource_context(db)
    room = make_room(db, context.hierarchy.faculty.id)
    preference = make_program_room_preference(db, context, room)

    with pytest.raises(ResourceInUseError) as exc_info:
        delete_room(db, room.id)

    assert exc_info.value.details["program_room_preference_id"] == preference.id
    db.refresh(room)
    assert room.status == RoomStatus.ACTIVE
