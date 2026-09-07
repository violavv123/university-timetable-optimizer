from decimal import Decimal
from typing import Annotated, Any

from app.routers.crud import register_crud_routes
from app.routers.dependencies import DbSession
from app.schemas.academic_term import AcademicTermCreate, AcademicTermRead, AcademicTermUpdate
from app.schemas.academic_year import AcademicYearCreate, AcademicYearRead, AcademicYearUpdate
from app.schemas.course import CourseCreate, CourseRead, CourseUpdate
from app.schemas.curriculum_course import (
    CurriculumCourseCreate,
    CurriculumCourseRead,
    CurriculumCourseUpdate,
)
from app.schemas.elective_group import ElectiveGroupCreate, ElectiveGroupRead, ElectiveGroupUpdate
from app.schemas.faculty import FacultyCreate, FacultyRead, FacultyUpdate
from app.schemas.level import LevelCreate, LevelRead, LevelUpdate
from app.schemas.program_semester import (
    ProgramSemesterCreate,
    ProgramSemesterRead,
    ProgramSemesterUpdate,
)
from app.schemas.study_program import StudyProgramCreate, StudyProgramRead, StudyProgramUpdate
from app.services.academic import (
    academic_term,
    academic_year,
    course,
    curriculum_course,
    elective_group,
    faculty,
    level,
    program_semester,
    study_program,
)
from app.services.academic.curriculum_validation import (
    get_curriculum_validation_report,
    validate_study_program_curriculum,
)
from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/academic", tags=["Academic data"])
ExpectedEcts = Annotated[Decimal, Query(gt=0)]


class ActiveFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_inactive: bool = False


class AcademicTermFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    academic_year_id: int | None = Field(default=None, gt=0)
    include_inactive: bool = False


class StudyProgramFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    faculty_id: int | None = Field(default=None, gt=0)
    level_id: int | None = Field(default=None, gt=0)
    include_inactive: bool = False


class ProgramSemesterFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_program_id: int | None = Field(default=None, gt=0)
    include_inactive: bool = False


class ElectiveGroupFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    program_semester_id: int | None = Field(default=None, gt=0)
    include_inactive: bool = False


class CurriculumCourseFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    program_semester_id: int | None = Field(default=None, gt=0)
    course_id: int | None = Field(default=None, gt=0)
    include_inactive: bool = False


