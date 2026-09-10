from types import SimpleNamespace

from app.services.timetable.export import _group_entries_by_program_and_level


def _entry(program_code: str, level_code: str) -> SimpleNamespace:
    level = SimpleNamespace(code=level_code, name=f"{level_code} level")
    program = SimpleNamespace(
        code=program_code,
        name=f"{program_code} programme",
        level=level,
    )
    curriculum = SimpleNamespace(program_semester=SimpleNamespace(study_program=program))
    session = SimpleNamespace(course_offering=SimpleNamespace(curriculum_course=curriculum))
    return SimpleNamespace(course_session=session)


def test_export_groups_entries_by_program_and_level() -> None:
    entries = (
        _entry("TIK", "MSC"),
        _entry("TIK", "BSC"),
        _entry("TIK", "MSC"),
    )

    sections = _group_entries_by_program_and_level(entries)

    assert [(key, len(section)) for key, section in sections] == [
        (("TIK — TIK programme", "BSC — BSC level"), 1),
        (("TIK — TIK programme", "MSC — MSC level"), 2),
    ]
