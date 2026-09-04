from decimal import Decimal

import pytest
from app.core.exceptions import (
    BusinessRuleError,
    DuplicateResourceError,
    InvalidReferenceError,
    ResourceInUseError,
)
from app.models.enums import CourseType
from app.schemas.curriculum_course import (
    CurriculumCourseCreate,
    CurriculumCourseUpdate,
)
from app.schemas.elective_group import ElectiveGroupUpdate
from app.services.academic.course import delete_course
from app.services.academic.curriculum_course import (
    create_curriculum_course,
    update_curriculum_course,
)
from app.services.academic.elective_group import update_elective_group
from sqlalchemy.orm import Session
from tests.services.academic.factories import (
    make_course,
    make_curriculum_course,
    make_elective_group,
    make_hierarchy,
)

pytestmark = pytest.mark.integration


def bypass_schema(**values: object) -> CurriculumCourseCreate:
    """Build invalid input to verify that the service repeats core rules."""

    return CurriculumCourseCreate.model_construct(**values)


def test_service_rejects_mandatory_course_with_elective_group(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(db)
    semester = hierarchy.semesters[0]
    group = make_elective_group(db, semester)
    course = make_course(db)

    payload = bypass_schema(
        program_semester_id=semester.id,
        course_id=course.id,
        course_type=CourseType.MANDATORY,
        elective_group_id=group.id,
        ects=Decimal("5.0"),
        requires_timetable=True,
        lecture_periods_per_week=2,
        numerical_periods_per_week=0,
        laboratory_periods_per_week=0,
        is_active=True,
    )

    with pytest.raises(BusinessRuleError, match="Mandatory courses"):
        create_curriculum_course(db, payload)


def test_service_rejects_elective_course_without_group(db: Session) -> None:
    hierarchy = make_hierarchy(db)
    semester = hierarchy.semesters[0]
    course = make_course(db)

    payload = bypass_schema(
        program_semester_id=semester.id,
        course_id=course.id,
        course_type=CourseType.ELECTIVE,
        elective_group_id=None,
        ects=Decimal("5.0"),
        requires_timetable=True,
        lecture_periods_per_week=2,
        numerical_periods_per_week=0,
        laboratory_periods_per_week=0,
        is_active=True,
    )

    with pytest.raises(BusinessRuleError, match="Elective courses"):
        create_curriculum_course(db, payload)


def test_elective_group_must_belong_to_same_semester(db: Session) -> None:
    hierarchy = make_hierarchy(db, created_semesters=(1, 2))
    first_semester, second_semester = hierarchy.semesters
    group = make_elective_group(db, first_semester)
    course = make_course(db)

    with pytest.raises(InvalidReferenceError) as exc_info:
        make_curriculum_course(
            db,
            second_semester,
            course,
            course_type=CourseType.ELECTIVE,
            elective_group=group,
        )

    assert exc_info.value.details["elective_group_program_semester_id"] == (first_semester.id)
    assert exc_info.value.details["curriculum_program_semester_id"] == (second_semester.id)


def test_active_elective_choices_in_group_require_equal_ects(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(db)
    semester = hierarchy.semesters[0]
    group = make_elective_group(db, semester)
    first_course = make_course(db)
    second_course = make_course(db)

    make_curriculum_course(
        db,
        semester,
        first_course,
        course_type=CourseType.ELECTIVE,
        elective_group=group,
        ects=Decimal("5.0"),
    )

    with pytest.raises(BusinessRuleError, match="equal ECTS"):
        make_curriculum_course(
            db,
            semester,
            second_course,
            course_type=CourseType.ELECTIVE,
            elective_group=group,
            ects=Decimal("6.0"),
        )


def test_curriculum_patch_validates_complete_merged_state(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(db)
    semester = hierarchy.semesters[0]
    group = make_elective_group(db, semester)
    course = make_course(db)
    curriculum_course = make_curriculum_course(
        db,
        semester,
        course,
        course_type=CourseType.ELECTIVE,
        elective_group=group,
    )

    # The PATCH does not mention elective_group_id. The service must merge the
    # stored group before validating the new mandatory course type.
    with pytest.raises(BusinessRuleError, match="Mandatory courses"):
        update_curriculum_course(
            db,
            curriculum_course.id,
            CurriculumCourseUpdate(course_type=CourseType.MANDATORY),
        )

    db.refresh(curriculum_course)
    assert curriculum_course.course_type == CourseType.ELECTIVE
    assert curriculum_course.elective_group_id == group.id


def test_timetabled_course_patch_cannot_reduce_merged_periods_to_zero(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(db)
    semester = hierarchy.semesters[0]
    course = make_course(db)
    curriculum_course = make_curriculum_course(
        db,
        semester,
        course,
        requires_timetable=True,
        lecture_periods_per_week=2,
        numerical_periods_per_week=0,
        laboratory_periods_per_week=0,
    )

    # Only one period field is supplied, so this specifically verifies merged
    # service-state validation rather than Pydantic request-only validation.
    with pytest.raises(BusinessRuleError, match="weekly teaching period"):
        update_curriculum_course(
            db,
            curriculum_course.id,
            CurriculumCourseUpdate(lecture_periods_per_week=0),
        )

    db.refresh(curriculum_course)
    assert curriculum_course.lecture_periods_per_week == 2


def test_non_timetabled_thesis_allows_zero_weekly_periods(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(db)
    semester = hierarchy.semesters[0]
    thesis = make_course(db)

    curriculum_course = make_curriculum_course(
        db,
        semester,
        thesis,
        ects=Decimal("30.0"),
        requires_timetable=False,
        lecture_periods_per_week=0,
        numerical_periods_per_week=0,
        laboratory_periods_per_week=0,
    )

    assert curriculum_course.requires_timetable is False
    assert curriculum_course.lecture_periods_per_week == 0
    assert curriculum_course.numerical_periods_per_week == 0
    assert curriculum_course.laboratory_periods_per_week == 0


def test_timetabled_course_still_rejects_zero_weekly_periods(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(db)
    semester = hierarchy.semesters[0]
    course = make_course(db)
    payload = bypass_schema(
        program_semester_id=semester.id,
        course_id=course.id,
        course_type=CourseType.MANDATORY,
        elective_group_id=None,
        ects=Decimal("5.0"),
        requires_timetable=True,
        lecture_periods_per_week=0,
        numerical_periods_per_week=0,
        laboratory_periods_per_week=0,
        is_active=True,
    )

    with pytest.raises(BusinessRuleError, match="weekly teaching period"):
        create_curriculum_course(db, payload)


def test_duplicate_course_in_same_semester_is_explicit(db: Session) -> None:
    hierarchy = make_hierarchy(db)
    semester = hierarchy.semesters[0]
    course = make_course(db)
    make_curriculum_course(db, semester, course)

    with pytest.raises(DuplicateResourceError) as exc_info:
        make_curriculum_course(db, semester, course)

    assert exc_info.value.details["fields"] == [
        "program_semester_id",
        "course_id",
    ]


def test_elective_group_cannot_move_away_from_existing_courses(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(db, created_semesters=(1, 2))
    first_semester, second_semester = hierarchy.semesters
    group = make_elective_group(db, first_semester)
    course = make_course(db)
    make_curriculum_course(
        db,
        first_semester,
        course,
        course_type=CourseType.ELECTIVE,
        elective_group=group,
    )

    with pytest.raises(BusinessRuleError, match="cannot be moved"):
        update_elective_group(
            db,
            group.id,
            ElectiveGroupUpdate(program_semester_id=second_semester.id),
        )

    db.refresh(group)
    assert group.program_semester_id == first_semester.id


def test_course_cannot_deactivate_while_active_curriculum_uses_it(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(db)
    semester = hierarchy.semesters[0]
    course = make_course(db)
    curriculum_course = make_curriculum_course(db, semester, course)

    with pytest.raises(ResourceInUseError) as exc_info:
        delete_course(db, course.id)

    assert exc_info.value.details["curriculum_course_id"] == curriculum_course.id
    db.refresh(course)
    assert course.is_active is True
