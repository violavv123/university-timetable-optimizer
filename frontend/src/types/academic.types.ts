import type { Id } from "./common.types";

export interface AcademicTerm {
  id: Id;
  academic_year_id: Id;
  name: string;
  term_type: "WINTER" | "SUMMER";
  start_date: string;
  end_date: string;
  is_active: boolean;
}

export interface Faculty {
  id: Id;
  code: string;
  name: string;
  is_active: boolean;
}

export interface ProgramSemester {
  id: Id;
  study_program_id: Id;
  semester_number: number;
  is_active: boolean;
}

export interface StudyProgram {
  id: Id;
  faculty_id: Id;
  level_id: Id;
  code: string;
  name: string;
  is_active: boolean;
}

export interface Course {
  id: Id;
  code: string;
  name: string;
  is_active: boolean;
}

export interface CurriculumCourse {
  id: Id;
  program_semester_id: Id;
  course_id: Id;
  course_type: "MANDATORY" | "ELECTIVE";
  elective_group_id: Id | null;
  ects: string | number;
  requires_timetable: boolean;
  lecture_periods_per_week: number;
  numerical_periods_per_week: number;
  laboratory_periods_per_week: number;
  is_active: boolean;
}
