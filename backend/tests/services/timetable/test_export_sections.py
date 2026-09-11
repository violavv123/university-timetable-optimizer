from types import SimpleNamespace

from app.services.timetable.export import (
    _group_entries_by_faculty_program_level_and_semester,
)


def _entry(program_code: str, level_code: str, semester_number: int) -> SimpleNamespace:
    level = SimpleNamespace(code=level_code, name=f"{level_code} level")
    faculty = SimpleNamespace(code="FIEK", name="Faculty of Electrical Engineering")
    program = SimpleNamespace(
        code=program_code,
        name=f"{program_code} programme",
        level=level,
        faculty=faculty,
    )
    curriculum = SimpleNamespace(
        program_semester=SimpleNamespace(
            study_program=program,
            semester_number=semester_number,
        )
    )
    session = SimpleNamespace(
        course_offering=SimpleNamespace(curriculum_course=curriculum)
    )
    return SimpleNamespace(course_session=session)


def test_export_groups_entries_by_program_and_level() -> None:
    entries = (
        _entry("TIK", "MSC", 1),
        _entry("TIK", "BSC", 2),
        _entry("TIK", "MSC", 3),
    )

    sections = _group_entries_by_faculty_program_level_and_semester(entries)

    assert [(key, len(section)) for key, section in sections] == [
        (
            (
                "FIEK — Faculty of Electrical Engineering",
                "TIK — TIK programme",
                "BSC — BSC level",
                "Semester 2",
            ),
            1,
        ),
        (
            (
                "FIEK — Faculty of Electrical Engineering",
                "TIK — TIK programme",
                "MSC — MSC level",
                "Semester 1",
            ),
            1,
        ),
        (
            (
                "FIEK — Faculty of Electrical Engineering",
                "TIK — TIK programme",
                "MSC — MSC level",
                "Semester 3",
            ),
            1,
        ),
    ]
