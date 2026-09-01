"""support non timetabled curriculum courses

Revision ID: 149fee23c191
Revises: 5845f377e88b
Create Date: 2026-09-01 21:34:30.385755

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '149fee23c191'
down_revision: Union[str, Sequence[str], None] = '5845f377e88b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add support for curriculum items without weekly timetable sessions."""

    # Existing records receive true and remain valid under the new constraint.
    op.add_column(
        "curriculum_courses",
        sa.Column(
            "requires_timetable",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )

    # Remove the previous unconditional positive-period constraint.
    op.drop_constraint(
        "weekly_periods_positive",
        "curriculum_courses",
        type_="check",
    )

    # Require positive periods only for courses included in the timetable.
    op.create_check_constraint(
        "weekly_periods_positive",
        "curriculum_courses",
        (
            "requires_timetable = false OR "
            "(lecture_periods_per_week + "
            "numerical_periods_per_week + "
            "laboratory_periods_per_week) > 0"
        ),
    )


def downgrade() -> None:
    """Restore the previous unconditional weekly-period requirement."""

    op.drop_constraint(
        "weekly_periods_positive",
        "curriculum_courses",
        type_="check",
    )

    # Do not silently corrupt thesis or professional-practice records.
    # The downgrade stops if records incompatible with the old model exist.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM curriculum_courses
                WHERE (
                    lecture_periods_per_week
                    + numerical_periods_per_week
                    + laboratory_periods_per_week
                ) <= 0
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade: zero-period curriculum courses exist';
            END IF;
        END
        $$;
        """
    )

    op.create_check_constraint(
        "weekly_periods_positive",
        "curriculum_courses",
        (
            "(lecture_periods_per_week + "
            "numerical_periods_per_week + "
            "laboratory_periods_per_week) > 0"
        ),
    )

    op.drop_column(
        "curriculum_courses",
        "requires_timetable",
    )