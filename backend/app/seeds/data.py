from __future__ import annotations

from collections import defaultdict
from datetime import date, time
from decimal import Decimal
from math import ceil
from typing import Any

from app.seeds.catalog import (
    ACTIVE_PROGRAMS as CATALOG_ACTIVE_PROGRAMS,
    CO_LECTURERS as CATALOG_CO_LECTURERS,
    COURSE_SPECS as CATALOG_COURSE_SPECS,
    ELECTIVE_GROUP_SPECS as CATALOG_ELECTIVE_GROUP_SPECS,
    STAFF_SPECS as CATALOG_STAFF_SPECS,
)

SeedRow = dict[str, Any]
TERM_KEY = "2026/2027-SUMMER"

FACULTIES: list[SeedRow] = [
    {
        "key": "FIEK",
        "code": "FIEK",
        "name": "Fakulteti i Inxhinierisë Elektrike dhe Kompjuterike",
        "is_active": True,
    }
]

LEVELS: list[SeedRow] = [
    {
        "key": "BSC",
        "code": "BSC",
        "name": "Bachelor i Shkencave",
        "semester_count": 6,
        "is_active": True,
    },
    {
        "key": "MSC",
        "code": "MSC",
        "name": "Master i Shkencave",
        "semester_count": 4,
        "is_active": True,
    },
]

_PROGRAM_NAMES = {
    "IKS": "Inxhinieri Kompjuterike dhe Softuerike",
    "EAR": "Elektronikë, Automatikë dhe Robotikë",
    "TIK": "Teknologjitë e Informacionit dhe Komunikimit",
    "EE": "Elektroenergjetikë",
}

STUDY_PROGRAMS: list[SeedRow] = [
    {
        "key": f"{code}-{level}",
        "faculty_key": "FIEK",
        "level_key": level,
        "code": code,
        "name": name,
        "is_active": True,
    }
    for code, name in _PROGRAM_NAMES.items()
    for level in ("BSC", "MSC")
]

PROGRAM_SEMESTERS: list[SeedRow] = [
    {
        "key": f"{program['key']}-S{number}",
        "study_program_key": program["key"],
        "semester_number": number,
        "is_active": True,
    }
    for program in STUDY_PROGRAMS
    for number in range(1, 7 if program["level_key"] == "BSC" else 5)
]

ACADEMIC_YEARS: list[SeedRow] = [
    {
        "key": "2026/2027",
        "name": "2026/2027",
        "start_date": date(2026, 10, 1),
        "end_date": date(2027, 9, 30),
        "is_current": True,
    }
]

ACADEMIC_TERMS: list[SeedRow] = [
    {
        "key": "2026/2027-WINTER",
        "academic_year_key": "2026/2027",
        "name": "Semestri dimëror 2026/2027",
        "term_type": "WINTER",
        "start_date": date(2026, 10, 1),
        "end_date": date(2027, 1, 31),
        "is_active": True,
    },
    {
        "key": TERM_KEY,
        "academic_year_key": "2026/2027",
        "name": "Semestri veror 2026/2027",
        "term_type": "SUMMER",
        "start_date": date(2027, 2, 15),
        "end_date": date(2027, 6, 30),
        "is_active": True,
    },
]

# code, program semester, name, type, elective group, ECTS, L/N/Lab,
# lecturer, assistant, offered in this test instance
_COURSE_SPECS = list(CATALOG_COURSE_SPECS)
_ELECTIVE_GROUP_SPECS = list(CATALOG_ELECTIVE_GROUP_SPECS)

ELECTIVE_GROUPS: list[SeedRow] = [
    {
        "key": key,
        "program_semester_key": semester,
        "name": name,
        "required_choices": choices,
        "is_active": True,
    }
    for key, semester, name, choices in _ELECTIVE_GROUP_SPECS
]

COURSES: list[SeedRow] = [
    {"key": spec[0], "code": spec[0], "name": spec[2], "is_active": True} for spec in _COURSE_SPECS
]

CURRICULUM_COURSES: list[SeedRow] = [
    {
        "key": f"{semester}:{code}",
        "program_semester_key": semester,
        "course_key": code,
        "course_type": course_type,
        "elective_group_key": elective_group,
        "ects": Decimal(str(ects)),
        "lecture_periods_per_week": lecture,
        "numerical_periods_per_week": numerical,
        "laboratory_periods_per_week": laboratory,
        "requires_timetable": requires_timetable,
        "is_active": True,
    }
    for (
        code,
        semester,
        _name,
        course_type,
        elective_group,
        ects,
        lecture,
        numerical,
        laboratory,
        _lecturer,
        _assistant,
        _offered,
        requires_timetable,
    ) in _COURSE_SPECS
]

_STAFF_SPECS = list(CATALOG_STAFF_SPECS)

STAFF_MEMBERS: list[SeedRow] = [
    {
        "key": key,
        "faculty_key": "FIEK",
        "first_name": first,
        "last_name": last,
        "email": f"{key}@fiek.example",
        "academic_title": title,
        "staff_type": staff_type,
        "is_active": True,
    }
    for key, first, last, title, staff_type in _STAFF_SPECS
]

_COURSE_TEACHERS = {spec[0]: (spec[9], spec[10]) for spec in _COURSE_SPECS}

# Multiple names in the official curriculum are preserved as co-lecturer
# qualifications and as additional session staff for lecture components.
_CO_LECTURERS: dict[str, tuple[str, ...]] = dict(CATALOG_CO_LECTURERS)

