from decimal import Decimal

import pytest
from app.core.exceptions import BusinessRuleError
from app.models.enums import CourseType
from app.services.academic.curriculum_validation import (
    get_curriculum_validation_report,
    validate_study_program_curriculum,
)
from sqlalchemy.orm import Session
from tests.services.academic.factories import (
    make_course,
    make_curriculum_course,
    make_elective_group,
    make_hierarchy,
)

pytestmark = pytest.mark.integration


def issue_codes(issues: list[dict[str, object]]) -> set[str]:
    return {str(issue["code"]) for issue in issues}


def test_complete_30_ects_semester_is_valid(db: Session) -> None:
    hierarchy = make_hierarchy(
        db,
        semester_count=1,
        created_semesters=(1,),
    )
    semester = hierarchy.semesters[0]
    course = make_course(db)
    make_curriculum_course(
        db,
        semester,
        course,
        ects=Decimal("30.0"),
    )

    report = validate_study_program_curriculum(
        db,
        hierarchy.study_program.id,
    )

    assert report["is_valid"] is True
    assert report["semester_totals"] == {1: Decimal("30.0")}
    assert report["errors"] == []


def test_missing_semester_and_wrong_ects_are_reported(db: Session) -> None:
    hierarchy = make_hierarchy(
        db,
        semester_count=2,
        created_semesters=(1,),
    )
    semester = hierarchy.semesters[0]
    course = make_course(db)
    make_curriculum_course(
        db,
        semester,
        course,
        ects=Decimal("5.0"),
    )

    report = get_curriculum_validation_report(
        db,
        hierarchy.study_program.id,
    )

    assert report["is_valid"] is False
    assert issue_codes(report["errors"]) >= {
        "missing_program_semester",
        "invalid_semester_ects",
    }

    with pytest.raises(BusinessRuleError) as exc_info:
        validate_study_program_curriculum(
            db,
            hierarchy.study_program.id,
        )

    assert exc_info.value.details["is_valid"] is False


def test_elective_options_count_once_per_required_choice(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(
        db,
        semester_count=1,
        created_semesters=(1,),
    )
    semester = hierarchy.semesters[0]
    mandatory = make_course(db)
    option_one = make_course(db)
    option_two = make_course(db)
    group = make_elective_group(db, semester, required_choices=1)

    make_curriculum_course(
        db,
        semester,
        mandatory,
        ects=Decimal("25.0"),
    )
    make_curriculum_course(
        db,
        semester,
        option_one,
        course_type=CourseType.ELECTIVE,
        elective_group=group,
        ects=Decimal("5.0"),
    )
    make_curriculum_course(
        db,
        semester,
        option_two,
        course_type=CourseType.ELECTIVE,
        elective_group=group,
        ects=Decimal("5.0"),
    )

    report = get_curriculum_validation_report(
        db,
        hierarchy.study_program.id,
    )

    assert report["is_valid"] is True
    assert report["semester_totals"] == {1: Decimal("30.0")}


def test_insufficient_elective_options_are_reported(db: Session) -> None:
    hierarchy = make_hierarchy(
        db,
        semester_count=1,
        created_semesters=(1,),
    )
    semester = hierarchy.semesters[0]
    group = make_elective_group(db, semester, required_choices=2)
    option = make_course(db)
    make_curriculum_course(
        db,
        semester,
        option,
        course_type=CourseType.ELECTIVE,
        elective_group=group,
        ects=Decimal("5.0"),
    )

    report = get_curriculum_validation_report(
        db,
        hierarchy.study_program.id,
    )

    assert "insufficient_elective_choices" in issue_codes(report["errors"])


def test_non_timetabled_thesis_counts_ects_without_period_warning(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(
        db,
        semester_count=1,
        created_semesters=(1,),
    )
    semester = hierarchy.semesters[0]
    thesis = make_course(db)
    make_curriculum_course(
        db,
        semester,
        thesis,
        ects=Decimal("30.0"),
        requires_timetable=False,
        lecture_periods_per_week=0,
        numerical_periods_per_week=0,
        laboratory_periods_per_week=0,
    )

    report = get_curriculum_validation_report(
        db,
        hierarchy.study_program.id,
    )

    assert report["is_valid"] is True
    assert report["semester_totals"] == {1: Decimal("30.0")}
    assert "no_weekly_periods" not in issue_codes(report["warnings"])


def test_non_timetabled_course_with_periods_is_reported_as_warning(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(
        db,
        semester_count=1,
        created_semesters=(1,),
    )
    semester = hierarchy.semesters[0]
    course = make_course(db)
    curriculum_course = make_curriculum_course(
        db,
        semester,
        course,
        ects=Decimal("30.0"),
        requires_timetable=False,
        lecture_periods_per_week=2,
    )

    report = get_curriculum_validation_report(
        db,
        hierarchy.study_program.id,
    )

    assert report["is_valid"] is True
    assert any(
        warning.get("details", {}).get("curriculum_course_id") == curriculum_course.id
        and "period" in str(warning.get("message", "")).lower()
        for warning in report["warnings"]
    )
