import pytest
from app.core.exceptions import (
    BusinessRuleError,
    InvalidReferenceError,
    ResourceInUseError,
)
from app.models.enums import StudentGroupType, TermType
from app.schemas.student_group import StudentGroupCreate, StudentGroupUpdate
from app.services.resources.student_group import (
    create_student_group,
    delete_student_group,
    update_student_group,
)
from sqlalchemy.orm import Session
from tests.services.academic.factories import (
    make_academic_term,
    make_academic_year,
    make_hierarchy,
)
from tests.services.resources.factories import (
    ResourceContext,
    make_resource_context,
    make_student_group,
)

pytestmark = pytest.mark.integration


def test_group_term_type_must_match_program_semester(db: Session) -> None:
    hierarchy = make_hierarchy(db, created_semesters=(2,))
    academic_year = make_academic_year(db)
    winter_term = make_academic_term(
        db,
        academic_year,
        term_type=TermType.WINTER,
    )
    payload = StudentGroupCreate(
        program_semester_id=hierarchy.semesters[0].id,
        academic_term_id=winter_term.id,
        parent_group_id=None,
        name="Semester two cohort",
        group_type=StudentGroupType.COHORT,
        student_count=30,
        is_active=True,
    )

    with pytest.raises(InvalidReferenceError, match="term type"):
        create_student_group(db, payload)


def test_noncohort_group_requires_a_compatible_parent(
    db: Session,
) -> None:
    context = make_resource_context(db)
    missing_parent = StudentGroupCreate(
        program_semester_id=context.hierarchy.semesters[0].id,
        academic_term_id=context.academic_term.id,
        parent_group_id=None,
        name="Lab group without parent",
        group_type=StudentGroupType.LAB_GROUP,
        student_count=10,
        is_active=True,
    )

    with pytest.raises(BusinessRuleError, match="require a parent"):
        create_student_group(db, missing_parent)

    cohort = make_student_group(db, context, student_count=30)
    lab = make_student_group(
        db,
        context,
        group_type=StudentGroupType.LAB_GROUP,
        student_count=10,
        parent_group=cohort,
    )
    invalid_child = StudentGroupCreate(
        program_semester_id=context.hierarchy.semesters[0].id,
        academic_term_id=context.academic_term.id,
        parent_group_id=lab.id,
        name="Numerical below laboratory",
        group_type=StudentGroupType.NUMERICAL_GROUP,
        student_count=5,
        is_active=True,
    )

    with pytest.raises(BusinessRuleError, match="not broader"):
        create_student_group(db, invalid_child)


def test_child_and_same_type_sibling_counts_cannot_exceed_parent(
    db: Session,
) -> None:
    context = make_resource_context(db)
    cohort = make_student_group(db, context, student_count=30)

    oversized_child = StudentGroupCreate(
        program_semester_id=context.hierarchy.semesters[0].id,
        academic_term_id=context.academic_term.id,
        parent_group_id=cohort.id,
        name="Oversized numerical group",
        group_type=StudentGroupType.NUMERICAL_GROUP,
        student_count=31,
        is_active=True,
    )
    with pytest.raises(BusinessRuleError, match="more students"):
        create_student_group(db, oversized_child)

    make_student_group(
        db,
        context,
        group_type=StudentGroupType.NUMERICAL_GROUP,
        student_count=20,
        parent_group=cohort,
    )
    with pytest.raises(BusinessRuleError, match="siblings"):
        make_student_group(
            db,
            context,
            group_type=StudentGroupType.NUMERICAL_GROUP,
            student_count=15,
            parent_group=cohort,
        )


def test_indirect_parent_cycle_is_detected(db: Session) -> None:
    context = make_resource_context(db)
    cohort = make_student_group(db, context, student_count=20)
    numerical = make_student_group(
        db,
        context,
        group_type=StudentGroupType.NUMERICAL_GROUP,
        student_count=10,
        parent_group=cohort,
    )
    laboratory = make_student_group(
        db,
        context,
        group_type=StudentGroupType.LAB_GROUP,
        student_count=5,
        parent_group=numerical,
    )

    # Simulate legacy/imported corruption that bypassed the service.
    cohort.parent_group_id = laboratory.id
    db.commit()

    with pytest.raises(BusinessRuleError, match="cycle"):
        update_student_group(
            db,
            laboratory.id,
            StudentGroupUpdate(student_count=5),
        )


def test_parent_group_cannot_deactivate_with_active_children(
    db: Session,
) -> None:
    context = make_resource_context(db)
    cohort = make_student_group(db, context, student_count=30)
    child = make_student_group(
        db,
        context,
        group_type=StudentGroupType.NUMERICAL_GROUP,
        student_count=15,
        parent_group=cohort,
    )

    with pytest.raises(ResourceInUseError) as exc_info:
        delete_student_group(db, cohort.id)

    assert exc_info.value.details["child_group_id"] == child.id
    db.refresh(cohort)
    assert cohort.is_active is True


def test_parent_and_child_must_share_term_and_semester(db: Session) -> None:
    first_context = make_resource_context(db)
    parent = make_student_group(db, first_context, student_count=30)
    second_hierarchy = make_hierarchy(db, created_semesters=(1,))
    second_context = ResourceContext(
        second_hierarchy,
        first_context.academic_term,
        first_context.course,
    )

    with pytest.raises(InvalidReferenceError, match="same semester and term"):
        make_student_group(
            db,
            second_context,
            group_type=StudentGroupType.LAB_GROUP,
            student_count=10,
            parent_group=parent,
        )
