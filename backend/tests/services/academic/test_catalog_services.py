import pytest
from app.core.exceptions import (
    BusinessRuleError,
    DuplicateResourceError,
    InactiveResourceError,
    ResourceInUseError,
    ResourceNotFoundError,
)
from app.models.faculty import Faculty
from app.schemas.common import PaginationParams
from app.schemas.faculty import FacultyCreate, FacultyUpdate
from app.schemas.study_program import StudyProgramCreate
from app.services.academic.faculty import (
    create_faculty,
    delete_faculty,
    list_faculties,
    update_faculty,
)
from app.services.academic.study_program import create_study_program
from sqlalchemy.orm import Session
from tests.services.academic.factories import (
    make_faculty,
    make_hierarchy,
    make_level,
    unique_code,
)

pytestmark = pytest.mark.integration


def test_faculty_code_is_normalized_and_duplicate_is_explicit(
    db: Session,
) -> None:
    faculty = create_faculty(
        db,
        FacultyCreate(
            code="  fiek-test  ",
            name="Faculty of Electrical and Computer Engineering",
            is_active=True,
        ),
    )

    assert faculty.code == "FIEK-TEST"

    with pytest.raises(DuplicateResourceError) as exc_info:
        create_faculty(
            db,
            FacultyCreate(
                code="FiEk-TeSt",
                name="Duplicate faculty",
                is_active=True,
            ),
        )

    assert exc_info.value.details == {
        "resource": "Faculty",
        "fields": ["code"],
    }

    # A service validation failure must not poison the current transaction.
    another = make_faculty(db)
    assert another.id > faculty.id


def test_patch_rejects_explicit_null_for_required_column(db: Session) -> None:
    faculty = make_faculty(db)

    with pytest.raises(BusinessRuleError, match="cannot be null"):
        update_faculty(
            db,
            faculty.id,
            FacultyUpdate(code=None),
        )

    db.refresh(faculty)
    assert faculty.code is not None


def test_faculty_delete_is_soft_and_default_listing_hides_it(
    db: Session,
) -> None:
    faculty = make_faculty(db)

    response = delete_faculty(db, faculty.id)

    assert response.message == "Faculty deactivated successfully."
    stored_faculty = db.get(Faculty, faculty.id)
    assert stored_faculty is not None
    assert stored_faculty.is_active is False

    active_page = list_faculties(db, PaginationParams(page=1, page_size=100))
    all_page = list_faculties(
        db,
        PaginationParams(page=1, page_size=100),
        include_inactive=True,
    )

    assert faculty.id not in {item.id for item in active_page.items}
    assert faculty.id in {item.id for item in all_page.items}


def test_faculty_deactivation_is_blocked_by_active_dependents(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(db)

    with pytest.raises(ResourceInUseError) as exc_info:
        delete_faculty(db, hierarchy.faculty.id)

    assert exc_info.value.details["dependent_resource"] == "study program"
    db.refresh(hierarchy.faculty)
    assert hierarchy.faculty.is_active is True


def test_active_study_program_requires_active_parents(db: Session) -> None:
    inactive_faculty = make_faculty(db, is_active=False)
    active_level = make_level(db)

    with pytest.raises(InactiveResourceError):
        create_study_program(
            db,
            StudyProgramCreate(
                faculty_id=inactive_faculty.id,
                level_id=active_level.id,
                code=unique_code("PROG"),
                name="Invalid active program",
                is_active=True,
            ),
        )


def test_study_program_foreign_key_existence_is_checked(db: Session) -> None:
    level = make_level(db)

    with pytest.raises(ResourceNotFoundError) as exc_info:
        create_study_program(
            db,
            StudyProgramCreate(
                faculty_id=2_147_483_647,
                level_id=level.id,
                code=unique_code("PROG"),
                name="Program with missing faculty",
                is_active=True,
            ),
        )

    assert exc_info.value.details == {
        "resource": "Faculty",
        "identifier": "2147483647",
    }
