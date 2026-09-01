from app.services.academic.academic_term import (
    create_academic_term,
    delete_academic_term,
    get_academic_term,
    list_academic_terms,
    update_academic_term,
)
from app.services.academic.academic_year import (
    create_academic_year,
    delete_academic_year,
    get_academic_year,
    list_academic_years,
    set_current_academic_year,
    update_academic_year,
)
from app.services.academic.course import (
    create_course,
    delete_course,
    get_course,
    list_courses,
    update_course,
)
from app.services.academic.curriculum_course import (
    create_curriculum_course,
    delete_curriculum_course,
    get_curriculum_course,
    list_curriculum_courses,
    update_curriculum_course,
)
from app.services.academic.curriculum_validation import (
    get_curriculum_validation_report,
    validate_study_program_curriculum,
)
from app.services.academic.elective_group import (
    create_elective_group,
    delete_elective_group,
    get_elective_group,
    list_elective_groups,
    update_elective_group,
)
from app.services.academic.faculty import (
    create_faculty,
    delete_faculty,
    get_faculty,
    list_faculties,
    update_faculty,
)
from app.services.academic.level import (
    create_level,
    delete_level,
    get_level,
    list_levels,
    update_level,
)
from app.services.academic.program_semester import (
    create_program_semester,
    delete_program_semester,
    get_program_semester,
    list_program_semesters,
    update_program_semester,
)
from app.services.academic.study_program import (
    create_study_program,
    delete_study_program,
    get_study_program,
    list_study_programs,
    update_study_program,
)

__all__ = [
    "create_academic_term",
    "create_academic_year",
    "create_course",
    "create_curriculum_course",
    "create_elective_group",
    "create_faculty",
    "create_level",
    "create_program_semester",
    "create_study_program",
    "delete_academic_term",
    "delete_academic_year",
    "delete_course",
    "delete_curriculum_course",
    "delete_elective_group",
    "delete_faculty",
    "delete_level",
    "delete_program_semester",
    "delete_study_program",
    "get_academic_term",
    "get_academic_year",
    "get_course",
    "get_curriculum_course",
    "get_curriculum_validation_report",
    "get_elective_group",
    "get_faculty",
    "get_level",
    "get_program_semester",
    "get_study_program",
    "list_academic_terms",
    "list_academic_years",
    "list_courses",
    "list_curriculum_courses",
    "list_elective_groups",
    "list_faculties",
    "list_levels",
    "list_program_semesters",
    "list_study_programs",
    "set_current_academic_year",
    "update_academic_term",
    "update_academic_year",
    "update_course",
    "update_curriculum_course",
    "update_elective_group",
    "update_faculty",
    "update_level",
    "update_program_semester",
    "update_study_program",
    "validate_study_program_curriculum",
]