_qualification_rows: dict[tuple[str, str], SeedRow] = {}
for _course_key, (_lecturer_key, _assistant_key) in _COURSE_TEACHERS.items():
    for _staff_key, _can_lecture, _can_assist in (
        (_lecturer_key, True, _lecturer_key == _assistant_key),
        (_assistant_key, False, True),
    ):
        _pair = (_staff_key, _course_key)
        _row = _qualification_rows.setdefault(
            _pair,
            {
                "key": f"{_staff_key}:{_course_key}",
                "staff_member_key": _staff_key,
                "course_key": _course_key,
                "can_lecture": False,
                "can_assist": False,
                "is_active": True,
            },
        )
        _row["can_lecture"] = _row["can_lecture"] or _can_lecture
        _row["can_assist"] = _row["can_assist"] or _can_assist
    for _co_lecturer_key in _CO_LECTURERS.get(_course_key, ()):
        _pair = (_co_lecturer_key, _course_key)
        _row = _qualification_rows.setdefault(
            _pair,
            {
                "key": f"{_co_lecturer_key}:{_course_key}",
                "staff_member_key": _co_lecturer_key,
                "course_key": _course_key,
                "can_lecture": False,
                "can_assist": False,
                "is_active": True,
            },
        )
        _row["can_lecture"] = True

STAFF_COURSES: list[SeedRow] = list(_qualification_rows.values())

# These recurring windows are explicit demonstration input, not an assertion
# of official personal availability. Every seeded staff member has complete,
# non-overlapping coverage for every teaching day and one soft preferred window
# per week. Blerim's Monday window demonstrates the shorter 08:00-15:00 case.
_DAILY_AVAILABILITY_PATTERNS = (
    (time(8, 0), time(20, 0)),
    (time(8, 45), time(20, 0)),
    (time(8, 0), time(18, 30)),
    (time(9, 30), time(20, 0)),
    (time(8, 0), time(20, 0)),
)
STAFF_AVAILABILITY: list[SeedRow] = []
for _staff_index, _staff_row in enumerate(STAFF_MEMBERS):
    _preferred_day = (_staff_index + 1) % 5 + 1
    for _day in range(1, 6):
        _start, _end = _DAILY_AVAILABILITY_PATTERNS[
            (_staff_index + _day - 1) % len(_DAILY_AVAILABILITY_PATTERNS)
        ]
        if _staff_row["key"] == "blerim-rexha" and _day == 1:
            _start, _end = time(8, 0), time(15, 0)
        _segments: tuple[tuple[time, time, str, int | None], ...]
        if _day == _preferred_day:
            if _staff_index % 2 == 0:
                _segments = (
                    (time(8, 0), time(12, 0), "PREFERRED", 5),
                    (time(12, 0), time(20, 0), "AVAILABLE", None),
                )
            else:
                _segments = (
                    (time(8, 0), time(17, 0), "AVAILABLE", None),
                    (time(17, 0), time(20, 0), "PREFERRED", 5),
                )
        else:
            _segments = ((_start, _end, "AVAILABLE", None),)
        for _segment_start, _segment_end, _availability_type, _weight in _segments:
            STAFF_AVAILABILITY.append(
                {
                    "key": f"{_staff_row['key']}:D{_day}:{_availability_type}",
                    "staff_member_key": _staff_row["key"],
                    "academic_term_key": TERM_KEY,
                    "day_of_week": _day,
                    "start_time": _segment_start,
                    "end_time": _segment_end,
                    "availability_type": _availability_type,
                    "preference_weight": _weight,
                }
            )

_ACTIVE_PROGRAMS = dict(CATALOG_ACTIVE_PROGRAMS)

MAX_LECTURE_STUDENTS = 60
MAX_NUMERICAL_STUDENTS = 40
MAX_LAB_STUDENTS = 20


def _split(total: int, maximum: int) -> list[int]:
    count = ceil(total / maximum)
    base, remainder = divmod(total, count)
    return [base + (index < remainder) for index in range(count)]


STUDENT_GROUPS: list[SeedRow] = []
_GROUPS_BY_SEMESTER: dict[str, dict[str, list[str]]] = {}
_GROUP_PARENT: dict[str, str | None] = {}
_GROUP_SIZE: dict[str, int] = {}

for _semester_key, _cohort_size in _ACTIVE_PROGRAMS.items():
    _cohort_key = f"{_semester_key}-COHORT"
    _GROUPS_BY_SEMESTER[_semester_key] = {
        "COHORT": [_cohort_key],
        "LECTURE": [],
        "NUMERICAL": [],
        "LABORATORY": [],
    }

    def _add_group(
        key: str,
        name: str,
        parent: str | None,
        group_type: str,
        size: int,
        semester_key: str = _semester_key,
    ) -> None:
        STUDENT_GROUPS.append(
            {
                "key": key,
                "program_semester_key": semester_key,
                "academic_term_key": TERM_KEY,
                "parent_group_key": parent,
                "name": name,
                "group_type": group_type,
                "student_count": size,
                "is_active": True,
            }
        )
        _GROUP_PARENT[key] = parent
        _GROUP_SIZE[key] = size

    _add_group(_cohort_key, "Cohort", None, "COHORT", _cohort_size)
    _is_bachelor = "-BSC-" in _semester_key
    _lecture_sizes = (
        _split(_cohort_size, ceil(_cohort_size / 2))
        if _is_bachelor
        else _split(_cohort_size, MAX_LECTURE_STUDENTS)
    )
    for _lecture_no, _lecture_size in enumerate(_lecture_sizes, start=1):
        _lecture_key = f"{_semester_key}-G{_lecture_no}"
        _add_group(_lecture_key, f"G{_lecture_no}", _cohort_key, "LECTURE_GROUP", _lecture_size)
        _GROUPS_BY_SEMESTER[_semester_key]["LECTURE"].append(_lecture_key)
        _numerical_sizes = (
            _split(_lecture_size, ceil(_lecture_size / 2))
            if _is_bachelor
            else _split(_lecture_size, MAX_NUMERICAL_STUDENTS)
        )
        for _numerical_no, _numerical_size in enumerate(_numerical_sizes, start=1):
            _letter = chr(ord("a") + _numerical_no - 1)
            _numerical_name = f"G{_lecture_no}{_letter}"
            _numerical_key = f"{_semester_key}-{_numerical_name.upper()}"
            _add_group(
                _numerical_key,
                _numerical_name,
                _lecture_key,
                "NUMERICAL_GROUP",
                _numerical_size,
            )
            _GROUPS_BY_SEMESTER[_semester_key]["NUMERICAL"].append(_numerical_key)
            _lab_sizes = (
                _split(_numerical_size, ceil(_numerical_size / 2))
                if _is_bachelor
                else _split(_numerical_size, MAX_LAB_STUDENTS)
            )
            for _lab_no, _lab_size in enumerate(_lab_sizes, start=1):
                _lab_key = f"{_numerical_key}-L{_lab_no}"
                _lab_suffix = "'" if _lab_no == 1 else '"'
                _add_group(
                    _lab_key,
                    f"{_numerical_name}{_lab_suffix}",
                    _numerical_key,
                    "LAB_GROUP",
                    _lab_size,
                )
                _GROUPS_BY_SEMESTER[_semester_key]["LABORATORY"].append(_lab_key)

