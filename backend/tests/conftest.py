import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

REQUIRED_TABLES = {
    "academic_terms",
    "academic_years",
    "course_offerings",
    "course_session_dependencies",
    "course_session_groups",
    "course_session_staff",
    "course_session_time_constraints",
    "course_sessions",
    "courses",
    "curriculum_courses",
    "elective_groups",
    "faculties",
    "levels",
    "program_room_preferences",
    "program_semesters",
    "room_availability",
    "rooms",
    "scheduling_profiles",
    "staff_availability",
    "staff_courses",
    "staff_members",
    "student_groups",
    "study_programs",
    "time_slots",
    "timetable_entries",
    "timetable_runs",
}


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "Integration tests require TEST_DATABASE_URL pointing to a "
            "migrated PostgreSQL test database."
        )
    if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL.")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            database_name = connection.scalar(text("SELECT current_database()"))
            normalized_name = database_name.lower() if isinstance(database_name, str) else ""
            is_test_database = (
                normalized_name == "test"
                or normalized_name.startswith("test_")
                or normalized_name.endswith("_test")
            )
            if not is_test_database:
                pytest.fail(
                    "Refusing database-mutating tests because the database "
                    "name is not clearly test-only."
                )

            existing_tables = set(inspect(connection).get_table_names())
            missing_tables = sorted(REQUIRED_TABLES - existing_tables)
            if missing_tables:
                pytest.fail(
                    "The test database is not migrated to the full schema. "
                    "Missing tables: " + ", ".join(missing_tables)
                )
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db(test_engine: Engine) -> Generator[Session]:
    connection = test_engine.connect()
    outer_transaction = connection.begin()
    session = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        if outer_transaction.is_active:
            outer_transaction.rollback()
        connection.close()
