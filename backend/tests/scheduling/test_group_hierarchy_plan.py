from collections import defaultdict

from app.models.enums import StudentGroupType
from app.services.resources.student_group import build_student_group_hierarchy_plan


def test_group_plan_uses_profile_limits_and_preserves_parent_totals() -> None:
    plan = build_student_group_hierarchy_plan(
        cohort_name="G1",
        student_count=91,
        max_lecture_students=60,
        max_numerical_students=40,
        max_lab_students=20,
    )
    by_name = {row.name: row for row in plan}
    child_totals: defaultdict[str, int] = defaultdict(int)
    for row in plan:
        if row.parent_name is not None:
            child_totals[row.parent_name] += row.student_count

    assert (
        max(row.student_count for row in plan if row.group_type == StudentGroupType.LECTURE_GROUP)
        <= 60
    )
    assert (
        max(row.student_count for row in plan if row.group_type == StudentGroupType.NUMERICAL_GROUP)
        <= 40
    )
    assert (
        max(row.student_count for row in plan if row.group_type == StudentGroupType.LAB_GROUP) <= 20
    )
    assert all(
        child_totals[parent_name] == parent.student_count
        for parent_name, parent in by_name.items()
        if parent.group_type != StudentGroupType.LAB_GROUP
    )
