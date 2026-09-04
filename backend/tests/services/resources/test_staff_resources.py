import pytest
from app.core.exceptions import (
    BusinessRuleError,
    DuplicateResourceError,
    InactiveResourceError,
    ResourceInUseError,
)
from app.schemas.staff_course import StaffCourseCreate, StaffCourseUpdate
from app.schemas.staff_member import StaffMemberCreate
from app.services.resources.staff_course import (
    create_staff_course,
    update_staff_course,
)
from app.services.resources.staff_member import (
    create_staff_member,
    delete_staff_member,
)
from sqlalchemy.orm import Session
from tests.services.resources.factories import (
    make_resource_context,
    make_staff_course,
    make_staff_member,
)

pytestmark = pytest.mark.integration


def test_staff_email_is_normalized_and_case_insensitive_unique(
    db: Session,
) -> None:
    context = make_resource_context(db)
    faculty_id = context.hierarchy.faculty.id
    first = make_staff_member(
        db,
        faculty_id,
        email="  Lecturer.One@Example.Test  ",
    )

    assert first.email == "lecturer.one@example.test"

    duplicate_payload = StaffMemberCreate(
        faculty_id=faculty_id,
        first_name="Another",
        last_name="Lecturer",
        email="LECTURER.ONE@EXAMPLE.TEST",
        academic_title=first.academic_title,
        staff_type=first.staff_type,
        is_active=True,
    )
    with pytest.raises(DuplicateResourceError):
        create_staff_member(db, duplicate_payload)


def test_active_qualification_requires_active_staff(db: Session) -> None:
    context = make_resource_context(db)
    inactive_staff = make_staff_member(
        db,
        context.hierarchy.faculty.id,
        is_active=False,
    )

    with pytest.raises(InactiveResourceError):
        make_staff_course(db, inactive_staff, context.course)


def test_qualification_must_allow_lecture_or_assistance(
    db: Session,
) -> None:
    context = make_resource_context(db)
    staff = make_staff_member(db, context.hierarchy.faculty.id)
    payload = StaffCourseCreate.model_construct(
        staff_member_id=staff.id,
        course_id=context.course.id,
        can_lecture=False,
        can_assist=False,
        is_active=True,
    )

    with pytest.raises(BusinessRuleError, match="lecturing, assisting"):
        create_staff_course(db, payload)


def test_duplicate_staff_course_qualification_is_rejected(
    db: Session,
) -> None:
    context = make_resource_context(db)
    staff = make_staff_member(db, context.hierarchy.faculty.id)
    make_staff_course(db, staff, context.course)

    with pytest.raises(DuplicateResourceError) as exc_info:
        make_staff_course(db, staff, context.course)

    assert exc_info.value.details["fields"] == [
        "staff_member_id",
        "course_id",
    ]


def test_staff_course_patch_validates_the_merged_capabilities(
    db: Session,
) -> None:
    context = make_resource_context(db)
    staff = make_staff_member(db, context.hierarchy.faculty.id)
    qualification = make_staff_course(
        db,
        staff,
        context.course,
        can_lecture=True,
        can_assist=True,
    )

    updated = update_staff_course(
        db,
        qualification.id,
        StaffCourseUpdate(can_lecture=False),
    )
    assert updated.can_assist is True

    with pytest.raises(BusinessRuleError, match="lecturing, assisting"):
        update_staff_course(
            db,
            qualification.id,
            StaffCourseUpdate(can_assist=False),
        )


def test_staff_member_with_active_qualification_cannot_deactivate(
    db: Session,
) -> None:
    context = make_resource_context(db)
    staff = make_staff_member(db, context.hierarchy.faculty.id)
    qualification = make_staff_course(db, staff, context.course)

    with pytest.raises(ResourceInUseError) as exc_info:
        delete_staff_member(db, staff.id)

    assert exc_info.value.details["staff_course_id"] == qualification.id
    db.refresh(staff)
    assert staff.is_active is True
