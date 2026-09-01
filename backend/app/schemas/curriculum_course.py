from decimal import Decimal
from typing import Self

from app.models.enums import CourseType
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CurriculumCourseBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    program_semester_id: int = Field(..., gt=0)
    course_id: int = Field(..., gt=0)
    course_type: CourseType
    elective_group_id: int | None = Field(default=None, gt=0)
    ects: Decimal = Field(..., gt=0, le=30, max_digits=4, decimal_places=1)
    requires_timetable: bool = True
    lecture_periods_per_week: int = Field(default=0, ge=0, le=32767)
    numerical_periods_per_week: int = Field(default=0, ge=0, le=32767)
    laboratory_periods_per_week: int = Field(default=0, ge=0, le=32767)

    @model_validator(mode="after")
    def validate_course_configuration(self) -> Self:
        total_periods = (
            self.lecture_periods_per_week
            + self.numerical_periods_per_week
            + self.laboratory_periods_per_week
        )
        if self.requires_timetable and total_periods <= 0:
            raise ValueError(
                "at least one weekly teaching period is required when requires_timetable is true"
            )

        if self.course_type == CourseType.MANDATORY and self.elective_group_id is not None:
            raise ValueError("mandatory courses cannot belong to an elective group")

        if self.course_type == CourseType.ELECTIVE and self.elective_group_id is None:
            raise ValueError("elective courses must belong to an elective group")

        return self


class CurriculumCourseCreate(CurriculumCourseBase):
    is_active: bool = True


class CurriculumCourseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    program_semester_id: int | None = Field(default=None, gt=0)
    course_id: int | None = Field(default=None, gt=0)
    course_type: CourseType | None = None
    elective_group_id: int | None = Field(default=None, gt=0)
    ects: Decimal | None = Field(default=None, gt=0, le=30, max_digits=4, decimal_places=1)
    requires_timetable: bool | None = None
    lecture_periods_per_week: int | None = Field(default=None, ge=0, le=32767)
    numerical_periods_per_week: int | None = Field(default=None, ge=0, le=32767)
    laboratory_periods_per_week: int | None = Field(default=None, ge=0, le=32767)
    is_active: bool | None = None

    @model_validator(mode="after")
    def reject_locally_inconsistent_patch(self) -> Self:
        supplied = self.model_fields_set

        period_fields = {
            "lecture_periods_per_week",
            "numerical_periods_per_week",
            "laboratory_periods_per_week",
        }
        if self.requires_timetable is True and period_fields.issubset(supplied):
            total_periods = (
                (self.lecture_periods_per_week or 0)
                + (self.numerical_periods_per_week or 0)
                + (self.laboratory_periods_per_week or 0)
            )

            if total_periods <= 0:
                raise ValueError(
                    "at least one weekly teaching period is required "
                    "when requires_timetable is true"
                )

        if self.course_type == CourseType.MANDATORY and self.elective_group_id is not None:
            raise ValueError("mandatory courses cannot belong to an elective group")

        if (
            self.course_type == CourseType.ELECTIVE
            and "elective_group_id" in supplied
            and self.elective_group_id is None
        ):
            raise ValueError("elective courses must belong to an elective group")

        return self


class CurriculumCourseRead(CurriculumCourseBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    is_active: bool
