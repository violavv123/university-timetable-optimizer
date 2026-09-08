from __future__ import annotations

from collections.abc import Iterable

from app.scheduling.domain import (
    CandidateRoom,
    RoomStrategy,
    SessionOccurrence,
    StartCandidate,
)


def occurrence_difficulty_key(
    occurrence: SessionOccurrence,
) -> tuple[bool, int, int, int, int, int]:

    return (
        occurrence.required_room_id is None,
        -occurrence.demand,
        -occurrence.duration_slots,
        len(occurrence.allowed_start_room_pairs),
        occurrence.session_id,
        occurrence.occurrence_number,
    )


def decreasing_occurrence_order(
    occurrences: Iterable[SessionOccurrence],
) -> tuple[SessionOccurrence, ...]:

    return tuple(sorted(occurrences, key=occurrence_difficulty_key))


def ordered_rooms(
    occurrence: SessionOccurrence,
    start: StartCandidate,
    rooms: Iterable[CandidateRoom],
    strategy: RoomStrategy,
) -> tuple[CandidateRoom, ...]:
    feasible = tuple(
        room
        for room in rooms
        if (start.start_slot_id, room.id) in occurrence.allowed_start_room_pairs
    )
    if strategy == RoomStrategy.BFD:
        return tuple(
            sorted(
                feasible,
                key=lambda room: (
                    room.capacity - occurrence.demand,
                    room.capacity,
                    room.code,
                ),
            )
        )
    # First fit scans a stable room order and selects the first feasible room.
    # The occurrences, rather than the rooms, are sorted decreasingly.
    return tuple(
        sorted(
            feasible,
            key=lambda room: (room.code, room.id),
        )
    )


def first_fit_decreasing(
    occurrence: SessionOccurrence,
    start: StartCandidate,
    rooms: Iterable[CandidateRoom],
) -> tuple[CandidateRoom, ...]:
    return ordered_rooms(occurrence, start, rooms, RoomStrategy.FFD)


def best_fit_decreasing(
    occurrence: SessionOccurrence,
    start: StartCandidate,
    rooms: Iterable[CandidateRoom],
) -> tuple[CandidateRoom, ...]:
    return ordered_rooms(occurrence, start, rooms, RoomStrategy.BFD)


__all__ = [
    "best_fit_decreasing",
    "decreasing_occurrence_order",
    "first_fit_decreasing",
    "occurrence_difficulty_key",
    "ordered_rooms",
]
