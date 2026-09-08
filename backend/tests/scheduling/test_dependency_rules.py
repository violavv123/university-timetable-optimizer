from app.models.enums import DependencyType
from app.scheduling.dependency_rules import dependency_satisfied
from app.scheduling.domain import SessionDependency
from tests.scheduling.factories import slot, start


def dependency(kind: DependencyType) -> SessionDependency:
    return SessionDependency(
        id=1,
        predecessor_session_id=1,
        successor_session_id=2,
        dependency_type=kind,
    )


def test_consecutive_dependency_uses_adjacent_slots_on_same_day() -> None:
    predecessor = start(slot(1, day=1, index=0, start_minute=480, week_index=0))
    successor = start(slot(2, day=1, index=1, start_minute=525, week_index=1))

    assert dependency_satisfied(
        dependency(DependencyType.CONSECUTIVE),
        (predecessor,),
        successor,
    )


def test_different_day_must_differ_from_every_predecessor() -> None:
    monday = start(slot(1, day=1, index=0, start_minute=480, week_index=0))
    tuesday = start(slot(2, day=2, index=0, start_minute=480, week_index=2))

    assert not dependency_satisfied(
        dependency(DependencyType.DIFFERENT_DAY),
        (monday, tuesday),
        tuesday,
    )
