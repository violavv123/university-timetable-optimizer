from app.models.program_semester import ProgramSemester
from app.models.study_program import StudyProgram
from app.services.academic._common import require_active


def require_active_study_program_hierarchy(
    study_program: StudyProgram,
) -> None:
    require_active(study_program.faculty, "Faculty")
    require_active(study_program.level, "Level")
    require_active(study_program, "Study program")


def require_active_program_semester_hierarchy(
    program_semester: ProgramSemester,
) -> None:
    require_active_study_program_hierarchy(program_semester.study_program)
    require_active(program_semester, "Program semester")
