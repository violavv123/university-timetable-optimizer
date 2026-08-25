from app.models.academic_term import AcademicTerm
from app.models.academic_year import AcademicYear
from app.models.course import Course
from app.models.curriculum_course import CurriculumCourse
from app.models.elective_group import ElectiveGroup
from app.models.faculty import Faculty
from app.models.level import Level
from app.models.program_semester import ProgramSemester
from app.models.study_program import StudyProgram
from app.models.room import Room
from app.models.room_availability import RoomAvailability
from app.models.staff_member import StaffMember
from app.models.staff_course import StaffCourse
from app.models.staff_availability import StaffAvailability
from app.models.program_room_preference import ProgramRoomPreference
from app.models.student_group import StudentGroup

__all__ = [
    "AcademicTerm",
    "AcademicYear",
    "Course",
    "CurriculumCourse",
    "ElectiveGroup",
    "Faculty",
    "Level",
    "ProgramSemester",
    "StudyProgram",
    "Room",
    "RoomAvailability",
    "StaffMember",
    "StaffCourse",
    "StaffAvailability",
    "ProgramRoomPreference",
    "StudentGroup",
]
