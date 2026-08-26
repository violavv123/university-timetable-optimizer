"""add query indexes

Revision ID: 5845f377e88b
Revises: e6c979861d02
Create Date: 2026-08-26 21:13:23.835857

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5845f377e88b'
down_revision: Union[str, Sequence[str], None] = 'e6c979861d02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_study_programs_level_id",
        "study_programs",
        ["level_id"],
        unique=False,
    )
    op.create_index(
        "ix_curriculum_courses_course_id",
        "curriculum_courses",
        ["course_id"],
        unique=False,
    )
    op.create_index(
        "ix_staff_members_faculty_id",
        "staff_members",
        ["faculty_id"],
        unique=False,
    )
    op.create_index(
        "ix_staff_availability_staff_term",
        "staff_availability",
        ["staff_member_id", "academic_term_id"],
        unique=False,
    )
    op.create_index(
        "ix_student_groups_term_semester",
        "student_groups",
        ["academic_term_id", "program_semester_id"],
        unique=False,
    )
    op.create_index(
        "ix_course_offerings_academic_term_id",
        "course_offerings",
        ["academic_term_id"],
        unique=False,
    )
    op.create_index(
        "ix_course_session_groups_student_group_id",
        "course_session_groups",
        ["student_group_id"],
        unique=False,
    )
    op.create_index(
        "ix_course_session_staff_staff_member_id",
        "course_session_staff",
        ["staff_member_id"],
        unique=False,
    )
    op.create_index(
        "ix_course_session_dependencies_successor_id",
        "course_session_dependencies",
        ["successor_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_course_session_time_constraints_session_id",
        "course_session_time_constraints",
        ["course_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_timetable_entries_run_start_slot",
        "timetable_entries",
        ["timetable_run_id", "start_slot_id"],
        unique=False,
    )
    op.create_index(
        "ix_timetable_entries_room_id",
        "timetable_entries",
        ["room_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_timetable_entries_room_id",
        table_name="timetable_entries",
    )
    op.drop_index(
        "ix_timetable_entries_run_start_slot",
        table_name="timetable_entries",
    )
    op.drop_index(
        "ix_course_session_time_constraints_session_id",
        table_name="course_session_time_constraints",
    )
    op.drop_index(
        "ix_course_session_dependencies_successor_id",
        table_name="course_session_dependencies",
    )
    op.drop_index(
        "ix_course_session_staff_staff_member_id",
        table_name="course_session_staff",
    )
    op.drop_index(
        "ix_course_session_groups_student_group_id",
        table_name="course_session_groups",
    )
    op.drop_index(
        "ix_course_offerings_academic_term_id",
        table_name="course_offerings",
    )
    op.drop_index(
        "ix_student_groups_term_semester",
        table_name="student_groups",
    )
    op.drop_index(
        "ix_staff_availability_staff_term",
        table_name="staff_availability",
    )
    op.drop_index(
        "ix_staff_members_faculty_id",
        table_name="staff_members",
    )
    op.drop_index(
        "ix_curriculum_courses_course_id",
        table_name="curriculum_courses",
    )
    op.drop_index(
        "ix_study_programs_level_id",
        table_name="study_programs",
    )
