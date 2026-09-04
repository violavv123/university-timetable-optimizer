from datetime import date

import pytest
from app.core.exceptions import BusinessRuleError, ResourceInUseError
from app.models.academic_year import AcademicYear
from app.models.enums import StudentGroupType, TermType
from app.models.student_group import StudentGroup
from app.schemas.academic_term import AcademicTermCreate, AcademicTermUpdate
from app.schemas.academic_year import AcademicYearCreate, AcademicYearUpdate
from app.services.academic.academic_term import (
    create_academic_term,
    delete_academic_term,
    update_academic_term,
)
from app.services.academic.academic_year import (
    create_academic_year,
    delete_academic_year,
    set_current_academic_year,
    update_academic_year,
)
from sqlalchemy.orm import Session
from tests.services.academic.factories import (
    make_academic_term,
    make_academic_year,
    make_hierarchy,
)

pytestmark = pytest.mark.integration


def add_student_group_dependency(
    db: Session,
    *,
    academic_term_id: int,
    program_semester_id: int,
) -> StudentGroup:
    student_group = StudentGroup(
        academic_term_id=academic_term_id,
        program_semester_id=program_semester_id,
        parent_group_id=None,
        name="Test cohort",
        group_type=StudentGroupType.COHORT,
        student_count=20,
        is_active=True,
    )
    db.add(student_group)
    db.commit()
    db.refresh(student_group)
    return student_group


def test_academic_year_name_must_match_its_dates(db: Session) -> None:
    with pytest.raises(BusinessRuleError, match="correspond"):
        create_academic_year(
            db,
            AcademicYearCreate(
                name="2200/2201",
                start_date=date(2199, 9, 1),
                end_date=date(2201, 8, 31),
            ),
        )


def test_academic_year_date_ranges_cannot_overlap(db: Session) -> None:
    make_academic_year(db, 2200)

    with pytest.raises(BusinessRuleError) as exc_info:
        create_academic_year(
            db,
            AcademicYearCreate(
                name="2201/2202",
                start_date=date(2201, 8, 1),
                end_date=date(2202, 7, 31),
            ),
        )

    assert "overlapping_academic_year_id" in exc_info.value.details


def test_academic_term_must_fit_inside_academic_year(db: Session) -> None:
    academic_year = make_academic_year(db)

    with pytest.raises(BusinessRuleError, match="fit inside"):
        create_academic_term(
            db,
            AcademicTermCreate(
                academic_year_id=academic_year.id,
                name="Invalid winter term",
                term_type=TermType.WINTER,
                start_date=date(2199, 9, 1),
                end_date=date(2200, 1, 31),
                is_active=True,
            ),
        )


def test_terms_in_same_year_cannot_overlap(db: Session) -> None:
    academic_year = make_academic_year(db)
    make_academic_term(
        db,
        academic_year,
        term_type=TermType.WINTER,
        start_date=date(2200, 9, 15),
        end_date=date(2201, 2, 28),
    )

    with pytest.raises(BusinessRuleError, match="cannot overlap"):
        make_academic_term(
            db,
            academic_year,
            term_type=TermType.SUMMER,
            start_date=date(2201, 2, 1),
            end_date=date(2201, 6, 30),
        )


def test_winter_term_must_precede_summer_term(db: Session) -> None:
    academic_year = make_academic_year(db)
    make_academic_term(
        db,
        academic_year,
        term_type=TermType.SUMMER,
        start_date=date(2200, 10, 1),
        end_date=date(2200, 12, 31),
    )

    with pytest.raises(BusinessRuleError, match="winter term"):
        make_academic_term(
            db,
            academic_year,
            term_type=TermType.WINTER,
            start_date=date(2201, 1, 15),
            end_date=date(2201, 5, 31),
        )


def test_year_cannot_shrink_around_existing_term(db: Session) -> None:
    academic_year = make_academic_year(db)
    term = make_academic_term(db, academic_year)

    with pytest.raises(BusinessRuleError) as exc_info:
        update_academic_year(
            db,
            academic_year.id,
            AcademicYearUpdate(start_date=term.start_date.replace(day=16)),
        )

    assert exc_info.value.details["academic_term_id"] == term.id
    db.refresh(academic_year)
    assert academic_year.start_date == date(2200, 9, 1)


def test_term_patch_is_validated_after_merging_stored_dates(
    db: Session,
) -> None:
    academic_year = make_academic_year(db)
    term = make_academic_term(db, academic_year)

    with pytest.raises(BusinessRuleError, match="after start_date"):
        update_academic_term(
            db,
            term.id,
            AcademicTermUpdate(end_date=term.start_date),
        )

    db.refresh(term)
    assert term.end_date == date(2201, 1, 31)


def test_referenced_term_cannot_be_structurally_changed(db: Session) -> None:
    hierarchy = make_hierarchy(db)
    academic_year = make_academic_year(db)
    term = make_academic_term(db, academic_year)
    student_group = add_student_group_dependency(
        db,
        academic_term_id=term.id,
        program_semester_id=hierarchy.semesters[0].id,
    )

    with pytest.raises(ResourceInUseError) as exc_info:
        update_academic_term(
            db,
            term.id,
            AcademicTermUpdate(start_date=date(2200, 9, 16)),
        )

    assert exc_info.value.details == {
        "academic_term_id": term.id,
        "dependent_resource": "student group",
        "dependent_id": student_group.id,
    }


def test_term_cannot_deactivate_with_active_student_groups(
    db: Session,
) -> None:
    hierarchy = make_hierarchy(db)
    academic_year = make_academic_year(db)
    term = make_academic_term(db, academic_year)
    student_group = add_student_group_dependency(
        db,
        academic_term_id=term.id,
        program_semester_id=hierarchy.semesters[0].id,
    )

    with pytest.raises(ResourceInUseError) as exc_info:
        delete_academic_term(db, term.id)

    assert exc_info.value.details["student_group_id"] == student_group.id
    db.refresh(term)
    assert term.is_active is True


def test_set_current_year_leaves_exactly_one_current(db: Session) -> None:
    first = make_academic_year(db, 2200)
    second = make_academic_year(db, 2202)

    set_current_academic_year(db, first.id)
    current = set_current_academic_year(db, second.id)

    db.refresh(first)
    assert first.is_current is False
    assert current.is_current is True


def test_year_with_terms_cannot_be_deleted(db: Session) -> None:
    academic_year = make_academic_year(db)
    term = make_academic_term(db, academic_year)

    with pytest.raises(ResourceInUseError) as exc_info:
        delete_academic_year(db, academic_year.id)

    assert exc_info.value.details["academic_term_id"] == term.id
    assert db.get(AcademicYear, academic_year.id) is not None


def test_empty_noncurrent_year_is_hard_deleted(db: Session) -> None:
    academic_year = make_academic_year(db)

    response = delete_academic_year(db, academic_year.id)

    assert response.message == "Academic year deleted successfully."
    assert db.get(AcademicYear, academic_year.id) is None


def test_current_year_cannot_be_deleted(db: Session) -> None:
    academic_year = make_academic_year(db)
    set_current_academic_year(db, academic_year.id)

    with pytest.raises(ResourceInUseError, match="current academic year"):
        delete_academic_year(db, academic_year.id)
