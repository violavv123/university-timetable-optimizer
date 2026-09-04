from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.academic_term import AcademicTerm
from app.models.academic_year import AcademicYear
from app.models.course import Course
from app.models.curriculum_course import CurriculumCourse
from app.models.elective_group import ElectiveGroup
from app.models.enums import CourseType, TermType
from app.models.faculty import Faculty
from app.models.level import Level
from app.models.program_semester import ProgramSemester
from app.models.study_program import StudyProgram
from app.schemas.academic_term import AcademicTermCreate
from app.schemas.academic_year import AcademicYearCreate
from app.schemas.course import CourseCreate
from app.schemas.curriculum_course import CurriculumCourseCreate
from app.schemas.elective_group import ElectiveGroupCreate
from app.schemas.faculty import FacultyCreate
from app.schemas.level import LevelCreate
from app.schemas.program_semester import ProgramSemesterCreate
from app.schemas.study_program import StudyProgramCreate
from app.services.academic.academic_term import create_academic_term
from app.services.academic.academic_year import create_academic_year
from app.services.academic.course import create_course
from app.services.academic.curriculum_course import create_curriculum_course
from app.services.academic.elective_group import create_elective_group
from app.services.academic.faculty import create_faculty
from app.services.academic.level import create_level
from app.services.academic.program_semester import create_program_semester
from app.services.academic.study_program import create_study_program
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class AcademicHierarchy:
    faculty: Faculty
    level: Level
    study_program: StudyProgram
    semesters: tuple[ProgramSemester, ...]


def unique_code(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}".upper()


def make_faculty(
    db: Session,
    *,
    is_active: bool = True,
    code: str | None = None,
) -> Faculty:
    return create_faculty(
        db,
        FacultyCreate(
            code=code or unique_code("FAC"),
            name="Test Faculty",
            is_active=is_active,
        ),
    )


def make_level(
    db: Session,
    *,
    semester_count: int = 6,
    is_active: bool = True,
    code: str | None = None,
) -> Level:
    return create_level(
        db,
        LevelCreate(
            code=code or unique_code("LVL"),
            name="Test level",
            semester_count=semester_count,
            is_active=is_active,
        ),
    )


def make_study_program(
    db: Session,
    faculty: Faculty,
    level: Level,
    *,
    is_active: bool = True,
    code: str | None = None,
) -> StudyProgram:
    return create_study_program(
        db,
        StudyProgramCreate(
            faculty_id=faculty.id,
            level_id=level.id,
            code=code or unique_code("PROG"),
            name="Test study program",
            is_active=is_active,
        ),
    )


def make_program_semester(
    db: Session,
    study_program: StudyProgram,
    semester_number: int,
    *,
    is_active: bool = True,
) -> ProgramSemester:
    return create_program_semester(
        db,
        ProgramSemesterCreate(
            study_program_id=study_program.id,
            semester_number=semester_number,
            is_active=is_active,
        ),
    )


def make_hierarchy(
    db: Session,
    *,
    semester_count: int = 6,
    created_semesters: tuple[int, ...] = (1,),
) -> AcademicHierarchy:
    faculty = make_faculty(db)
    level = make_level(db, semester_count=semester_count)
    study_program = make_study_program(db, faculty, level)
    semesters = tuple(
        make_program_semester(db, study_program, semester_number)
        for semester_number in created_semesters
    )
    return AcademicHierarchy(faculty, level, study_program, semesters)


def make_course(
    db: Session,
    *,
    code: str | None = None,
    is_active: bool = True,
) -> Course:
    return create_course(
        db,
        CourseCreate(
            code=code or unique_code("COURSE"),
            name="Test course",
            is_active=is_active,
        ),
    )


def make_elective_group(
    db: Session,
    semester: ProgramSemester,
    *,
    required_choices: int = 1,
    name: str | None = None,
) -> ElectiveGroup:
    return create_elective_group(
        db,
        ElectiveGroupCreate(
            program_semester_id=semester.id,
            name=name or f"Electives {uuid4().hex[:8]}",
            required_choices=required_choices,
            is_active=True,
        ),
    )


def make_curriculum_course(
    db: Session,
    semester: ProgramSemester,
    course: Course,
    *,
    course_type: CourseType = CourseType.MANDATORY,
    elective_group: ElectiveGroup | None = None,
    ects: Decimal = Decimal("5.0"),
    requires_timetable: bool = True,
    lecture_periods_per_week: int = 2,
    numerical_periods_per_week: int = 0,
    laboratory_periods_per_week: int = 0,
) -> CurriculumCourse:
    return create_curriculum_course(
        db,
        CurriculumCourseCreate(
            program_semester_id=semester.id,
            course_id=course.id,
            course_type=course_type,
            elective_group_id=(elective_group.id if elective_group else None),
            ects=ects,
            requires_timetable=requires_timetable,
            lecture_periods_per_week=lecture_periods_per_week,
            numerical_periods_per_week=numerical_periods_per_week,
            laboratory_periods_per_week=laboratory_periods_per_week,
            is_active=True,
        ),
    )


def make_academic_year(db: Session, start_year: int = 2200) -> AcademicYear:
    return create_academic_year(
        db,
        AcademicYearCreate(
            name=f"{start_year}/{start_year + 1}",
            start_date=date(start_year, 9, 1),
            end_date=date(start_year + 1, 8, 31),
        ),
    )


def make_academic_term(
    db: Session,
    academic_year: AcademicYear,
    *,
    term_type: TermType = TermType.WINTER,
    start_date: date | None = None,
    end_date: date | None = None,
) -> AcademicTerm:
    if term_type == TermType.WINTER:
        default_start = date(academic_year.start_date.year, 9, 15)
        default_end = date(academic_year.start_date.year + 1, 1, 31)
        name = "Winter term"
    else:
        default_start = date(academic_year.start_date.year + 1, 2, 15)
        default_end = date(academic_year.start_date.year + 1, 6, 30)
        name = "Summer term"

    return create_academic_term(
        db,
        AcademicTermCreate(
            academic_year_id=academic_year.id,
            name=name,
            term_type=term_type,
            start_date=start_date or default_start,
            end_date=end_date or default_end,
            is_active=True,
        ),
    )
