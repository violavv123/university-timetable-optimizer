from enum import Enum, IntEnum


class DayOfWeek(IntEnum):
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    SUNDAY = 7


class TermType(str, Enum):
    WINTER = "WINTER"
    SUMMER = "SUMMER"


class CourseType(str, Enum):
    MANDATORY = "MANDATORY"
    ELECTIVE = "ELECTIVE"


class AcademicTitle(str, Enum):
    FULL_PROFESSOR = "FULL_PROFESSOR"
    ASSOCIATE_PROFESSOR = "ASSOCIATE_PROFESSOR"
    ASSISTANT_PROFESSOR = "ASSISTANT_PROFESSOR"
    ASSISTANT = "ASSISTANT"
    OTHER = "OTHER"


class StaffType(str, Enum):
    INTERNAL = "INTERNAL"
    ENGAGED = "ENGAGED"
    OTHER_UP_FACULTY = "OTHER_UP_FACULTY"
    EXTERNAL = "EXTERNAL"


class AvailabilityType(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    PREFERRED = "PREFERRED"
    AVOID = "AVOID"


class StudentGroupType(str, Enum):
    COHORT = "COHORT"
    LECTURE_GROUP = "LECTURE_GROUP"
    NUMERICAL_GROUP = "NUMERICAL_GROUP"
    LAB_GROUP = "LAB_GROUP"


class RoomType(str, Enum):
    GENERAL_ROOM = "GENERAL_ROOM"
    LABORATORY = "LABORATORY"


class RoomStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    MAINTENANCE = "MAINTENANCE"


class CourseOfferingStatus(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class ComponentType(str, Enum):
    LECTURE = "LECTURE"
    NUMERICAL = "NUMERICAL"
    LABORATORY = "LABORATORY"


class TeachingRole(str, Enum):
    LECTURER = "LECTURER"
    NUMERICAL_INSTRUCTOR = "NUMERICAL_INSTRUCTOR"
    LAB_INSTRUCTOR = "LAB_INSTRUCTOR"


class TimeConstraintType(str, Enum):
    ALLOWED_WINDOW = "ALLOWED_WINDOW"
    FORBIDDEN_WINDOW = "FORBIDDEN_WINDOW"
    PREFERRED_WINDOW = "PREFERRED_WINDOW"
    FIXED_WINDOW = "FIXED_WINDOW"


class DependencyType(str, Enum):
    PRECEDES = "PRECEDES"
    SAME_DAY = "SAME_DAY"
    DIFFERENT_DAY = "DIFFERENT_DAY"
    CONSECUTIVE = "CONSECUTIVE"


class TimetableSourceType(str, Enum):
    GENERATED = "GENERATED"
    MANUAL = "MANUAL"
    IMPORTED = "IMPORTED"
    REOPTIMIZED = "REOPTIMIZED"


class SchedulingAlgorithm(str, Enum):
    FIRST_FIT_DECREASING = "FIRST_FIT_DECREASING"
    BEST_FIT_DECREASING = "BEST_FIT_DECREASING"
    CP_SAT = "CP_SAT"
    HYBRID = "HYBRID"


class TimetableRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    INFEASIBLE = "INFEASIBLE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AssignmentSource(str, Enum):
    SOLVER = "SOLVER"
    MANUAL = "MANUAL"
    IMPORTED = "IMPORTED"
    PRESERVED = "PRESERVED"