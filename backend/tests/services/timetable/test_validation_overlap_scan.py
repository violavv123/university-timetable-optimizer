from types import SimpleNamespace

from app.services.timetable.validation import _collect_resource_overlap_conflicts


class FakeDatabase:
    def __init__(self, groups: dict[int, object]) -> None:
        self.groups = groups

    def get(self, model: object, identifier: int) -> object:
        return self.groups.get(identifier)


def _resolved(entry_id: int, room_id: int, group_id: int) -> tuple[int, object]:
    return entry_id, SimpleNamespace(
        room=SimpleNamespace(id=room_id),
        slots=(SimpleNamespace(id=1),),
        staff_ids=frozenset(),
        group_ids=frozenset({group_id}),
    )


def test_overlap_scan_does_not_confuse_sibling_groups_with_overlaps() -> None:
    groups = {
        1: SimpleNamespace(id=1, parent_group_id=None),
        2: SimpleNamespace(id=2, parent_group_id=1),
        3: SimpleNamespace(id=3, parent_group_id=1),
    }
    conflicts: list[object] = []

    _collect_resource_overlap_conflicts(
        FakeDatabase(groups),  # type: ignore[arg-type]
        resolved_by_entry=dict(
            [_resolved(10, 20, 2), _resolved(11, 21, 3)],
        ),
        conflicts=conflicts,  # type: ignore[arg-type]
    )

    assert conflicts == []
