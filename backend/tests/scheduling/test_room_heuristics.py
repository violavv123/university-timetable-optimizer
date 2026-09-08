from dataclasses import replace

from app.scheduling.domain import RoomStrategy
from app.scheduling.room_heuristics import decreasing_occurrence_order, ordered_rooms
from tests.scheduling.factories import occurrence, room, slot, start


def test_decreasing_order_places_larger_occurrence_first() -> None:
    time_slot = slot(1, day=1, index=0, start_minute=8 * 60, week_index=0)
    candidate = start(time_slot)
    classroom = room(1, "611", 100)
    smaller = occurrence(1, candidate, classroom, demand=30)
    larger = occurrence(2, candidate, classroom, demand=80)

    assert decreasing_occurrence_order((smaller, larger)) == (larger, smaller)


def test_first_fit_uses_stable_order_and_best_fit_minimizes_waste() -> None:
    time_slot = slot(1, day=1, index=0, start_minute=8 * 60, week_index=0)
    candidate = start(time_slot)
    large = room(1, "201", 100)
    tight = room(2, "611", 60)
    session = occurrence(1, candidate, large, demand=55)
    session = replace(
        session,
        compatible_room_ids=frozenset({large.id, tight.id}),
        allowed_start_room_pairs=frozenset(
            {
                (candidate.start_slot_id, large.id),
                (candidate.start_slot_id, tight.id),
            }
        ),
    )

    assert ordered_rooms(session, candidate, (tight, large), RoomStrategy.FFD)[0] == large
    assert ordered_rooms(session, candidate, (large, tight), RoomStrategy.BFD)[0] == tight
