from app.schemas.academic_term import (
    AcademicTermBase,
    AcademicTermCreate,
    AcademicTermRead,
    AcademicTermUpdate,
)
from app.schemas.academic_year import (
    AcademicYearBase,
    AcademicYearCreate,
    AcademicYearRead,
    AcademicYearSetCurrent,
    AcademicYearUpdate,
)
from app.schemas.course import CourseBase, CourseCreate, CourseRead, CourseUpdate
from app.schemas.course_offering import (
    CourseOfferingBase,
    CourseOfferingCreate,
    CourseOfferingRead,
    CourseOfferingUpdate,
)
from app.schemas.course_session import (
    CourseSessionBase,
    CourseSessionCreate,
    CourseSessionRead,
    CourseSessionUpdate,
)
from app.schemas.course_session_dependency import (
    CourseSessionDependencyBase,
    CourseSessionDependencyCreate,
    CourseSessionDependencyRead,
    CourseSessionDependencyUpdate,
)
from app.schemas.course_session_group import (
    CourseSessionGroupCreate,
    CourseSessionGroupRead,
)
from app.schemas.course_session_staff import (
    CourseSessionStaffBase,
    CourseSessionStaffCreate,
    CourseSessionStaffRead,
    CourseSessionStaffUpdate,
)
from app.schemas.course_session_time_constraint import (
    CourseSessionTimeConstraintBase,
    CourseSessionTimeConstraintCreate,
    CourseSessionTimeConstraintRead,
    CourseSessionTimeConstraintUpdate,
)
from app.schemas.curriculum_course import (
    CurriculumCourseBase,
    CurriculumCourseCreate,
    CurriculumCourseRead,
    CurriculumCourseUpdate,
)
from app.schemas.elective_group import (
    ElectiveGroupBase,
    ElectiveGroupCreate,
    ElectiveGroupRead,
    ElectiveGroupUpdate,
)
from app.schemas.error import ErrorResponse
from app.schemas.faculty import FacultyBase, FacultyCreate, FacultyRead, FacultyUpdate
from app.schemas.level import LevelBase, LevelCreate, LevelRead, LevelUpdate
from app.schemas.program_room_preference import (
    ProgramRoomPreferenceBase,
    ProgramRoomPreferenceCreate,
    ProgramRoomPreferenceRead,
    ProgramRoomPreferenceUpdate,
)
from app.schemas.program_semester import (
    ProgramSemesterBase,
    ProgramSemesterCreate,
    ProgramSemesterRead,
    ProgramSemesterUpdate,
)
from app.schemas.room import RoomBase, RoomCreate, RoomRead, RoomUpdate
from app.schemas.room_availability import (
    RoomAvailabilityBase,
    RoomAvailabilityCreate,
    RoomAvailabilityRead,
    RoomAvailabilityUpdate,
)
from app.schemas.scheduler import (
    RoomUtilizationRead,
    SchedulingConflictRead,
    SolverStatisticsRead,
    TimetableGenerationRequest,
    TimetableGenerationResponse,
    TimetableReoptimizationRequest,
    TimetableValidationResult,
)
from app.schemas.scheduling_profile import (
    SchedulingProfileBase,
    SchedulingProfileCreate,
    SchedulingProfileRead,
    SchedulingProfileUpdate,
)
from app.schemas.staff_availability import (
    StaffAvailabilityBase,
    StaffAvailabilityCreate,
    StaffAvailabilityRead,
    StaffAvailabilityUpdate,
)
from app.schemas.staff_course import (
    StaffCourseBase,
    StaffCourseCreate,
    StaffCourseRead,
    StaffCourseUpdate,
)
from app.schemas.staff_member import (
    StaffMemberBase,
    StaffMemberCreate,
    StaffMemberRead,
    StaffMemberUpdate,
)
from app.schemas.student_group import (
    StudentGroupBase,
    StudentGroupCreate,
    StudentGroupRead,
    StudentGroupUpdate,
)
from app.schemas.study_program import (
    StudyProgramBase,
    StudyProgramCreate,
    StudyProgramRead,
    StudyProgramUpdate,
)
from app.schemas.time_slot import TimeSlotBase, TimeSlotCreate, TimeSlotRead, TimeSlotUpdate
from app.schemas.timetable_entry import (
    TimetableEntryBase,
    TimetableEntryBulkCreate,
    TimetableEntryBulkItem,
    TimetableEntryCreate,
    TimetableEntryLockUpdate,
    TimetableEntryRead,
    TimetableEntryUpdate,
)
from app.schemas.timetable_run import (
    TimetableRunBase,
    TimetableRunCreate,
    TimetableRunPublishRequest,
    TimetableRunRead,
    TimetableRunSummary,
    TimetableRunUpdate,
)