ROOMS: list[SeedRow] = [
    {
        "key": "408",
        "faculty_key": "FIEK",
        "code": "408",
        "name": "Amfiteatri 408",
        "capacity": 300,
        "room_type": "GENERAL_ROOM",
        "status": "ACTIVE",
    },
    {
        "key": "411",
        "faculty_key": "FIEK",
        "code": "411",
        "name": "Amfiteatri 411",
        "capacity": 300,
        "room_type": "GENERAL_ROOM",
        "status": "ACTIVE",
    },
    {
        "key": "414",
        "faculty_key": "FIEK",
        "code": "414",
        "name": "Salla 414",
        "capacity": 150,
        "room_type": "GENERAL_ROOM",
        "status": "ACTIVE",
    },
    {
        "key": "415",
        "faculty_key": "FIEK",
        "code": "415",
        "name": "Salla 415",
        "capacity": 150,
        "room_type": "GENERAL_ROOM",
        "status": "ACTIVE",
    },
    {
        "key": "626",
        "faculty_key": "FIEK",
        "code": "626",
        "name": "Salla 626",
        "capacity": 60,
        "room_type": "GENERAL_ROOM",
        "status": "ACTIVE",
    },
    {
        "key": "611",
        "faculty_key": "FIEK",
        "code": "611",
        "name": "Salla 611",
        "capacity": 60,
        "room_type": "GENERAL_ROOM",
        "status": "ACTIVE",
    },
    {
        "key": "621",
        "faculty_key": "FIEK",
        "code": "621",
        "name": "Salla 621",
        "capacity": 60,
        "room_type": "GENERAL_ROOM",
        "status": "ACTIVE",
    },
    {
        "key": "636",
        "faculty_key": "FIEK",
        "code": "636",
        "name": "Salla 636",
        "capacity": 60,
        "room_type": "GENERAL_ROOM",
        "status": "ACTIVE",
    },
    {
        "key": "616",
        "faculty_key": "FIEK",
        "code": "616",
        "name": "Salla 616",
        "capacity": 60,
        "room_type": "GENERAL_ROOM",
        "status": "ACTIVE",
    },
    # Capacity 60 for room 201 is an explicit test assumption until confirmed.
    {
        "key": "201",
        "faculty_key": "FIEK",
        "code": "201",
        "name": "Salla 201",
        "capacity": 60,
        "room_type": "GENERAL_ROOM",
        "status": "ACTIVE",
    },
    {
        "key": "745",
        "faculty_key": "FIEK",
        "code": "745",
        "name": "Salla 745",
        "capacity": 40,
        "room_type": "GENERAL_ROOM",
        "status": "ACTIVE",
    },
    {
        "key": "311",
        "faculty_key": "FIEK",
        "code": "311",
        "name": "Salla 311",
        "capacity": 40,
        "room_type": "GENERAL_ROOM",
        "status": "ACTIVE",
    },
    {
        "key": "A3",
        "faculty_key": "FIEK",
        "code": "A3",
        "name": "Salla A3",
        "capacity": 40,
        "room_type": "GENERAL_ROOM",
        "status": "ACTIVE",
    },
    {
        "key": "310",
        "faculty_key": "FIEK",
        "code": "310",
        "name": "Salla 310",
        "capacity": 40,
        "room_type": "GENERAL_ROOM",
        "status": "ACTIVE",
    },
    # Additional teaching rooms appearing in the supplied FIEK timetables and
    # room inventory. Capacities not supplied by FIEK are conservative demo
    # assumptions and remain easy to edit here.
    {
        "key": "440",
        "faculty_key": "FIEK",
        "code": "440",
        "name": "Salla 440",
        "capacity": 40,
        "room_type": "GENERAL_ROOM",
        "status": "ACTIVE",
    },
    {
        "key": "523",
        "faculty_key": "FIEK",
        "code": "523",
        "name": "Salla 523",
        "capacity": 40,
        "room_type": "GENERAL_ROOM",
        "status": "ACTIVE",
    },
    {
        "key": "606",
        "faculty_key": "FIEK",
        "code": "606",
        "name": "Salla 606",
        "capacity": 40,
        "room_type": "GENERAL_ROOM",
        "status": "ACTIVE",
    },
    {
        "key": "A4",
        "faculty_key": "FIEK",
        "code": "A4",
        "name": "Salla A4",
        "capacity": 40,
        "room_type": "GENERAL_ROOM",
        "status": "ACTIVE",
    },
    {
        "key": "615",
        "faculty_key": "FIEK",
        "code": "615",
        "name": "Laboratori kompjuterik 615",
        "capacity": 24,
        "room_type": "LABORATORY",
        "status": "ACTIVE",
    },
    {
        "key": "LAB-EAR",
        "faculty_key": "FIEK",
        "code": "LAB-EAR",
        "name": "Laboratori i automatikës",
        "capacity": 20,
        "room_type": "LABORATORY",
        "status": "ACTIVE",
    },
    {
        "key": "LAB-TIK",
        "faculty_key": "FIEK",
        "code": "LAB-TIK",
        "name": "Laboratori i telekomunikacionit",
        "capacity": 20,
        "room_type": "LABORATORY",
        "status": "ACTIVE",
    },
    {
        "key": "LAB-ENERGY",
        "faculty_key": "FIEK",
        "code": "LAB-ENERGY",
        "name": "Laboratori i elektroenergjetikës",
        "capacity": 20,
        "room_type": "LABORATORY",
        "status": "ACTIVE",
    },
    {
        "key": "LAB-FIZ",
        "faculty_key": "FIEK",
        "code": "LAB-FIZ",
        "name": "Laboratori i fizikës",
        "capacity": 20,
        "room_type": "LABORATORY",
        "status": "ACTIVE",
    },
    {
        "key": "LAB-E",
        "faculty_key": "FIEK",
        "code": "LAB-E",
        "name": "Laboratori i elektronikës",
        "capacity": 20,
        "room_type": "LABORATORY",
        "status": "ACTIVE",
    },
    {
        "key": "LAB-A",
        "faculty_key": "FIEK",
        "code": "LAB-A",
        "name": "Laboratori i automatikës A",
        "capacity": 20,
        "room_type": "LABORATORY",
        "status": "ACTIVE",
    },
    {
        "key": "LAB-MATJE",
        "faculty_key": "FIEK",
        "code": "LAB-MATJE",
        "name": "Laboratori i matjeve",
        "capacity": 20,
        "room_type": "LABORATORY",
        "status": "ACTIVE",
    },
    {
        "key": "LAB-EL",
        "faculty_key": "FIEK",
        "code": "LAB-EL",
        "name": "Laboratori elektrik",
        "capacity": 20,
        "room_type": "LABORATORY",
        "status": "ACTIVE",
    },
    {
        "key": "LAB-OLD",
        "faculty_key": "FIEK",
        "code": "LAB-OLD",
        "name": "Laboratori jashtë përdorimit",
        "capacity": 20,
        "room_type": "LABORATORY",
        "status": "MAINTENANCE",
    },
]

