from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from math import ceil

from app.models.enums import AvailabilityType, TimeConstraintType
from app.scheduling.domain import (
    AvailabilityWindow,
    CandidateRoom,
    SchedulingInput,
    SessionOccurrence,
    SolverAssignment,
    StartCandidate,
)


@dataclass(frozen=True, slots=True)
class TimetableMetrics:
    assigned_occurrences: int
    unassigned_occurrences: int
    rooms_used: int
    unused_room_seats: int
    student_gap_slots: int
    staff_gap_slots: int
    late_bsc_slots: int
    hard_conflicts: int
    soft_penalty: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def _contains(window_start: int, window_end: int, start: int, end: int) -> bool:
    return window_start <= start and end <= window_end


def _overlaps(window_start: int, window_end: int, start: int, end: int) -> bool:
    return window_start < end and window_end > start


def _availability_penalty(
    windows: tuple[AvailabilityWindow, ...],
    start: StartCandidate,
) -> int:
    penalty = 0
    avoid = (
        window
        for window in windows
        if window.availability_type == AvailabilityType.AVOID
        and window.day_of_week == start.day_of_week
    )
    penalty += sum(
        window.preference_weight
        for window in avoid
        if _overlaps(
            window.start_minute,
            window.end_minute,
            start.start_minute,
            start.end_minute,
        )
    )
    preferred = tuple(
        window for window in windows if window.availability_type == AvailabilityType.PREFERRED
    )
    if preferred and not any(
        window.day_of_week == start.day_of_week
        and _contains(
            window.start_minute,
            window.end_minute,
            start.start_minute,
            start.end_minute,
        )
        for window in preferred
    ):
        penalty += max(window.preference_weight for window in preferred)
    return penalty


def placement_penalty(
    data: SchedulingInput,
    occurrence: SessionOccurrence,
    start: StartCandidate,
    room: CandidateRoom,
) -> int:
    penalty = 0
    for constraint in occurrence.time_constraints:
        if constraint.constraint_type != TimeConstraintType.PREFERRED_WINDOW:
            continue
        if not (
            constraint.day_of_week in {None, start.day_of_week}
            and _contains(
                constraint.start_minute,
                constraint.end_minute,
                start.start_minute,
                start.end_minute,
            )
        ):
            penalty += constraint.preference_weight

    penalty += sum(
        _availability_penalty(data.staff_availability.get(staff_id, ()), start)
        for staff_id in occurrence.staff_ids
    )
    penalty += _availability_penalty(
        data.room_availability.get(room.id, ()),
        start,
    )

    preferences = data.program_room_preferences.get(occurrence.program_id, {})
    if preferences:
        best_score = max(preferences.values())
        selected_score = preferences.get(room.id, 0)
        penalty += (best_score - selected_score) * data.weights.preferred_room

    historical_rooms = data.historical_rooms.get(occurrence.session_id)
    if historical_rooms and room.id not in historical_rooms:
        penalty += data.weights.historical_room

    penalty += max(0, room.capacity - occurrence.demand) * data.weights.unused_seat

    if occurrence.level_code.upper() == "BSC" and start.end_minute > 17 * 60:
        late_minutes = start.end_minute - max(start.start_minute, 17 * 60)
        penalty += ceil(late_minutes / data.slot_minutes) * data.weights.late_hour
    return penalty


def _gap_slots(
    data: SchedulingInput,
    occupied_by_resource: dict[int, set[int]],
) -> int:
    slot_by_id = data.slot_by_id
    positions_by_day: dict[int, list[int]] = defaultdict(list)
    for slot in data.slots:
        positions_by_day[slot.day_of_week].append(slot.id)
    ordered_days = {
        day: tuple(sorted(slot_ids, key=lambda slot_id: slot_by_id[slot_id].slot_index))
        for day, slot_ids in positions_by_day.items()
    }
    total = 0
    for occupied in occupied_by_resource.values():
        for slot_ids in ordered_days.values():
            indexes = [index for index, slot_id in enumerate(slot_ids) if slot_id in occupied]
            if len(indexes) < 2:
                continue
            total += sum(
                slot_ids[index] not in occupied for index in range(min(indexes), max(indexes) + 1)
            )
    return total


def calculate_metrics(
    data: SchedulingInput,
    assignments: tuple[SolverAssignment, ...],
    *,
    hard_conflicts: int = 0,
) -> TimetableMetrics:
    occurrence_by_key = data.occurrence_by_key
    room_by_id = data.room_by_id
    student_occupied: dict[int, set[int]] = defaultdict(set)
    staff_occupied: dict[int, set[int]] = defaultdict(set)
    rooms_used: set[int] = set()
    unused_room_seats = 0
    late_bsc_slots = 0
    placement_total = 0

    for assignment in assignments:
        occurrence = occurrence_by_key.get(assignment.key)
        room = room_by_id.get(assignment.room_id)
        if occurrence is None or room is None:
            continue
        start = next(
            (
                candidate
                for candidate in occurrence.start_candidates
                if candidate.start_slot_id == assignment.start_slot_id
            ),
            None,
        )
        if start is None:
            continue
        rooms_used.add(room.id)
        unused_room_seats += max(0, room.capacity - occurrence.demand)
        if occurrence.level_code.upper() == "BSC" and start.end_minute > 17 * 60:
            late_minutes = start.end_minute - max(start.start_minute, 17 * 60)
            late_bsc_slots += ceil(late_minutes / data.slot_minutes)
        placement_total += placement_penalty(data, occurrence, start, room)
        for resource_id in occurrence.student_resource_ids:
            student_occupied[resource_id].update(start.occupied_slot_ids)
        for staff_id in occurrence.staff_ids:
            staff_occupied[staff_id].update(start.occupied_slot_ids)

    student_gaps = _gap_slots(data, student_occupied)
    staff_gaps = _gap_slots(data, staff_occupied)
    soft_penalty = (
        placement_total
        + student_gaps * data.weights.student_gap
        + staff_gaps * data.weights.staff_gap
    )
    return TimetableMetrics(
        assigned_occurrences=len(assignments),
        unassigned_occurrences=max(0, len(data.occurrences) - len(assignments)),
        rooms_used=len(rooms_used),
        unused_room_seats=unused_room_seats,
        student_gap_slots=student_gaps,
        staff_gap_slots=staff_gaps,
        late_bsc_slots=late_bsc_slots,
        hard_conflicts=hard_conflicts,
        soft_penalty=soft_penalty,
    )


__all__ = ["TimetableMetrics", "calculate_metrics", "placement_penalty"]
