from datetime import time

import pytest
from app.core.exceptions import (
    BusinessRuleError,
    DuplicateResourceError,
    ResourceInUseError,
)
from app.models.enums import DayOfWeek
from app.schemas.scheduling_profile import (
    SchedulingProfileCreate,
    SchedulingProfileUpdate,
)
from app.schemas.time_slot import TimeSlotCreate
from app.services.scheduling_input.scheduling_profile import (
    create_scheduling_profile,
    delete_scheduling_profile,
    update_scheduling_profile,
)
from app.services.scheduling_input.time_slot import create_time_slot
from sqlalchemy.orm import Session
from tests.services.academic.factories import make_faculty
from tests.services.scheduling_input.factories import (
    make_scheduling_profile,
    make_time_slot,
)

pytestmark = pytest.mark.integration


def test_profile_requires_positive_capacities_and_nonnegative_weights(
    db: Session,
) -> None:
    faculty = make_faculty(db)
    payload = SchedulingProfileCreate.model_construct(
        faculty_id=faculty.id,
        name="Invalid profile",
        slot_minutes=0,
        max_lecture_students=80,
        max_numerical_students=40,
        max_lab_students=30,
        preferred_room_weight=1,
        historical_room_weight=1,
        student_gap_weight=1,
        staff_gap_weight=1,
        late_hour_weight=1,
        is_active=True,
    )

    with pytest.raises(BusinessRuleError, match="greater than zero"):
        create_scheduling_profile(db, payload)


def test_profile_name_is_normalized_and_case_insensitive_unique(
    db: Session,
) -> None:
    faculty = make_faculty(db)
    profile = make_scheduling_profile(
        db,
        faculty.id,
        name="  Standard   Profile  ",
    )

    assert profile.name == "Standard Profile"
    with pytest.raises(DuplicateResourceError):
        make_scheduling_profile(db, faculty.id, name="standard profile")


def test_slot_duration_must_equal_profile_slot_minutes(db: Session) -> None:
    faculty = make_faculty(db)
    profile = make_scheduling_profile(db, faculty.id, slot_minutes=45)
    payload = TimeSlotCreate(
        scheduling_profile_id=profile.id,
        day_of_week=DayOfWeek.MONDAY,
        slot_index=0,
        start_time=time(8, 0),
        end_time=time(9, 0),
        is_active=True,
    )

    with pytest.raises(BusinessRuleError, match="slot_minutes"):
        create_time_slot(db, payload)


def test_slots_may_touch_but_cannot_overlap_or_break_index_order(
    db: Session,
) -> None:
    faculty = make_faculty(db)
    profile = make_scheduling_profile(db, faculty.id)
    make_time_slot(db, profile)
    touching = make_time_slot(
        db,
        profile,
        slot_index=1,
        start_time=time(8, 45),
        end_time=time(9, 30),
    )

    assert touching.slot_index == 1
    with pytest.raises(BusinessRuleError, match="cannot overlap"):
        make_time_slot(
            db,
            profile,
            slot_index=2,
            start_time=time(9, 15),
            end_time=time(10, 0),
        )

    with pytest.raises(BusinessRuleError, match="chronological"):
        make_time_slot(
            db,
            profile,
            slot_index=3,
            start_time=time(7, 15),
            end_time=time(8, 0),
        )


def test_profile_slot_size_is_immutable_after_slots_exist(db: Session) -> None:
    faculty = make_faculty(db)
    profile = make_scheduling_profile(db, faculty.id)
    make_time_slot(db, profile)

    with pytest.raises(ResourceInUseError, match="with time slots"):
        update_scheduling_profile(
            db,
            profile.id,
            SchedulingProfileUpdate(slot_minutes=60),
        )


def test_profile_with_active_slots_cannot_be_deactivated(db: Session) -> None:
    faculty = make_faculty(db)
    profile = make_scheduling_profile(db, faculty.id)
    slot = make_time_slot(db, profile)

    with pytest.raises(ResourceInUseError) as exc_info:
        delete_scheduling_profile(db, profile.id)

    assert exc_info.value.details["time_slot_id"] == slot.id
    db.refresh(profile)
    assert profile.is_active is True