register_crud_routes(
    router,
    path="/faculties",
    resource_name="faculty",
    read_schema=FacultyRead,
    create_schema=FacultyCreate,
    update_schema=FacultyUpdate,
    get_service=faculty.get_faculty,
    list_service=faculty.list_faculties,
    create_service=faculty.create_faculty,
    update_service=faculty.update_faculty,
    delete_service=faculty.delete_faculty,
    filters_schema=ActiveFilters,
)
register_crud_routes(
    router,
    path="/levels",
    resource_name="level",
    read_schema=LevelRead,
    create_schema=LevelCreate,
    update_schema=LevelUpdate,
    get_service=level.get_level,
    list_service=level.list_levels,
    create_service=level.create_level,
    update_service=level.update_level,
    delete_service=level.delete_level,
    filters_schema=ActiveFilters,
)
register_crud_routes(
    router,
    path="/study-programs",
    resource_name="study program",
    read_schema=StudyProgramRead,
    create_schema=StudyProgramCreate,
    update_schema=StudyProgramUpdate,
    get_service=study_program.get_study_program,
    list_service=study_program.list_study_programs,
    create_service=study_program.create_study_program,
    update_service=study_program.update_study_program,
    delete_service=study_program.delete_study_program,
    filters_schema=StudyProgramFilters,
)
register_crud_routes(
    router,
    path="/program-semesters",
    resource_name="program semester",
    read_schema=ProgramSemesterRead,
    create_schema=ProgramSemesterCreate,
    update_schema=ProgramSemesterUpdate,
    get_service=program_semester.get_program_semester,
    list_service=program_semester.list_program_semesters,
    create_service=program_semester.create_program_semester,
    update_service=program_semester.update_program_semester,
    delete_service=program_semester.delete_program_semester,
    filters_schema=ProgramSemesterFilters,
)
register_crud_routes(
    router,
    path="/academic-years",
    resource_name="academic year",
    read_schema=AcademicYearRead,
    create_schema=AcademicYearCreate,
    update_schema=AcademicYearUpdate,
    get_service=academic_year.get_academic_year,
    list_service=academic_year.list_academic_years,
    create_service=academic_year.create_academic_year,
    update_service=academic_year.update_academic_year,
    delete_service=academic_year.delete_academic_year,
)
register_crud_routes(
    router,
    path="/academic-terms",
    resource_name="academic term",
    read_schema=AcademicTermRead,
    create_schema=AcademicTermCreate,
    update_schema=AcademicTermUpdate,
    get_service=academic_term.get_academic_term,
    list_service=academic_term.list_academic_terms,
    create_service=academic_term.create_academic_term,
    update_service=academic_term.update_academic_term,
    delete_service=academic_term.delete_academic_term,
    filters_schema=AcademicTermFilters,
)
register_crud_routes(
    router,
    path="/courses",
    resource_name="course",
    read_schema=CourseRead,
    create_schema=CourseCreate,
    update_schema=CourseUpdate,
    get_service=course.get_course,
    list_service=course.list_courses,
    create_service=course.create_course,
    update_service=course.update_course,
    delete_service=course.delete_course,
    filters_schema=ActiveFilters,
)
register_crud_routes(
    router,
    path="/elective-groups",
    resource_name="elective group",
    read_schema=ElectiveGroupRead,
    create_schema=ElectiveGroupCreate,
    update_schema=ElectiveGroupUpdate,
    get_service=elective_group.get_elective_group,
    list_service=elective_group.list_elective_groups,
    create_service=elective_group.create_elective_group,
    update_service=elective_group.update_elective_group,
    delete_service=elective_group.delete_elective_group,
    filters_schema=ElectiveGroupFilters,
)
register_crud_routes(
    router,
    path="/curriculum-courses",
    resource_name="curriculum course",
    read_schema=CurriculumCourseRead,
    create_schema=CurriculumCourseCreate,
    update_schema=CurriculumCourseUpdate,
    get_service=curriculum_course.get_curriculum_course,
    list_service=curriculum_course.list_curriculum_courses,
    create_service=curriculum_course.create_curriculum_course,
    update_service=curriculum_course.update_curriculum_course,
    delete_service=curriculum_course.delete_curriculum_course,
    filters_schema=CurriculumCourseFilters,
)


@router.post(
    "/academic-years/{academic_year_id}/set-current",
    response_model=AcademicYearRead,
    summary="Set the current academic year",
)
def set_current_year(
    db: DbSession,
    academic_year_id: int = Path(..., gt=0),
) -> Any:
    return academic_year.set_current_academic_year(db, academic_year_id)


@router.get(
    "/study-programs/{study_program_id}/curriculum-validation",
    summary="Get a curriculum validation report",
)
def curriculum_validation_report(
    db: DbSession,
    study_program_id: int = Path(..., gt=0),
    expected_ects_per_semester: ExpectedEcts = Decimal("30.0"),
) -> dict[str, Any]:
    return get_curriculum_validation_report(
        db,
        study_program_id,
        expected_ects_per_semester=expected_ects_per_semester,
    )


@router.post(
    "/study-programs/{study_program_id}/curriculum-validation",
    summary="Validate a study program curriculum",
)
def validate_curriculum(
    db: DbSession,
    study_program_id: int = Path(..., gt=0),
    expected_ects_per_semester: ExpectedEcts = Decimal("30.0"),
) -> dict[str, Any]:
    return validate_study_program_curriculum(
        db,
        study_program_id,
        expected_ects_per_semester=expected_ects_per_semester,
    )


__all__ = ["router"]
