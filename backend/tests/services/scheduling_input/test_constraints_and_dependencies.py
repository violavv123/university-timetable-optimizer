from dataclasses import replace
from datetime import time

import pytest
from app.core.exceptions import BusinessRuleError, InvalidReferenceError
from app.models.course_session_time_constraint import (
    CourseSessionTimeConstraint,
)
from app.models.enums import (
    DayOfWeek,
    DependencyType,
    TimeConstraintType,
)
from app.schemas.course_session_dependency import CourseSessionDependencyCreate
from app.schemas.course_session_time_constraint import (
    CourseSessionTimeConstraintCreate,
)
from app.services.scheduling_input.course_session_dependency import (
    create_course_session_dependency,
)
from app.services.scheduling_input.course_session_time_constraint import (
    create_course_session_time_constraint,
)
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.services.academic.factories import make_academic_term, make_academic_year
from tests.services.resources.factories import ResourceContext
from tests.services.scheduling_input.factories import (
    make_course_offering,
    make_course_session,
    make_dependency,
    make_master_scheduling_context,
    make_scheduling_context,
    make_time_constraint,
)

pytestmark = pytest.mark.integration


def test_preferred_constraints_require_weight_and_hard_constraints_forbid_it(
    db: Session,
) -> None:
    context = make_scheduling_context(db)
    session = make_course_session(db, context)

    missing_weight = CourseSessionTimeConstraintCreate.model_construct(
        course_session_id=session.id,
        day_of_week=None,
        start_time=time(9, 0),
        end_time=time(11, 0),
        constraint_type=TimeConstraintType.PREFERRED_WINDOW,
        preference_weight=None,
    )
    with pytest.raises(BusinessRuleError, match="requires preference_weight"):
        create_course_session_time_constraint(db, missing_weight)

    hard_with_weight = CourseSessionTimeConstraintCreate.model_construct(
        course_session_id=session.id,
        day_of_week=None,
        start_time=time(8, 0),
        end_time=time(18, 0),
        constraint_type=TimeConstraintType.ALLOWED_WINDOW,
        preference_weight=1,
    )
    with pytest.raises(BusinessRuleError, match="must not have"):
        create_course_session_time_constraint(db, hard_with_weight)


def test_fixed_window_requires_one_weekly_occurrence_and_specific_day(
    db: Session,
) -> None:
    context = make_scheduling_context(db, lecture_periods=4)
    repeated = make_course_session(
        db,
        context,
        weekly_frequency=2,
        duration_slots=2,
    )

    with pytest.raises(BusinessRuleError, match="specific day"):
        make_time_constraint(
            db,
            repeated,
            constraint_type=TimeConstraintType.FIXED_WINDOW,
            start_time=time(9, 0),
            end_time=time(10, 30),
        )

    with pytest.raises(BusinessRuleError, match="weekly_frequency=1"):
        make_time_constraint(
            db,
            repeated,
            constraint_type=TimeConstraintType.FIXED_WINDOW,
            day_of_week=DayOfWeek.MONDAY,
            start_time=time(9, 0),
            end_time=time(10, 30),
        )


def test_fixed_and_preferred_windows_respect_allowed_and_forbidden_windows(
    db: Session,
) -> None:
    context = make_scheduling_context(db)
    session = make_course_session(db, context)
    make_time_constraint(
        db,
        session,
        constraint_type=TimeConstraintType.ALLOWED_WINDOW,
        start_time=time(8, 0),
        end_time=time(16, 0),
    )
    make_time_constraint(
        db,
        session,
        constraint_type=TimeConstraintType.FORBIDDEN_WINDOW,
        day_of_week=DayOfWeek.MONDAY,
        start_time=time(12, 0),
        end_time=time(13, 0),
    )

    with pytest.raises(BusinessRuleError, match="forbidden"):
        make_time_constraint(
            db,
            session,
            constraint_type=TimeConstraintType.PREFERRED_WINDOW,
            day_of_week=DayOfWeek.MONDAY,
            start_time=time(11, 0),
            end_time=time(12, 30),
            preference_weight=2,
        )

    with pytest.raises(BusinessRuleError, match="inside an allowed"):
        make_time_constraint(
            db,
            session,
            constraint_type=TimeConstraintType.FIXED_WINDOW,
            day_of_week=DayOfWeek.TUESDAY,
            start_time=time(17, 0),
            end_time=time(18, 0),
        )


