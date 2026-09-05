import pytest
from app.core.exceptions import (
    BusinessRuleError,
    InvalidReferenceError,
    ResourceInUseError,
)
from app.models.enums import (
    ComponentType,
    CourseOfferingStatus,
    RoomType,
    TermType,
)
from app.schemas.course_offering import CourseOfferingCreate, CourseOfferingUpdate
from app.schemas.course_session_group import CourseSessionGroupCreate
from app.services.scheduling_input.course_offering import (
    create_course_offering,
    update_course_offering,
)
from app.services.scheduling_input.course_session_group import (
    create_course_session_group,
)
from sqlalchemy.orm import Session
from tests.services.academic.factories import (
    make_academic_term,
    make_academic_year,
    make_course,
    make_curriculum_course,
    make_hierarchy,
)
from tests.services.resources.factories import make_room
from tests.services.scheduling_input.factories import (
    attach_group,
    attach_staff,
    make_course_session,
    make_scheduling_context,
)

pytestmark = pytest.mark.integration


def test_offering_requires_a_timetabled_curriculum_course(db: Session) -> None:
    hierarchy = make_hierarchy(db, created_semesters=(1,))
    course = make_course(db)
    curriculum = make_curriculum_course(
        db,
        hierarchy.semesters[0],
        course,
        requires_timetable=False,
        lecture_periods_per_week=0,
    )
    academic_year = make_academic_year(db)
    term = make_academic_term(db, academic_year)
    payload = CourseOfferingCreate(
        curriculum_course_id=curriculum.id,
        academic_term_id=term.id,
        expected_students=30,
        status=CourseOfferingStatus.DRAFT,
    )

    with pytest.raises(BusinessRuleError, match="requires_timetable=False"):
        create_course_offering(db, payload)


def test_offering_term_type_must_match_program_semester(db: Session) -> None:
    hierarchy = make_hierarchy(db, created_semesters=(2,))
    curriculum = make_curriculum_course(
        db,
        hierarchy.semesters[0],
        make_course(db),
    )
    academic_year = make_academic_year(db)
    winter_term = make_academic_term(
        db,
        academic_year,
        term_type=TermType.WINTER,
    )
    payload = CourseOfferingCreate(
        curriculum_course_id=curriculum.id,
        academic_term_id=winter_term.id,
        expected_students=30,
        status=CourseOfferingStatus.DRAFT,
    )

    with pytest.raises(InvalidReferenceError, match="term type"):
        create_course_offering(db, payload)


def test_new_offering_must_start_in_draft(db: Session) -> None:
    context = make_scheduling_context(db)
    second_course = make_course(db)
    second_curriculum = make_curriculum_course(
        db,
        context.resources.hierarchy.semesters[0],
        second_course,
    )
    payload = CourseOfferingCreate.model_construct(
        curriculum_course_id=second_curriculum.id,
        academic_term_id=context.resources.academic_term.id,
        expected_students=30,
        status=CourseOfferingStatus.READY,
    )

    with pytest.raises(BusinessRuleError, match="start in DRAFT"):
        create_course_offering(db, payload)


def test_session_periods_cannot_exceed_curriculum_totals(db: Session) -> None:
    context = make_scheduling_context(db, lecture_periods=2)

    with pytest.raises(BusinessRuleError, match="exceed"):
        make_course_session(
            db,
            context,
            weekly_frequency=2,
            duration_slots=2,
        )


def test_laboratory_session_automatically_requires_laboratory_room_type(
    db: Session,
) -> None:
    context = make_scheduling_context(
        db,
        lecture_periods=0,
        laboratory_periods=2,
        room_type=RoomType.LABORATORY,
    )

    session = make_course_session(
        db,
        context,
        component_type=ComponentType.LABORATORY,
    )

    assert session.required_room_type == RoomType.LABORATORY


def test_laboratory_session_rejects_a_specific_general_room(
    db: Session,
) -> None:
    context = make_scheduling_context(
        db,
        lecture_periods=0,
        laboratory_periods=2,
        room_type=RoomType.GENERAL_ROOM,
    )

    with pytest.raises(InvalidReferenceError, match="must be a laboratory"):
        make_course_session(
            db,
            context,
            component_type=ComponentType.LABORATORY,
            required_room_id=context.room.id,
        )


def test_specific_room_must_have_enough_capacity(db: Session) -> None:
    context = make_scheduling_context(db)
    small_room = make_room(
        db,
        context.resources.hierarchy.faculty.id,
        capacity=20,
    )

    with pytest.raises(BusinessRuleError, match="too small"):
        make_course_session(
            db,
            context,
            max_students=30,
            required_room_id=small_room.id,
        )


def test_offering_becomes_ready_only_with_exact_periods_groups_and_staff(
    db: Session,
) -> None:
    context = make_scheduling_context(db, lecture_periods=2)
    session = make_course_session(db, context)

    with pytest.raises(BusinessRuleError, match="student group"):
        update_course_offering(
            db,
            context.offering.id,
            CourseOfferingUpdate(status=CourseOfferingStatus.READY),
        )

    attach_group(db, session, context.cohort)
    attach_staff(db, session, context.staff_member)
    ready = update_course_offering(
        db,
        context.offering.id,
        CourseOfferingUpdate(status=CourseOfferingStatus.READY),
    )
    assert ready.status == CourseOfferingStatus.READY

    with pytest.raises(ResourceInUseError, match="DRAFT"):
        create_course_session_group(
            db,
            CourseSessionGroupCreate(
                course_session_id=session.id,
                student_group_id=context.cohort.id,
            ),
        )
