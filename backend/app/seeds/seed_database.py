"""Idempotently seed the complete eight-program FIEK scheduling fixture.

Run from the backend directory with::

    python -m app.seeds.seed_database

To atomically replace all application data before seeding::

    python -m app.seeds.seed_database --reset

The application services currently commit internally. This seeder therefore
uses the SQLAlchemy models directly so that all 24 seed stages share one atomic
transaction. Its data is constructed to satisfy the same cross-table business
rules enforced by the services.
"""

import argparse
import importlib
import pkgutil
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from app.database import SessionLocal
from app.seeds import data
from sqlalchemy import select, text
from sqlalchemy.orm import Session

MODEL_NAMES = (
    "Faculty",
    "Level",
    "StudyProgram",
    "ProgramSemester",
    "AcademicYear",
    "AcademicTerm",
    "Course",
    "ElectiveGroup",
    "CurriculumCourse",
    "StaffMember",
    "StaffCourse",
    "StaffAvailability",
    "StudentGroup",
    "Room",
    "RoomAvailability",
    "ProgramRoomPreference",
    "SchedulingProfile",
    "TimeSlot",
    "CourseOffering",
    "CourseSession",
    "CourseSessionGroup",
    "CourseSessionStaff",
    "CourseSessionTimeConstraint",
    "CourseSessionDependency",
)


def _load_models() -> dict[str, type[Any]]:
    """Find model classes even when the project groups them into submodules."""
    package = importlib.import_module("app.models")
    modules = [package]
    if hasattr(package, "__path__"):
        modules.extend(
            importlib.import_module(module_info.name)
            for module_info in pkgutil.walk_packages(
                package.__path__,
                prefix=f"{package.__name__}.",
            )
        )

    loaded: dict[str, type[Any]] = {}
    for model_name in MODEL_NAMES:
        for module in modules:
            candidate = getattr(module, model_name, None)
            if candidate is not None and hasattr(candidate, "__table__"):
                loaded[model_name] = candidate
                break
        else:
            raise ImportError(f"Could not find SQLAlchemy model {model_name!r} under app.models.")
    return loaded


MODELS = _load_models()


def reset_database(db: Session) -> None:
    """Remove application data while preserving Alembic's migration version.

    PostgreSQL TRUNCATE is transactional, so a later seed failure rolls the
    reset back together with the inserts instead of leaving an empty database.
    """
    table_names = list(
        db.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = current_schema() "
                "AND tablename <> 'alembic_version'"
            )
        ).scalars()
    )
    if not table_names:
        print("No application tables found to reset.")
        return
    preparer = db.get_bind().dialect.identifier_preparer
    targets = ", ".join(preparer.quote(name) for name in table_names)
    db.execute(text(f"TRUNCATE TABLE {targets} RESTART IDENTITY CASCADE"))
    print(f"Reset {len(table_names)} application tables.")


class Seeder:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.created: Counter[str] = Counter()
        self.existing: Counter[str] = Counter()
        self.references: dict[tuple[str, str], Any] = {}

    def ref(self, model_name: str, seed_key: str | None) -> Any | None:
        if seed_key is None:
            return None
        return self.references[(model_name, seed_key)]

    def get_or_create(
        self,
        model_name: str,
        row: Mapping[str, Any],
        *,
        natural_key: tuple[str, ...],
        foreign_keys: Mapping[str, tuple[str, str]] | None = None,
        overrides: Mapping[str, Any] | None = None,
    ) -> Any:
        model = MODELS[model_name]
        seed_key = str(row["key"])
        values = {
            key: value for key, value in row.items() if not key.endswith("_key") and key != "key"
        }
        for field, (parent_model, row_key_field) in (foreign_keys or {}).items():
            parent = self.ref(parent_model, row[row_key_field])
            values[field] = None if parent is None else parent.id
        values.update(overrides or {})

        filters = [getattr(model, field) == values[field] for field in natural_key]
        instance = self.db.scalar(select(model).where(*filters))
        if instance is None:
            instance = model(**values)
            self.db.add(instance)
            self.db.flush()
            self.created[model.__table__.name] += 1
        else:
            self.existing[model.__table__.name] += 1
        self.references[(model_name, seed_key)] = instance
        return instance

    def seed_many(
        self,
        model_name: str,
        rows: Iterable[Mapping[str, Any]],
        *,
        natural_key: tuple[str, ...],
        foreign_keys: Mapping[str, tuple[str, str]] | None = None,
    ) -> None:
        for row in rows:
            self.get_or_create(
                model_name,
                row,
                natural_key=natural_key,
                foreign_keys=foreign_keys,
            )

    def print_summary(self) -> None:
        print("\nSeed summary")
        print("-" * 55)
        for model_name in MODEL_NAMES:
            table_name = MODELS[model_name].__table__.name
            print(
                f"{table_name:<38} "
                f"created={self.created[table_name]:>3}  "
                f"existing={self.existing[table_name]:>3}"
            )


