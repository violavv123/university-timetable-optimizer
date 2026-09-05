import pytest
from app.core.exceptions import BusinessRuleError, InvalidReferenceError
from app.models.enums import ComponentType, StudentGroupType, TeachingRole
from sqlalchemy.orm import Session
from tests.services.academic.factories import make_academic_term, make_academic_year
from tests.services.resources.factories import (
    ResourceContext,
    make_staff_course,
    make_staff_member,
    make_student_group,
)
from tests.services.scheduling_input.factories import (
    attach_group,
    attach_staff,
    make_course_session,
    make_scheduling_context,
)

pytestmark = pytest.mark.integration


def test_group_and_offering_must_share_program_semester_and_term(
    db: Session,
) -> None:
    context = make_scheduling_context(db)
    session = make_course_session(db, context)
    other_year = make_academic_year(db, start_year=2202)
    other_term = make_academic_term(db, other_year)
    other_context = ResourceContext(
        context.resources.hierarchy,
        other_term,
        context.resources.course,
    )
    other_term_group = make_student_group(db, other_context)

    with pytest.raises(InvalidReferenceError, match="same academic term"):
        attach_group(db, session, other_term_group)


def test_group_type_must_match_session_component(db: Session) -> None:
    context = make_scheduling_context(db)
    session = make_course_session(db, context)
    lab_group = make_student_group(
        db,
        context.resources,
        group_type=StudentGroupType.LAB_GROUP,
        student_count=10,
        parent_group=context.cohort,
    )

    with pytest.raises(BusinessRuleError, match="incompatible"):
        attach_group(db, session, lab_group)


def test_session_cannot_contain_both_parent_and_descendant_groups(
    db: Session,
) -> None:
    context = make_scheduling_context(
        db,
        lecture_periods=0,
        numerical_periods=2,
    )
    session = make_course_session(
        db,
        context,
        component_type=ComponentType.NUMERICAL,
    )
    child = make_student_group(
        db,
        context.resources,
        group_type=StudentGroupType.NUMERICAL_GROUP,
        student_count=15,
        parent_group=context.cohort,
    )
    attach_group(db, session, context.cohort)

    with pytest.raises(BusinessRuleError, match="ancestor"):
        attach_group(db, session, child)


def test_assigned_groups_cannot_exceed_session_capacity(db: Session) -> None:
    context = make_scheduling_context(db)
    session = make_course_session(db, context, max_students=20)

    with pytest.raises(BusinessRuleError, match="max_students"):
        attach_group(db, session, context.cohort)


def test_teaching_role_and_staff_capability_must_match_component(
    db: Session,
) -> None:
    context = make_scheduling_context(db)
    session = make_course_session(db, context)

    with pytest.raises(BusinessRuleError, match="teaching_role"):
        attach_staff(
            db,
            session,
            context.staff_member,
            teaching_role=TeachingRole.LAB_INSTRUCTOR,
        )

    assistant_only = make_staff_member(
        db,
        context.resources.hierarchy.faculty.id,
    )
    make_staff_course(
        db,
        assistant_only,
        context.resources.course,
        can_lecture=False,
        can_assist=True,
    )
    with pytest.raises(BusinessRuleError, match="can_lecture=True"):
        attach_staff(db, session, assistant_only)


def test_session_can_have_only_one_primary_staff_member(db: Session) -> None:
    context = make_scheduling_context(db)
    session = make_course_session(db, context)
    attach_staff(db, session, context.staff_member)
    second_staff = make_staff_member(
        db,
        context.resources.hierarchy.faculty.id,
    )
    make_staff_course(db, second_staff, context.resources.course)

    with pytest.raises(BusinessRuleError, match="only one primary"):
        attach_staff(db, session, second_staff, is_primary=True)
