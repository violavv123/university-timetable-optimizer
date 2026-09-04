from datetime import time

import pytest
from app.core.exceptions import BusinessRuleError
from app.models.enums import (
    AvailabilityType,
    DayOfWeek,
    RoomStatus,
)
from app.schemas.room_availability import RoomAvailabilityCreate
from app.schemas.staff_availability import (
    StaffAvailabilityCreate,
    StaffAvailabilityUpdate,
)
from app.services.resources.room_availability import create_room_availability
from app.services.resources.staff_availability import (
    create_staff_availability,
    update_staff_availability,
)
from sqlalchemy.orm import Session
from tests.services.resources.factories import (
    make_resource_context,
    make_room,
    make_room_availability,
    make_staff_availability,
    make_staff_member,
)

pytestmark = pytest.mark.integration


def test_preferred_availability_requires_a_nonnegative_weight(
    db: Session,
) -> None:
    context = make_resource_context(db)
    staff = make_staff_member(db, context.hierarchy.faculty.id)
    missing_weight = StaffAvailabilityCreate.model_construct(
        staff_member_id=staff.id,
        academic_term_id=context.academic_term.id,
        day_of_week=DayOfWeek.MONDAY,
        start_time=time(17, 0),
        end_time=time(20, 0),
        availability_type=AvailabilityType.PREFERRED,
        preference_weight=None,
    )

    with pytest.raises(BusinessRuleError, match="require preference_weight"):
        create_staff_availability(db, missing_weight)

    negative_weight = StaffAvailabilityCreate.model_construct(
        staff_member_id=staff.id,
        academic_term_id=context.academic_term.id,
        day_of_week=DayOfWeek.MONDAY,
        start_time=time(17, 0),
        end_time=time(20, 0),
        availability_type=AvailabilityType.PREFERRED,
        preference_weight=-1,
    )
    with pytest.raises(BusinessRuleError, match="cannot be negative"):
        create_staff_availability(db, negative_weight)


def test_hard_availability_must_not_have_a_preference_weight(
    db: Session,
) -> None:
    context = make_resource_context(db)
    staff = make_staff_member(db, context.hierarchy.faculty.id)
    payload = StaffAvailabilityCreate.model_construct(
        staff_member_id=staff.id,
        academic_term_id=context.academic_term.id,
        day_of_week=DayOfWeek.MONDAY,
        start_time=time(9, 0),
        end_time=time(11, 0),
        availability_type=AvailabilityType.UNAVAILABLE,
        preference_weight=2,
    )

    with pytest.raises(BusinessRuleError, match="must not have"):
        create_staff_availability(db, payload)


def test_staff_windows_may_touch_but_may_not_overlap(db: Session) -> None:
    context = make_resource_context(db)
    staff = make_staff_member(db, context.hierarchy.faculty.id)
    make_staff_availability(
        db,
        staff,
        context.academic_term,
        start_time=time(9, 0),
        end_time=time(10, 0),
    )
    touching = make_staff_availability(
        db,
        staff,
        context.academic_term,
        start_time=time(10, 0),
        end_time=time(11, 0),
    )
    assert touching.id > 0

    with pytest.raises(BusinessRuleError, match="cannot overlap"):
        make_staff_availability(
            db,
            staff,
            context.academic_term,
            start_time=time(9, 30),
            end_time=time(10, 30),
            availability_type=AvailabilityType.AVOID,
            preference_weight=1,
        )


def test_availability_patch_validates_the_complete_merged_window(
    db: Session,
) -> None:
    context = make_resource_context(db)
    staff = make_staff_member(db, context.hierarchy.faculty.id)
    availability = make_staff_availability(
        db,
        staff,
        context.academic_term,
        start_time=time(9, 0),
        end_time=time(11, 0),
    )
    invalid_patch = StaffAvailabilityUpdate.model_construct(start_time=time(11, 0))

    with pytest.raises(BusinessRuleError, match="after start_time"):
        update_staff_availability(db, availability.id, invalid_patch)

    db.refresh(availability)
    assert availability.start_time == time(9, 0)
    assert availability.end_time == time(11, 0)


def test_room_availability_requires_an_active_room(db: Session) -> None:
    context = make_resource_context(db)
    room = make_room(
        db,
        context.hierarchy.faculty.id,
        status=RoomStatus.MAINTENANCE,
    )
    payload = RoomAvailabilityCreate(
        room_id=room.id,
        academic_term_id=context.academic_term.id,
        day_of_week=DayOfWeek.MONDAY,
        start_time=time(9, 0),
        end_time=time(11, 0),
        availability_type=AvailabilityType.UNAVAILABLE,
        preference_weight=None,
    )

    with pytest.raises(BusinessRuleError, match="active room"):
        create_room_availability(db, payload)


def test_room_availability_windows_cannot_overlap(db: Session) -> None:
    context = make_resource_context(db)
    room = make_room(db, context.hierarchy.faculty.id)
    make_room_availability(
        db,
        room,
        context.academic_term,
        start_time=time(8, 0),
        end_time=time(12, 0),
    )

    with pytest.raises(BusinessRuleError, match="cannot overlap"):
        make_room_availability(
            db,
            room,
            context.academic_term,
            start_time=time(11, 0),
            end_time=time(13, 0),
            availability_type=AvailabilityType.UNAVAILABLE,
        )