ROOM_AVAILABILITY: list[SeedRow] = []
for _room in ROOMS:
    for _day in range(1, 6):
        _is_active = _room["status"] == "ACTIVE"
        _start = time(8, 0)
        _end = time(20, 0)
        # Two shorter windows exercise availability constraints without
        # overlapping another row for the same room and day.
        if _room["key"] == "408" and _day == 1:
            _start = time(10, 15)
        if _room["key"] == "615" and _day == 5:
            _end = time(12, 0)
        ROOM_AVAILABILITY.append(
            {
                "key": f"{_room['key']}:D{_day}:{'AVAILABLE' if _is_active else 'UNAVAILABLE'}",
                "room_key": _room["key"],
                "academic_term_key": TERM_KEY,
                "day_of_week": _day,
                "start_time": _start,
                "end_time": _end,
                "availability_type": "AVAILABLE" if _is_active else "UNAVAILABLE",
                "preference_weight": None,
            }
        )

PROGRAM_ROOM_PREFERENCES: list[SeedRow] = []
for _program in STUDY_PROGRAMS:
    _code = _program["code"]
    _level = _program["level_key"]
    _preferred = {
        "EAR": ("611", "201", "408", "626", "LAB-EAR"),
        "IKS": ("411", "621", "611", "408", "626"),
        "TIK": ("745", "636", "201"),
        "EE": ("636", "611", "408", "745"),
    }[_code]
    for _rank, _room_key in enumerate(_preferred):
        PROGRAM_ROOM_PREFERENCES.append(
            {
                "key": f"{_code}-{_level}:{_room_key}",
                "study_program_key": f"{_code}-{_level}",
                "room_key": _room_key,
                "penalty_weight": len(_preferred) - _rank + 2,
                "is_active": True,
            }
        )

SCHEDULING_PROFILES: list[SeedRow] = [
    {
        "key": "FIEK-45-MIN",
        "faculty_key": "FIEK",
        "name": "FIEK - orari standard 45 minuta",
        "slot_minutes": 45,
        "max_lecture_students": MAX_LECTURE_STUDENTS,
        "max_numerical_students": MAX_NUMERICAL_STUDENTS,
        "max_lab_students": MAX_LAB_STUDENTS,
        "preferred_room_weight": 6,
        "historical_room_weight": 3,
        "student_gap_weight": 5,
        "staff_gap_weight": 4,
        "late_hour_weight": 2,
        "is_active": True,
    }
]