__all__ = [
    "AcademicTermBase",
    "AcademicTermCreate",
    "AcademicTermRead",
    "AcademicTermUpdate",
    "AcademicYearBase",
    "AcademicYearCreate",
    "AcademicYearRead",
    "AcademicYearSetCurrent",
    "AcademicYearUpdate",
    "CourseBase",
    "CourseCreate",
    "CourseRead",
    "CourseUpdate",
    "CourseOfferingBase",
    "CourseOfferingCreate",
    "CourseOfferingRead",
    "CourseOfferingUpdate",
    "CourseSessionBase",
    "CourseSessionCreate",
    "CourseSessionDependencyBase",
    "CourseSessionDependencyCreate",
    "CourseSessionDependencyRead",
    "CourseSessionDependencyUpdate",
    "CourseSessionGroupCreate",
    "CourseSessionGroupRead",
    "CourseSessionRead",
    "CourseSessionStaffBase",
    "CourseSessionStaffCreate",
    "CourseSessionStaffRead",
    "CourseSessionStaffUpdate",
    "CourseSessionTimeConstraintBase",
    "CourseSessionTimeConstraintCreate",
    "CourseSessionTimeConstraintRead",
    "CourseSessionTimeConstraintUpdate",
    "CourseSessionUpdate",
    "CurriculumCourseBase",
    "CurriculumCourseCreate",
    "CurriculumCourseRead",
    "CurriculumCourseUpdate",
    "ElectiveGroupBase",
    "ElectiveGroupCreate",
    "ElectiveGroupRead",
    "ElectiveGroupUpdate",
    "ErrorResponse",
    "FacultyBase",
    "FacultyCreate",
    "FacultyRead",
    "FacultyUpdate",
    "LevelBase",
    "LevelCreate",
    "LevelRead",
    "LevelUpdate",
    "ProgramRoomPreferenceBase",
    "ProgramRoomPreferenceCreate",
    "ProgramRoomPreferenceRead",
    "ProgramRoomPreferenceUpdate",
    "ProgramSemesterBase",
    "ProgramSemesterCreate",
    "ProgramSemesterRead",
    "ProgramSemesterUpdate",
    "RoomAvailabilityBase",
    "RoomAvailabilityCreate",
    "RoomAvailabilityRead",
    "RoomAvailabilityUpdate",
    "RoomBase",
    "RoomCreate",
    "RoomRead",
    "RoomUpdate",
    "RoomUtilizationRead",
    "SchedulingConflictRead",
    "SchedulingProfileBase",
    "SchedulingProfileCreate",
    "SchedulingProfileRead",
    "SchedulingProfileUpdate",
    "SolverStatisticsRead",
    "StaffAvailabilityBase",
    "StaffAvailabilityCreate",
    "StaffAvailabilityRead",
    "StaffAvailabilityUpdate",
    "StaffCourseBase",
    "StaffCourseCreate",
    "StaffCourseRead",
    "StaffCourseUpdate",
    "StaffMemberBase",
    "StaffMemberCreate",
    "StaffMemberRead",
    "StaffMemberUpdate",
    "StudyProgramBase",
    "StudyProgramCreate",
    "StudyProgramRead",
    "StudyProgramUpdate",
    "StudentGroupBase",
    "StudentGroupCreate",
    "StudentGroupRead",
    "StudentGroupUpdate",
    "TimeSlotBase",
    "TimeSlotCreate",
    "TimeSlotRead",
    "TimeSlotUpdate",
    "TimetableEntryBase",
    "TimetableEntryBulkCreate",
    "TimetableEntryBulkItem",
    "TimetableEntryCreate",
    "TimetableEntryLockUpdate",
    "TimetableEntryRead",
    "TimetableEntryUpdate",
    "TimetableGenerationRequest",
    "TimetableGenerationResponse",
    "TimetableReoptimizationRequest",
    "TimetableRunBase",
    "TimetableRunCreate",
    "TimetableRunPublishRequest",
    "TimetableRunRead",
    "TimetableRunSummary",
    "TimetableRunUpdate",
    "TimetableValidationResult",
]

