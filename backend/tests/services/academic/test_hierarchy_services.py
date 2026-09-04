import pytest
from app.core.exceptions import (
    BusinessRuleError,
    DuplicateResourceError,
    InactiveResourceError,
    ResourceInUseError,
)
from app.schemas.level import LevelUpdate
from app.schemas.program_semester import ProgramSemesterCreate
from app.schemas.study_program import StudyProgramUpdate
from app.services.academic.level import update_level
from app.services.academic.program_semester import (
    create_program_semester,
    delete_program_semester,
)
from app.services.academic.study_program import update_study_program
from sqlalchemy.orm import Session
from tests.services.academic.factories import (
    make_course,
    make_curriculum_course,
    make_hierarchy,
    make_level,
    make_program_semester,
)

pytestmark = pytest.mark.integration


def test_semester_number_cannot_exceed_level_semester_count(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(
        db,
        semester_count=4,
        created_semesters=(),
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        create_program_semester(
            db,
            ProgramSemesterCreate(
                study_program_id=hierarchy.study_program.id,
                semester_number=5,
                is_active=True,
            ),
        )

    assert exc_info.value.details["level_semester_count"] == 4


def test_level_cannot_shrink_below_existing_program_semester(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(
        db,
        semester_count=6,
        created_semesters=(6,),
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        update_level(
            db,
            hierarchy.level.id,
            LevelUpdate(semester_count=5),
        )

    assert exc_info.value.details["highest_existing_semester"] == 6
    db.refresh(hierarchy.level)
    assert hierarchy.level.semester_count == 6


def test_program_cannot_move_to_level_with_too_few_semesters(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(
        db,
        semester_count=6,
        created_semesters=(6,),
    )
    shorter_level = make_level(db, semester_count=4)

    with pytest.raises(BusinessRuleError) as exc_info:
        update_study_program(
            db,
            hierarchy.study_program.id,
            StudyProgramUpdate(level_id=shorter_level.id),
        )

    assert exc_info.value.details["highest_existing_semester"] == 6
    assert exc_info.value.details["level_semester_count"] == 4


def test_duplicate_program_semester_is_reported_explicitly(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(db, created_semesters=(1,))

    with pytest.raises(DuplicateResourceError) as exc_info:
        make_program_semester(db, hierarchy.study_program, 1)

    assert exc_info.value.details["fields"] == [
        "study_program_id",
        "semester_number",
    ]


def test_active_semester_cannot_be_created_under_inactive_program(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(db, created_semesters=())
    hierarchy.study_program.is_active = False
    db.commit()

    with pytest.raises(InactiveResourceError):
        make_program_semester(db, hierarchy.study_program, 1)


def test_program_semester_cannot_deactivate_with_active_curriculum(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(db)
    semester = hierarchy.semesters[0]
    course = make_course(db)
    make_curriculum_course(db, semester, course)

    with pytest.raises(ResourceInUseError) as exc_info:
        delete_program_semester(db, semester.id)

    assert exc_info.value.details["dependent_resource"] == "curriculum course"
    db.refresh(semester)
    assert semester.is_active is True