TIME_SLOTS: list[SeedRow] = []
for _day in range(1, 6):
    for _slot_index in range(16):
        _start_minutes = 8 * 60 + 45 * _slot_index
        _end_minutes = _start_minutes + 45
        TIME_SLOTS.append(
            {
                "key": f"FIEK-45-MIN:D{_day}:S{_slot_index}",
                "scheduling_profile_key": "FIEK-45-MIN",
                "day_of_week": _day,
                "slot_index": _slot_index,
                "start_time": time(_start_minutes // 60, _start_minutes % 60),
                "end_time": time(_end_minutes // 60, _end_minutes % 60),
                "is_active": True,
            }
        )

_SPEC_BY_CODE = {spec[0]: spec for spec in _COURSE_SPECS}
_OFFERED_CODES = {spec[0] for spec in _COURSE_SPECS if spec[11]}
COURSE_OFFERINGS: list[SeedRow] = [
    {
        "key": f"{row['key']}:{TERM_KEY}",
        "curriculum_course_key": row["key"],
        "academic_term_key": TERM_KEY,
        "expected_students": _ACTIVE_PROGRAMS[row["program_semester_key"]],
        "status": "READY",
    }
    for row in CURRICULUM_COURSES
    if row["course_key"] in _OFFERED_CODES
]

COURSE_SESSIONS: list[SeedRow] = []
COURSE_SESSION_GROUPS: list[SeedRow] = []
COURSE_SESSION_STAFF: list[SeedRow] = []
_SESSION_BY_COMPONENT_GROUP: dict[tuple[str, str, str], str] = {}


def _add_session(
    curriculum: SeedRow,
    component: str,
    group_key: str,
    periods: int,
    staff_key: str,
) -> str:
    offering_key = f"{curriculum['key']}:{TERM_KEY}"
    group_label = group_key.removeprefix(f"{curriculum['program_semester_key']}-")
    session_name = f"{component.title()} {group_label}"
    session_key = f"{offering_key}:{session_name}"
    weekly_frequency = 1
    duration_slots = periods
    required_room_type = "LABORATORY" if component == "LABORATORY" else "GENERAL_ROOM"
    required_room_key = None
    COURSE_SESSIONS.append(
        {
            "key": session_key,
            "course_offering_key": offering_key,
            "name": session_name,
            "component_type": component,
            "weekly_frequency": weekly_frequency,
            "duration_slots": duration_slots,
            "max_students": _GROUP_SIZE[group_key],
            "required_room_type": required_room_type,
            "required_room_key": required_room_key,
            "is_splittable": False,
            "is_active": True,
        }
    )
    COURSE_SESSION_GROUPS.append(
        {
            "key": f"{session_key}:{group_key}",
            "course_session_key": session_key,
            "student_group_key": group_key,
        }
    )
    role = {
        "LECTURE": "LECTURER",
        "NUMERICAL": "NUMERICAL_INSTRUCTOR",
        "LABORATORY": "LAB_INSTRUCTOR",
    }[component]
    assigned_staff = [staff_key]
    if component == "LECTURE":
        assigned_staff.extend(_CO_LECTURERS.get(curriculum["course_key"], ()))
    for staff_index, assigned_staff_key in enumerate(dict.fromkeys(assigned_staff)):
        COURSE_SESSION_STAFF.append(
            {
                "key": f"{session_key}:{assigned_staff_key}",
                "course_session_key": session_key,
                "staff_member_key": assigned_staff_key,
                "teaching_role": role,
                "is_primary": staff_index == 0,
                "is_fixed": True,
            }
        )
    _SESSION_BY_COMPONENT_GROUP[(curriculum["key"], component, group_key)] = session_key
    return session_key


for _curriculum in CURRICULUM_COURSES:
    if _curriculum["course_key"] not in _OFFERED_CODES:
        continue
    _lecturer, _assistant = _COURSE_TEACHERS[_curriculum["course_key"]]
    _components = (
        ("LECTURE", "lecture_periods_per_week", _lecturer),
        ("NUMERICAL", "numerical_periods_per_week", _assistant),
        ("LABORATORY", "laboratory_periods_per_week", _assistant),
    )
    for _component, _period_field, _assigned_staff_key in _components:
        _periods = _curriculum[_period_field]
        if not _periods:
            continue
        for _group_key in _GROUPS_BY_SEMESTER[_curriculum["program_semester_key"]][_component]:
            _add_session(
                _curriculum,
                _component,
                _group_key,
                _periods,
                _assigned_staff_key,
            )

COURSE_SESSION_TIME_CONSTRAINTS: list[SeedRow] = []
for _session in COURSE_SESSIONS:
    _curriculum_key = _session["course_offering_key"].removesuffix(f":{TERM_KEY}")
    _semester_key = _curriculum_key.split(":", maxsplit=1)[0]
    _is_master = "-MSC-" in _semester_key
    _allowed_start = time(8, 0)
    _allowed_end = time(20, 0)
    COURSE_SESSION_TIME_CONSTRAINTS.append(
        {
            "key": f"{_session['key']}:ALLOWED",
            "course_session_key": _session["key"],
            "day_of_week": None,
            "start_time": _allowed_start,
            "end_time": _allowed_end,
            "constraint_type": "ALLOWED_WINDOW",
            "preference_weight": None,
        }
    )
    if _is_master:
        COURSE_SESSION_TIME_CONSTRAINTS.append(
            {
                "key": f"{_session['key']}:PREFERRED-EVENING",
                "course_session_key": _session["key"],
                "day_of_week": None,
                "start_time": time(17, 0),
                "end_time": time(20, 0),
                "constraint_type": "PREFERRED_WINDOW",
                "preference_weight": 8,
            }
        )

COURSE_SESSION_DEPENDENCIES: list[SeedRow] = []


def _ancestor_of_type(group_key: str, group_type: str) -> str:
    types = {row["key"]: row["group_type"] for row in STUDENT_GROUPS}
    current: str | None = group_key
    while current is not None:
        if types[current] == group_type:
            return current
        current = _GROUP_PARENT[current]
    raise KeyError(f"No {group_type} ancestor for {group_key}")


def _dependency(predecessor: str, successor: str, dependency_type: str) -> None:
    COURSE_SESSION_DEPENDENCIES.append(
        {
            "key": f"{predecessor}>{successor}:{dependency_type}",
            "predecessor_session_key": predecessor,
            "successor_session_key": successor,
            "dependency_type": dependency_type,
            "min_gap_slots": 0 if dependency_type == "PRECEDES" else None,
            "max_gap_slots": None,
        }
    )


for _curriculum in CURRICULUM_COURSES:
    if (
        _curriculum["course_key"] not in _OFFERED_CODES
        or not _curriculum["lecture_periods_per_week"]
    ):
        continue
    _semester_key = _curriculum["program_semester_key"]
    for _component in ("NUMERICAL", "LABORATORY"):
        if not _curriculum[f"{_component.lower()}_periods_per_week"]:
            continue
        for _group_key in _GROUPS_BY_SEMESTER[_semester_key][_component]:
            _lecture_group = _ancestor_of_type(_group_key, "LECTURE_GROUP")
            _lecture_session = _SESSION_BY_COMPONENT_GROUP[
                (_curriculum["key"], "LECTURE", _lecture_group)
            ]
            _child_session = _SESSION_BY_COMPONENT_GROUP[
                (_curriculum["key"], _component, _group_key)
            ]
            _dependency(_lecture_session, _child_session, "PRECEDES")

def validate_seed_data() -> None:
    """Validate schema-level and solver-critical invariants before any insert."""

    collections = (
        FACULTIES,
        LEVELS,
        STUDY_PROGRAMS,
        PROGRAM_SEMESTERS,
        ACADEMIC_YEARS,
        ACADEMIC_TERMS,
        COURSES,
        ELECTIVE_GROUPS,
        CURRICULUM_COURSES,
        STAFF_MEMBERS,
        STAFF_COURSES,
        STAFF_AVAILABILITY,
        STUDENT_GROUPS,
        ROOMS,
        ROOM_AVAILABILITY,
        PROGRAM_ROOM_PREFERENCES,
        SCHEDULING_PROFILES,
        TIME_SLOTS,
        COURSE_OFFERINGS,
        COURSE_SESSIONS,
        COURSE_SESSION_GROUPS,
        COURSE_SESSION_STAFF,
        COURSE_SESSION_TIME_CONSTRAINTS,
        COURSE_SESSION_DEPENDENCIES,
    )
    for rows in collections:
        keys = [row["key"] for row in rows]
        if len(keys) != len(set(keys)):
            raise ValueError("A seed collection contains duplicate stable keys.")

    levels = {row["key"]: row for row in LEVELS}
    programs = {row["key"]: row for row in STUDY_PROGRAMS}
    program_semesters = {row["key"]: row for row in PROGRAM_SEMESTERS}
    elective_groups = {row["key"]: row for row in ELECTIVE_GROUPS}
    curriculum = {row["key"]: row for row in CURRICULUM_COURSES}
    groups = {row["key"]: row for row in STUDENT_GROUPS}
    rooms = {row["key"]: row for row in ROOMS}
    offerings = {row["key"]: row for row in COURSE_OFFERINGS}
    sessions = {row["key"]: row for row in COURSE_SESSIONS}

    def assert_unique(rows: list[SeedRow], *fields: str) -> None:
        values = [tuple(row[field] for field in fields) for row in rows]
        if len(values) != len(set(values)):
            raise ValueError(f"Duplicate database natural key: {fields}")

    # Mirror every PostgreSQL UNIQUE constraint used by this package.
    assert_unique(FACULTIES, "code")
    assert_unique(LEVELS, "code")
    assert_unique(STUDY_PROGRAMS, "faculty_key", "level_key", "code")
    assert_unique(PROGRAM_SEMESTERS, "study_program_key", "semester_number")
    assert_unique(ACADEMIC_YEARS, "name")
    assert_unique(ACADEMIC_TERMS, "academic_year_key", "term_type")
    assert_unique(COURSES, "code")
    assert_unique(ELECTIVE_GROUPS, "program_semester_key", "name")
    assert_unique(CURRICULUM_COURSES, "program_semester_key", "course_key")
    assert_unique(STAFF_MEMBERS, "faculty_key", "first_name", "last_name")
    assert_unique(STAFF_COURSES, "staff_member_key", "course_key")
    assert_unique(
        STAFF_AVAILABILITY,
        "staff_member_key",
        "academic_term_key",
        "day_of_week",
        "start_time",
        "end_time",
        "availability_type",
    )
    assert_unique(STUDENT_GROUPS, "program_semester_key", "academic_term_key", "name")
    assert_unique(ROOMS, "faculty_key", "code")
    assert_unique(
        ROOM_AVAILABILITY,
        "room_key",
        "academic_term_key",
        "day_of_week",
        "start_time",
        "end_time",
        "availability_type",
    )
    assert_unique(PROGRAM_ROOM_PREFERENCES, "study_program_key", "room_key")
    assert_unique(SCHEDULING_PROFILES, "faculty_key", "name")
    assert_unique(TIME_SLOTS, "scheduling_profile_key", "day_of_week", "slot_index")
    assert_unique(TIME_SLOTS, "scheduling_profile_key", "day_of_week", "start_time")
    assert_unique(COURSE_OFFERINGS, "curriculum_course_key", "academic_term_key")
    assert_unique(COURSE_SESSIONS, "course_offering_key", "name")
    assert_unique(COURSE_SESSION_GROUPS, "course_session_key", "student_group_key")
    assert_unique(COURSE_SESSION_STAFF, "course_session_key", "staff_member_key")
    assert_unique(
        COURSE_SESSION_TIME_CONSTRAINTS,
        "course_session_key",
        "day_of_week",
        "start_time",
        "end_time",
        "constraint_type",
    )
    assert_unique(
        COURSE_SESSION_DEPENDENCIES,
        "predecessor_session_key",
        "successor_session_key",
        "dependency_type",
    )

    # Foreign-key existence checks fail with useful seed keys before SQLAlchemy
    # can fail with a less specific database exception.
    faculty_keys = {row["key"] for row in FACULTIES}
    level_keys = set(levels)
    program_keys = set(programs)
    semester_keys = set(program_semesters)
    year_keys = {row["key"] for row in ACADEMIC_YEARS}
    term_keys = {row["key"] for row in ACADEMIC_TERMS}
    course_keys = {row["key"] for row in COURSES}
    staff_keys = {row["key"] for row in STAFF_MEMBERS}
    room_keys = set(rooms)
    profile_keys = {row["key"] for row in SCHEDULING_PROFILES}
    reference_checks = (
        (STUDY_PROGRAMS, "faculty_key", faculty_keys),
        (STUDY_PROGRAMS, "level_key", level_keys),
        (PROGRAM_SEMESTERS, "study_program_key", program_keys),
        (ACADEMIC_TERMS, "academic_year_key", year_keys),
        (ELECTIVE_GROUPS, "program_semester_key", semester_keys),
        (CURRICULUM_COURSES, "program_semester_key", semester_keys),
        (CURRICULUM_COURSES, "course_key", course_keys),
        (STAFF_MEMBERS, "faculty_key", faculty_keys),
        (STAFF_COURSES, "staff_member_key", staff_keys),
        (STAFF_COURSES, "course_key", course_keys),
        (STAFF_AVAILABILITY, "staff_member_key", staff_keys),
        (STAFF_AVAILABILITY, "academic_term_key", term_keys),
        (STUDENT_GROUPS, "program_semester_key", semester_keys),
        (STUDENT_GROUPS, "academic_term_key", term_keys),
        (ROOMS, "faculty_key", faculty_keys),
        (ROOM_AVAILABILITY, "room_key", room_keys),
        (ROOM_AVAILABILITY, "academic_term_key", term_keys),
        (PROGRAM_ROOM_PREFERENCES, "study_program_key", program_keys),
        (PROGRAM_ROOM_PREFERENCES, "room_key", room_keys),
        (SCHEDULING_PROFILES, "faculty_key", faculty_keys),
        (TIME_SLOTS, "scheduling_profile_key", profile_keys),
        (COURSE_OFFERINGS, "curriculum_course_key", set(curriculum)),
        (COURSE_OFFERINGS, "academic_term_key", term_keys),
        (COURSE_SESSIONS, "course_offering_key", set(offerings)),
        (COURSE_SESSION_GROUPS, "course_session_key", set(sessions)),
        (COURSE_SESSION_GROUPS, "student_group_key", set(groups)),
        (COURSE_SESSION_STAFF, "course_session_key", set(sessions)),
        (COURSE_SESSION_STAFF, "staff_member_key", staff_keys),
        (COURSE_SESSION_TIME_CONSTRAINTS, "course_session_key", set(sessions)),
        (COURSE_SESSION_DEPENDENCIES, "predecessor_session_key", set(sessions)),
        (COURSE_SESSION_DEPENDENCIES, "successor_session_key", set(sessions)),
    )
    for rows, field, valid_keys in reference_checks:
        for row in rows:
            value = row[field]
            if value is not None and value not in valid_keys:
                raise ValueError(f"Missing reference {field}={value!r} in {row['key']}")

    for course in COURSES:
        if len(course["code"]) > 30 or len(course["name"]) > 200:
            raise ValueError(f"Course exceeds PostgreSQL VARCHAR limit: {course['key']}")
    for semester in PROGRAM_SEMESTERS:
        program = programs[semester["study_program_key"]]
        if not 1 <= semester["semester_number"] <= levels[program["level_key"]]["semester_count"]:
            raise ValueError(f"Invalid program semester: {semester['key']}")

    elective_members: dict[str, list[SeedRow]] = defaultdict(list)
    for row in CURRICULUM_COURSES:
        total_periods = sum(
            row[field]
            for field in (
                "lecture_periods_per_week",
                "numerical_periods_per_week",
                "laboratory_periods_per_week",
            )
        )
        if row["requires_timetable"] and total_periods == 0:
            raise ValueError(f"Timetabled course has no weekly periods: {row['key']}")
        if row["course_type"] == "MANDATORY" and row["elective_group_key"] is not None:
            raise ValueError(f"Mandatory course has elective group: {row['key']}")
        if row["course_type"] == "ELECTIVE":
            group_key = row["elective_group_key"]
            if (
                group_key is None
                or elective_groups[group_key]["program_semester_key"] != row["program_semester_key"]
            ):
                raise ValueError(f"Invalid elective group: {row['key']}")
            elective_members[group_key].append(row)

    offered_curricula = {row["curriculum_course_key"] for row in COURSE_OFFERINGS}
    for row in CURRICULUM_COURSES:
        is_offered = row["key"] in offered_curricula
        is_active_semester = row["program_semester_key"] in _ACTIVE_PROGRAMS
        if (
            is_active_semester
            and row["requires_timetable"]
            and row["course_type"] == "MANDATORY"
            and not is_offered
        ):
            raise ValueError(f"Active mandatory course is not offered: {row['key']}")
        if (not is_active_semester or not row["requires_timetable"]) and is_offered:
            raise ValueError(f"Inactive/non-timetabled course is offered: {row['key']}")
    for group_key, members in elective_members.items():
        if elective_groups[group_key]["program_semester_key"] not in _ACTIVE_PROGRAMS:
            continue
        selected = sum(member["key"] in offered_curricula for member in members)
        required = elective_groups[group_key]["required_choices"]
        if selected != required:
            raise ValueError(
                f"Elective selection mismatch for {group_key}: {selected} != {required}"
            )

    represented = {
        program_semesters[row["program_semester_key"]]["study_program_key"]
        for row in CURRICULUM_COURSES
        if row["key"] in offered_curricula
    }
    if represented != set(programs):
        raise ValueError(
            f"Not all FIEK programs have offerings: {sorted(set(programs) - represented)}"
        )

    type_limits = {
        "LECTURE_GROUP": MAX_LECTURE_STUDENTS,
        "NUMERICAL_GROUP": MAX_NUMERICAL_STUDENTS,
        "LAB_GROUP": MAX_LAB_STUDENTS,
    }
    for group in STUDENT_GROUPS:
        parent_key = group["parent_group_key"]
        if (
            group["group_type"] in type_limits
            and group["student_count"] > type_limits[group["group_type"]]
        ):
            raise ValueError(f"Oversized student group: {group['key']}")
        if parent_key is None:
            continue
        parent = groups[parent_key]
        if (
            parent["program_semester_key"] != group["program_semester_key"]
            or parent["academic_term_key"] != group["academic_term_key"]
            or group["student_count"] > parent["student_count"]
        ):
            raise ValueError(f"Invalid student-group parent: {group['key']}")
        seen = {group["key"]}
        current: str | None = parent_key
        while current is not None:
            if current in seen:
                raise ValueError(f"Student-group cycle at {group['key']}")
            seen.add(current)
            current = groups[current]["parent_group_key"]

    children: dict[str, list[SeedRow]] = defaultdict(list)
    for group in STUDENT_GROUPS:
        if group["parent_group_key"] is not None:
            children[group["parent_group_key"]].append(group)
    for parent_key, child_rows in children.items():
        if (
            sum(child["student_count"] for child in child_rows)
            != groups[parent_key]["student_count"]
        ):
            raise ValueError(f"Child-group totals do not match {parent_key}")

    qualifications = {(row["staff_member_key"], row["course_key"]): row for row in STAFF_COURSES}
    role_permission = {
        "LECTURER": "can_lecture",
        "NUMERICAL_INSTRUCTOR": "can_assist",
        "LAB_INSTRUCTOR": "can_assist",
    }
    session_groups: dict[str, list[str]] = defaultdict(list)
    for link in COURSE_SESSION_GROUPS:
        session_groups[link["course_session_key"]].append(link["student_group_key"])
    if set(session_groups) != set(sessions):
        raise ValueError("Every course session must have at least one student group.")

    for session in COURSE_SESSIONS:
        offering = offerings[session["course_offering_key"]]
        curriculum_row = curriculum[offering["curriculum_course_key"]]
        if session["weekly_frequency"] <= 0 or session["duration_slots"] <= 0:
            raise ValueError(f"Invalid session duration/frequency: {session['key']}")
        period_field = {
            "LECTURE": "lecture_periods_per_week",
            "NUMERICAL": "numerical_periods_per_week",
            "LABORATORY": "laboratory_periods_per_week",
        }[session["component_type"]]
        if session["weekly_frequency"] * session["duration_slots"] != curriculum_row[period_field]:
            raise ValueError(f"Session workload does not match curriculum: {session['key']}")
        for group_key in session_groups[session["key"]]:
            group = groups[group_key]
            if (
                group["program_semester_key"] != curriculum_row["program_semester_key"]
                or group["academic_term_key"] != offering["academic_term_key"]
            ):
                raise ValueError(f"Session-group mismatch: {session['key']}")
            if session["max_students"] < group["student_count"]:
                raise ValueError(f"Session capacity is below group size: {session['key']}")
        compatible = [
            room
            for room in ROOMS
            if room["status"] == "ACTIVE"
            and room["room_type"] == session["required_room_type"]
            and room["capacity"] >= session["max_students"]
        ]
        if not compatible:
            raise ValueError(f"No compatible active room for session: {session['key']}")
        required_room_key = session["required_room_key"]
        if required_room_key is not None and rooms[required_room_key] not in compatible:
            raise ValueError(f"Invalid required room: {session['key']}")

    for assignment in COURSE_SESSION_STAFF:
        session = sessions[assignment["course_session_key"]]
        offering = offerings[session["course_offering_key"]]
        course_key = curriculum[offering["curriculum_course_key"]]["course_key"]
        qualification = qualifications.get((assignment["staff_member_key"], course_key))
        if qualification is None or not qualification[role_permission[assignment["teaching_role"]]]:
            raise ValueError(f"Unqualified session staff: {assignment['key']}")

    for availability in (*STAFF_AVAILABILITY, *ROOM_AVAILABILITY):
        weighted = availability["availability_type"] in {"PREFERRED", "AVOID"}
        if availability["start_time"] >= availability["end_time"] or weighted != (
            availability["preference_weight"] is not None
        ):
            raise ValueError(f"Invalid availability row: {availability['key']}")

    def validate_weekly_coverage(
        rows: list[SeedRow], resource_field: str, expected_resources: set[str]
    ) -> None:
        windows: dict[tuple[str, int], list[SeedRow]] = defaultdict(list)
        for row in rows:
            windows[(row[resource_field], row["day_of_week"])].append(row)
        expected = {
            (resource_key, day) for resource_key in expected_resources for day in range(1, 6)
        }
        if set(windows) != expected:
            raise ValueError(f"Incomplete weekly availability for {resource_field}")
        for resource_day, day_rows in windows.items():
            ordered = sorted(day_rows, key=lambda row: row["start_time"])
            for previous, current in zip(
                ordered,
                ordered[1:],
                strict=False,
            ):
                if current["start_time"] < previous["end_time"]:
                    raise ValueError(f"Overlapping availability at {resource_day}")

    validate_weekly_coverage(STAFF_AVAILABILITY, "staff_member_key", staff_keys)
    validate_weekly_coverage(ROOM_AVAILABILITY, "room_key", room_keys)

    profile = SCHEDULING_PROFILES[0]
    expected_limits = (
        profile["max_lecture_students"],
        profile["max_numerical_students"],
        profile["max_lab_students"],
    )
    if expected_limits != (
        MAX_LECTURE_STUDENTS,
        MAX_NUMERICAL_STUDENTS,
        MAX_LAB_STUDENTS,
    ):
        raise ValueError("Scheduling-profile limits do not match group generation.")
    for constraint in COURSE_SESSION_TIME_CONSTRAINTS:
        weighted = constraint["constraint_type"] == "PREFERRED_WINDOW"
        if constraint["start_time"] >= constraint["end_time"] or weighted != (
            constraint["preference_weight"] is not None
        ):
            raise ValueError(f"Invalid time constraint: {constraint['key']}")

    graph: dict[str, set[str]] = {key: set() for key in sessions}
    for dependency in COURSE_SESSION_DEPENDENCIES:
        predecessor = dependency["predecessor_session_key"]
        successor = dependency["successor_session_key"]
        if predecessor == successor:
            raise ValueError(f"Self dependency: {dependency['key']}")
        graph[predecessor].add(successor)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(session_key: str) -> None:
        if session_key in visiting:
            raise ValueError(f"Session dependency cycle at {session_key}")
        if session_key in visited:
            return
        visiting.add(session_key)
        for successor in graph[session_key]:
            visit(successor)
        visiting.remove(session_key)
        visited.add(session_key)

    for session_key in graph:
        visit(session_key)

    # Necessary (not sufficient) resource-capacity checks for a weekly model.
    for room_type in ("GENERAL_ROOM", "LABORATORY"):
        demand = sum(
            session["weekly_frequency"] * session["duration_slots"]
            for session in COURSE_SESSIONS
            if session["required_room_type"] == room_type
        )
        active_room_count = sum(
            room["status"] == "ACTIVE" and room["room_type"] == room_type for room in ROOMS
        )
        if demand > active_room_count * len(TIME_SLOTS):
            raise ValueError(f"Aggregate {room_type} demand exceeds weekly capacity.")


if __name__ == "__main__":
    validate_seed_data()
    for _name in (
        "STUDY_PROGRAMS",
        "CURRICULUM_COURSES",
        "COURSE_OFFERINGS",
        "STUDENT_GROUPS",
        "COURSE_SESSIONS",
        "COURSE_SESSION_DEPENDENCIES",
    ):
        print(f"{_name}: {len(globals()[_name])}")