def seed_database(db: Session) -> Seeder:
    data.validate_seed_data()
    seed = Seeder(db)

    # 1-4. Core academic structure.
    seed.seed_many("Faculty", data.FACULTIES, natural_key=("code",))
    seed.seed_many("Level", data.LEVELS, natural_key=("code",))
    seed.seed_many(
        "StudyProgram",
        data.STUDY_PROGRAMS,
        natural_key=("faculty_id", "level_id", "code"),
        foreign_keys={
            "faculty_id": ("Faculty", "faculty_key"),
            "level_id": ("Level", "level_key"),
        },
    )
    seed.seed_many(
        "ProgramSemester",
        data.PROGRAM_SEMESTERS,
        natural_key=("study_program_id", "semester_number"),
        foreign_keys={"study_program_id": ("StudyProgram", "study_program_key")},
    )

    # 5-6. Academic year and terms. Respect an existing current year.
    academic_year_model = MODELS["AcademicYear"]
    current_year = db.scalar(
        select(academic_year_model).where(academic_year_model.is_current.is_(True))
    )
    for row in data.ACADEMIC_YEARS:
        requested_current = bool(row["is_current"])
        is_current = requested_current and (
            current_year is None or current_year.name == row["name"]
        )
        if requested_current and not is_current:
            assert current_year is not None
            print(
                f"Keeping existing current academic year {current_year.name!r}; "
                f"seeding {row['name']!r} as non-current."
            )
        seed.get_or_create(
            "AcademicYear",
            row,
            natural_key=("name",),
            overrides={"is_current": is_current},
        )
    seed.seed_many(
        "AcademicTerm",
        data.ACADEMIC_TERMS,
        natural_key=("academic_year_id", "term_type"),
        foreign_keys={"academic_year_id": ("AcademicYear", "academic_year_key")},
    )

    # 7-9. Courses and curriculum.
    seed.seed_many("Course", data.COURSES, natural_key=("code",))
    seed.seed_many(
        "ElectiveGroup",
        data.ELECTIVE_GROUPS,
        natural_key=("program_semester_id", "name"),
        foreign_keys={"program_semester_id": ("ProgramSemester", "program_semester_key")},
    )
    seed.seed_many(
        "CurriculumCourse",
        data.CURRICULUM_COURSES,
        natural_key=("program_semester_id", "course_id"),
        foreign_keys={
            "program_semester_id": ("ProgramSemester", "program_semester_key"),
            "course_id": ("Course", "course_key"),
            "elective_group_id": ("ElectiveGroup", "elective_group_key"),
        },
    )

    # 10-13. Staff, qualifications, availability, and student groups.
    seed.seed_many(
        "StaffMember",
        data.STAFF_MEMBERS,
        natural_key=("faculty_id", "first_name", "last_name"),
        foreign_keys={"faculty_id": ("Faculty", "faculty_key")},
    )
    seed.seed_many(
        "StaffCourse",
        data.STAFF_COURSES,
        natural_key=("staff_member_id", "course_id"),
        foreign_keys={
            "staff_member_id": ("StaffMember", "staff_member_key"),
            "course_id": ("Course", "course_key"),
        },
    )
    seed.seed_many(
        "StaffAvailability",
        data.STAFF_AVAILABILITY,
        natural_key=(
            "staff_member_id",
            "academic_term_id",
            "day_of_week",
            "start_time",
            "end_time",
            "availability_type",
        ),
        foreign_keys={
            "staff_member_id": ("StaffMember", "staff_member_key"),
            "academic_term_id": ("AcademicTerm", "academic_term_key"),
        },
    )
    seed.seed_many(
        "StudentGroup",
        data.STUDENT_GROUPS,
        natural_key=("program_semester_id", "academic_term_id", "name"),
        foreign_keys={
            "program_semester_id": ("ProgramSemester", "program_semester_key"),
            "academic_term_id": ("AcademicTerm", "academic_term_key"),
            "parent_group_id": ("StudentGroup", "parent_group_key"),
        },
    )

    # 14-18. Rooms, preferences, profile, and slots.
    seed.seed_many(
        "Room",
        data.ROOMS,
        natural_key=("faculty_id", "code"),
        foreign_keys={"faculty_id": ("Faculty", "faculty_key")},
    )
    seed.seed_many(
        "RoomAvailability",
        data.ROOM_AVAILABILITY,
        natural_key=(
            "room_id",
            "academic_term_id",
            "day_of_week",
            "start_time",
            "end_time",
            "availability_type",
        ),
        foreign_keys={
            "room_id": ("Room", "room_key"),
            "academic_term_id": ("AcademicTerm", "academic_term_key"),
        },
    )
    seed.seed_many(
        "ProgramRoomPreference",
        data.PROGRAM_ROOM_PREFERENCES,
        natural_key=("study_program_id", "room_id"),
        foreign_keys={
            "study_program_id": ("StudyProgram", "study_program_key"),
            "room_id": ("Room", "room_key"),
        },
    )
    seed.seed_many(
        "SchedulingProfile",
        data.SCHEDULING_PROFILES,
        natural_key=("faculty_id", "name"),
        foreign_keys={"faculty_id": ("Faculty", "faculty_key")},
    )
    seed.seed_many(
        "TimeSlot",
        data.TIME_SLOTS,
        natural_key=("scheduling_profile_id", "day_of_week", "slot_index"),
        foreign_keys={
            "scheduling_profile_id": (
                "SchedulingProfile",
                "scheduling_profile_key",
            )
        },
    )

    # 19-24. Offerings, sessions, assignments, constraints, dependencies.
    seed.seed_many(
        "CourseOffering",
        data.COURSE_OFFERINGS,
        natural_key=("curriculum_course_id", "academic_term_id"),
        foreign_keys={
            "curriculum_course_id": (
                "CurriculumCourse",
                "curriculum_course_key",
            ),
            "academic_term_id": ("AcademicTerm", "academic_term_key"),
        },
    )
    seed.seed_many(
        "CourseSession",
        data.COURSE_SESSIONS,
        natural_key=("course_offering_id", "name"),
        foreign_keys={
            "course_offering_id": ("CourseOffering", "course_offering_key"),
            "required_room_id": ("Room", "required_room_key"),
        },
    )
    seed.seed_many(
        "CourseSessionGroup",
        data.COURSE_SESSION_GROUPS,
        natural_key=("course_session_id", "student_group_id"),
        foreign_keys={
            "course_session_id": ("CourseSession", "course_session_key"),
            "student_group_id": ("StudentGroup", "student_group_key"),
        },
    )
    seed.seed_many(
        "CourseSessionStaff",
        data.COURSE_SESSION_STAFF,
        natural_key=("course_session_id", "staff_member_id"),
        foreign_keys={
            "course_session_id": ("CourseSession", "course_session_key"),
            "staff_member_id": ("StaffMember", "staff_member_key"),
        },
    )
    seed.seed_many(
        "CourseSessionTimeConstraint",
        data.COURSE_SESSION_TIME_CONSTRAINTS,
        natural_key=(
            "course_session_id",
            "day_of_week",
            "start_time",
            "end_time",
            "constraint_type",
        ),
        foreign_keys={"course_session_id": ("CourseSession", "course_session_key")},
    )
    seed.seed_many(
        "CourseSessionDependency",
        data.COURSE_SESSION_DEPENDENCIES,
        natural_key=(
            "predecessor_session_id",
            "successor_session_id",
            "dependency_type",
        ),
        foreign_keys={
            "predecessor_session_id": (
                "CourseSession",
                "predecessor_session_key",
            ),
            "successor_session_id": (
                "CourseSession",
                "successor_session_key",
            ),
        },
    )
    return seed


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the FIEK timetable database.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Replace all application data before inserting this seed package.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    with SessionLocal() as db:
        try:
            if args.reset:
                # Validate the complete in-memory fixture before removing data.
                data.validate_seed_data()
                reset_database(db)
            seed = seed_database(db)
            db.commit()
        except Exception:
            db.rollback()
            print("Database seed failed; the transaction was rolled back.")
            raise
        seed.print_summary()
        print("\nDatabase seed completed successfully.")


if __name__ == "__main__":
    main()
