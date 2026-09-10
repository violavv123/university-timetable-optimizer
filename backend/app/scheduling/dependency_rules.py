from __future__ import annotations

from collections.abc import Iterable

from app.models.enums import DependencyType
from app.scheduling.domain import SessionDependency, StartCandidate


def dependency_satisfied(
    dependency: SessionDependency,
    predecessor_starts: Iterable[StartCandidate],
    successor_start: StartCandidate,
) -> bool:

    predecessors = tuple(predecessor_starts)
    if not predecessors:
        return False
    if dependency.dependency_type == DependencyType.DIFFERENT_DAY:
        return all(
            predecessor.day_of_week != successor_start.day_of_week for predecessor in predecessors
        )
    if dependency.dependency_type == DependencyType.SAME_DAY:
        return any(
            predecessor.day_of_week == successor_start.day_of_week for predecessor in predecessors
        )
    for predecessor in predecessors:
        predecessor_end = predecessor.week_index + len(predecessor.occupied_slot_ids)
        if dependency.dependency_type == DependencyType.CONSECUTIVE:
            if (
                predecessor.day_of_week == successor_start.day_of_week
                and predecessor_end == successor_start.week_index
            ):
                return True
            continue
        gap = successor_start.week_index - predecessor_end
        if gap < 0:
            continue
        if dependency.min_gap_slots is not None and gap < dependency.min_gap_slots:
            continue
        if dependency.max_gap_slots is not None and gap > dependency.max_gap_slots:
            continue
        return True
    return False


__all__ = ["dependency_satisfied"]
