import type {
  AcademicTerm,
  Course,
  CourseOffering,
  CurriculumCourse,
  EntityRecord,
  Faculty,
  ProgramSemester,
  Room,
  SchedulingProfile,
  StaffMember,
  StudentGroup,
  StudyProgram,
} from "../../types";
import type { IconName } from "../../components/Icon";

export interface SelectOption {
  value: string | number;
  label: string;
}

export interface InputLookups {
  terms: AcademicTerm[];
  faculties: Faculty[];
  programs: StudyProgram[];
  semesters: ProgramSemester[];
  courses: Course[];
  curricula: CurriculumCourse[];
  rooms: Room[];
  staff: StaffMember[];
  groups: StudentGroup[];
  profiles: SchedulingProfile[];
  offerings: CourseOffering[];
}

export type FormValues = Record<string, string | number | boolean | null>;

export interface FieldDefinition {
  key: string;
  label: string;
  type: "text" | "number" | "time" | "select" | "checkbox";
  required?: boolean;
  min?: number;
  max?: number;
  step?: number;
  help?: string;
  options?: (lookups: InputLookups) => SelectOption[];
  visible?: (values: FormValues) => boolean;
}

export interface ColumnDefinition {
  label: string;
  value: (item: EntityRecord, lookups: InputLookups) => string;
  badge?: boolean;
}

export interface ResourceDefinition {
  key: string;
  title: string;
  singular: string;
  description: string;
  endpoint: string;
  icon: IconName;
  defaults: FormValues;
  fields: FieldDefinition[];
  columns: ColumnDefinition[];
}
