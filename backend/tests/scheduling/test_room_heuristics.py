from app.scheduling.domain import RoomStrategy
from app.scheduling.room_heuristics import ordered_rooms
from tests.scheduling.factories import make_input, with_rooms


def test_ffd_and_bfd_provide_distinct_room_orderings() -> None:
    data = make_input()
    occurrence = with_rooms(data.occurrences[0], frozenset({1, 2}))
    start = occurrence.start_candidates[0]

    ffd = ordered_rooms(occurrence, start, data.rooms, RoomStrategy.FFD)
    bfd = ordered_rooms(occurrence, start, data.rooms, RoomStrategy.BFD)

    assert [room.id for room in ffd] == [2, 1]
    assert [room.id for room in bfd] == [1, 2]