def test_master_session_receives_required_evening_policy(db: Session) -> None:
    context = make_master_scheduling_context(db)
    session = make_course_session(db, context)
    constraints = list(
        db.scalars(
            select(CourseSessionTimeConstraint).where(
                CourseSessionTimeConstraint.course_session_id == session.id
            )
        ).all()
    )

    assert any(
        item.constraint_type == TimeConstraintType.ALLOWED_WINDOW
        and item.start_time == time(8, 0)
        and item.end_time == time(20, 0)
        for item in constraints
    )
    assert any(
        item.constraint_type == TimeConstraintType.PREFERRED_WINDOW
        and item.start_time == time(17, 0)
        and item.end_time == time(20, 0)
        and item.preference_weight == 1
        for item in constraints
    )


def test_dependency_rejects_self_reference_and_invalid_gap_rules(
    db: Session,
) -> None:
    context = make_scheduling_context(db, lecture_periods=2)
    first = make_course_session(db, context, duration_slots=1)
    second = make_course_session(db, context, duration_slots=1)

    self_reference = CourseSessionDependencyCreate.model_construct(
        predecessor_session_id=first.id,
        successor_session_id=first.id,
        dependency_type=DependencyType.PRECEDES,
        min_gap_slots=None,
        max_gap_slots=None,
    )
    with pytest.raises(BusinessRuleError, match="depend on itself"):
        create_course_session_dependency(db, self_reference)

    same_day_with_gap = CourseSessionDependencyCreate.model_construct(
        predecessor_session_id=first.id,
        successor_session_id=second.id,
        dependency_type=DependencyType.SAME_DAY,
        min_gap_slots=1,
        max_gap_slots=None,
    )
    with pytest.raises(BusinessRuleError, match="cannot define slot gaps"):
        create_course_session_dependency(db, same_day_with_gap)

    consecutive_with_gap = CourseSessionDependencyCreate.model_construct(
        predecessor_session_id=first.id,
        successor_session_id=second.id,
        dependency_type=DependencyType.CONSECUTIVE,
        min_gap_slots=None,
        max_gap_slots=1,
    )
    with pytest.raises(BusinessRuleError, match="zero gap"):
        create_course_session_dependency(db, consecutive_with_gap)


def test_dependent_sessions_must_be_in_same_academic_term(db: Session) -> None:
    context = make_scheduling_context(db, lecture_periods=2)
    first = make_course_session(db, context, duration_slots=1)
    other_year = make_academic_year(db, start_year=2202)
    other_term = make_academic_term(db, other_year)
    other_offering = make_course_offering(
        db,
        context.curriculum_course,
        other_term.id,
    )
    other_resources = ResourceContext(
        context.resources.hierarchy,
        other_term,
        context.resources.course,
    )
    other_context = replace(
        context,
        resources=other_resources,
        offering=other_offering,
    )
    second = make_course_session(db, other_context, duration_slots=1)

    with pytest.raises(InvalidReferenceError, match="same academic term"):
        make_dependency(db, first, second)


def test_dependency_graph_cannot_contain_an_indirect_cycle(db: Session) -> None:
    context = make_scheduling_context(db, lecture_periods=3)
    first = make_course_session(db, context, duration_slots=1)
    second = make_course_session(db, context, duration_slots=1)
    third = make_course_session(db, context, duration_slots=1)
    make_dependency(db, first, second)
    make_dependency(db, second, third)

    with pytest.raises(BusinessRuleError, match="indirect cycle"):
        make_dependency(db, third, first)


def test_same_day_and_different_day_dependencies_are_contradictory(
    db: Session,
) -> None:
    context = make_scheduling_context(db, lecture_periods=2)
    first = make_course_session(db, context, duration_slots=1)
    second = make_course_session(db, context, duration_slots=1)
    make_dependency(
        db,
        first,
        second,
        dependency_type=DependencyType.SAME_DAY,
    )

    with pytest.raises(BusinessRuleError, match="conflicts"):
        make_dependency(
            db,
            first,
            second,
            dependency_type=DependencyType.DIFFERENT_DAY,
        )
