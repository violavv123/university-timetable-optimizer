from decimal import Decimal

import pytest
from app.core.exceptions import BusinessRuleError, ResourceInUseError
from app.models.enums import (
    SchedulingAlgorithm,
    TimetableRunStatus,
    TimetableSourceType,
)
from app.schemas.timetable_run import TimetableRunCreate, TimetableRunUpdate
from app.services.timetable.publication import publish_timetable_run
from app.services.timetable.timetable_run import (
    complete_timetable_run,
    create_timetable_run,
    start_timetable_run,
    update_timetable_run,
)
from sqlalchemy.orm import Session
from tests.services.scheduling_input.factories import make_scheduling_context
from tests.services.timetable.factories import (
    TimetableContext,
    complete_valid_manual_run,
    make_manual_entry,
    make_profile_slots,
    make_ready_timetable_context,
    make_timetable_run,
)

pytestmark = pytest.mark.integration


def test_run_requires_active_slots_and_generated_run_requires_algorithm(
    db: Session,
) -> None:
    scheduling = make_scheduling_context(db)

    with pytest.raises(BusinessRuleError, match="active time slots"):
        make_timetable_run(db, scheduling)

    make_profile_slots(db, scheduling, count=2)
    payload = TimetableRunCreate.model_construct(
        academic_term_id=scheduling.resources.academic_term.id,
        scheduling_profile_id=scheduling.profile.id,
        name="Generated without algorithm",
        source_type=TimetableSourceType.GENERATED,
        algorithm=None,
        parameters={},
    )
    with pytest.raises(BusinessRuleError, match="require a scheduling algorithm"):
        create_timetable_run(db, payload)


def test_new_run_normalizes_name_and_owns_initial_state(db: Session) -> None:
    context = make_ready_timetable_context(db)
    run = context.run

    updated = update_timetable_run(
        db,
        run.id,
        TimetableRunUpdate(name="  First   approved   input  "),
    )

    assert updated.name == "First approved input"
    assert updated.status == TimetableRunStatus.PENDING
    assert updated.objective_score is None
    assert updated.hard_conflicts == 0
    assert updated.soft_penalty is None
    assert updated.execution_time_ms is None
    assert updated.is_published is False


def test_run_configuration_is_immutable_after_entries_exist(db: Session) -> None:
    context = make_ready_timetable_context(db)
    make_manual_entry(db, context)

    with pytest.raises(ResourceInUseError, match="with entries"):
        update_timetable_run(
            db,
            context.run.id,
            TimetableRunUpdate(name="Changed too late"),
        )


def test_run_cannot_succeed_when_required_occurrences_are_missing(
    db: Session,
) -> None:
    context = make_ready_timetable_context(
        db,
        weekly_frequency=2,
        duration_slots=1,
    )
    make_manual_entry(db, context, occurrence_number=1)
    start_timetable_run(db, context.run.id)

    with pytest.raises(BusinessRuleError, match="hard conflicts") as exc_info:
        complete_timetable_run(
            db,
            context.run.id,
            status=TimetableRunStatus.SUCCEEDED,
            objective_score=Decimal("1"),
        )

    assert exc_info.value.details["hard_conflicts"] > 0


def test_only_a_successful_valid_run_can_be_published(db: Session) -> None:
    context = make_ready_timetable_context(db)

    with pytest.raises(BusinessRuleError, match="Only a SUCCEEDED"):
        publish_timetable_run(db, context.run.id)


def test_publishing_new_run_unpublishes_previous_run_for_term_and_profile(
    db: Session,
) -> None:
    first_context = make_ready_timetable_context(db)
    make_manual_entry(db, first_context)
    complete_valid_manual_run(db, first_context)
    first = publish_timetable_run(db, first_context.run.id)
    assert first.is_published is True

    second_run = make_timetable_run(
        db,
        first_context.scheduling,
        name="Replacement run",
        source_type=TimetableSourceType.MANUAL,
        algorithm=SchedulingAlgorithm.CP_SAT,
    )
    second_context = TimetableContext(
        first_context.scheduling,
        first_context.session,
        first_context.slots,
        second_run,
    )
    make_manual_entry(db, second_context)
    complete_valid_manual_run(db, second_context)
    second = publish_timetable_run(db, second_run.id)

    db.refresh(first)
    assert first.is_published is False
    assert second.is_published is True
