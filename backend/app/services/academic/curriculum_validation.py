from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.models.curriculum_course import CurriculumCourse
from app.models.elective_group import ElectiveGroup
from app.models.enums import CourseType
from app.models.program_semester import ProgramSemester
from app.models.study_program import StudyProgram
from app.services.academic._common import require_by_id
from app.services.academic._hierarchy import (
    require_active_study_program_hierarchy,
)


DEFAULT_SEMESTER_ECTS = Decimal("30.0")


def _issue(
    code: str,
    message: str,
    **details: Any,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "details": details,
    }


def get_curriculum_validation_report(
    db: Session,
    study_program_id: int,
    *,
    expected_ects_per_semester: Decimal = DEFAULT_SEMESTER_ECTS,
) -> dict[str, Any]:
    study_program = require_by_id(
        db,
        StudyProgram,
        study_program_id,
        "Study program",
    )
    require_active_study_program_hierarchy(study_program)

    semesters = list(
        db.scalars(
            select(ProgramSemester)
            .where(
                ProgramSemester.study_program_id == study_program.id,
                ProgramSemester.is_active.is_(True),
            )
            .order_by(ProgramSemester.semester_number)
        ).all()
    )
    semester_by_number = {
        semester.semester_number: semester for semester in semesters
    }

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    expected_numbers = set(range(1, study_program.level.semester_count + 1))
    actual_numbers = set(semester_by_number)

    for semester_number in sorted(expected_numbers - actual_numbers):
        errors.append(
            _issue(
                "missing_program_semester",
                "The study program is missing an active semester.",
                semester_number=semester_number,
            )
        )

    for semester_number in sorted(actual_numbers - expected_numbers):
        errors.append(
            _issue(
                "semester_exceeds_level",
                "An active semester exceeds the level semester count.",
                semester_number=semester_number,
            )
        )

    semester_totals: dict[int, Decimal] = {}
    for semester in semesters:
        curriculum_courses = list(
            db.scalars(
                select(CurriculumCourse).where(
                    CurriculumCourse.program_semester_id == semester.id,
                    CurriculumCourse.is_active.is_(True),
                )
            ).all()
        )
        elective_groups = list(
            db.scalars(
                select(ElectiveGroup).where(
                    ElectiveGroup.program_semester_id == semester.id,
                    ElectiveGroup.is_active.is_(True),
                )
            ).all()
        )
        group_by_id = {group.id: group for group in elective_groups}
        mandatory_ects = Decimal("0")
        elective_ects = Decimal("0")

        for curriculum_course in curriculum_courses:
            weekly_periods = (
                curriculum_course.lecture_periods_per_week
                + curriculum_course.numerical_periods_per_week
                + curriculum_course.laboratory_periods_per_week
            )
            if curriculum_course.requires_timetable and weekly_periods == 0:
                errors.append(
                    _issue(
                        "timetabled_course_without_periods",
                        "A timetabled course has no weekly teaching periods.",
                        semester_number=semester.semester_number,
                        curriculum_course_id=curriculum_course.id,
                    )
                )

            if not curriculum_course.requires_timetable and weekly_periods > 0:
                warnings.append(
                    _issue(
                        "non_timetabled_course_has_periods",
                        "A non-timetabled course still contains weekly teaching periods.",
                        semester_number=semester.semester_number,
                        curriculum_course_id=curriculum_course.id,
                        weekly_periods=weekly_periods,
                    )
                )

            if curriculum_course.course_type == CourseType.MANDATORY:
                if curriculum_course.elective_group_id is not None:
                    errors.append(
                        _issue(
                            "mandatory_course_has_elective_group",
                            "A mandatory course belongs to an elective group.",
                            curriculum_course_id=curriculum_course.id,
                        )
                    )
                mandatory_ects += curriculum_course.ects
                continue

            elective_group_id = curriculum_course.elective_group_id
            if elective_group_id is None:
                errors.append(
                    _issue(
                        "elective_course_without_group",
                        "An elective course has no elective group.",
                        curriculum_course_id=curriculum_course.id,
                    )
                )
            elif elective_group_id not in group_by_id:
                errors.append(
                    _issue(
                        "inactive_elective_group",
                        "An active elective course uses an inactive group.",
                        curriculum_course_id=curriculum_course.id,
                        elective_group_id=elective_group_id,
                    )
                )

        for group in elective_groups:
            options = [
                course
                for course in curriculum_courses
                if course.course_type == CourseType.ELECTIVE
                and course.elective_group_id == group.id
            ]
            if len(options) < group.required_choices:
                errors.append(
                    _issue(
                        "insufficient_elective_choices",
                        "The elective group has fewer options than required choices.",
                        elective_group_id=group.id,
                        option_count=len(options),
                        required_choices=group.required_choices,
                    )
                )
                continue

            option_ects = {option.ects for option in options}
            if len(option_ects) != 1:
                errors.append(
                    _issue(
                        "unequal_elective_ects",
                        "Choices in one elective group must have equal ECTS.",
                        elective_group_id=group.id,
                        ects_values=sorted(option_ects),
                    )
                )
                continue

            elective_ects += option_ects.pop() * group.required_choices

        semester_total = mandatory_ects + elective_ects
        semester_totals[semester.semester_number] = semester_total
        if semester_total != expected_ects_per_semester:
            errors.append(
                _issue(
                    "invalid_semester_ects",
                    "The semester does not resolve to the required ECTS total.",
                    semester_number=semester.semester_number,
                    actual_ects=semester_total,
                    expected_ects=expected_ects_per_semester,
                )
            )

    return {
        "is_valid": not errors,
        "study_program_id": study_program.id,
        "expected_ects_per_semester": expected_ects_per_semester,
        "semester_totals": semester_totals,
        "errors": errors,
        "warnings": warnings,
    }


def validate_study_program_curriculum(
    db: Session,
    study_program_id: int,
    *,
    expected_ects_per_semester: Decimal = DEFAULT_SEMESTER_ECTS,
) -> dict[str, Any]:
    report = get_curriculum_validation_report(
        db,
        study_program_id,
        expected_ects_per_semester=expected_ects_per_semester,
    )
    if not report["is_valid"]:
        raise BusinessRuleError(
            "The study-program curriculum is incomplete or inconsistent.",
            details=report,
        )
    return report
