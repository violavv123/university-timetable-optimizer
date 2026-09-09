import type { Course } from "./academic.types";
import type { DayOfWeek, Id } from "./common.types";
import type { Room, StaffMember, StudentGroup } from "./resource.types";
import type { CourseSession, TimeSlot } from "./scheduling.types";

export type SchedulingAlgorithm =
  | "FIRST_FIT_DECREASING"
  | "BEST_FIT_DECREASING"
  | "CP_SAT"
  | "HYBRID";

export type TimetableRunStatus =
  | "PENDING"
  | "RUNNING"
  | "SUCCEEDED"
  | "INFEASIBLE"
  | "FAILED"
  | "CANCELLED";

export interface TimetableRun {
  id: Id;
  academic_term_id: Id;
  scheduling_profile_id: Id;
  name: string;
  source_type: "GENERATED" | "MANUAL" | "IMPORTED" | "REOPTIMIZED";
  algorithm: SchedulingAlgorithm | null;
  parameters: Record<string, unknown>;
  status: TimetableRunStatus;
  objective_score: string | number | null;
  hard_conflicts: number;
  soft_penalty: string | number | null;
  execution_time_ms: number | null;
  is_published: boolean;
  created_at: string;
}

export interface TimetableEntry {
  id: Id;
  timetable_run_id: Id;
  course_session_id: Id;
  occurrence_number: number;
  room_id: Id;
  start_slot_id: Id;
  is_locked: boolean;
  assignment_source: "SOLVER" | "MANUAL" | "IMPORTED" | "PRESERVED";
  created_at: string;
}

export interface SchedulingParameters {
  time_limit_seconds: number;
  num_search_workers: number;
  random_seed: number;
  spread_repeated_occurrences: boolean;
  unused_seat_weight: number;
  log_search_progress: boolean;
}

export interface GenerationRequest {
  academic_term_id: Id;
  scheduling_profile_id: Id;
  name: string;
  algorithm: SchedulingAlgorithm;
  parameters: SchedulingParameters;
}

export interface SchedulingConflict {
  conflict_type: string;
  message: string;
  course_session_ids: Id[];
  staff_member_ids: Id[];
  student_group_ids: Id[];
  room_ids: Id[];
  day_of_week: DayOfWeek | null;
  start_time: string | null;
  end_time: string | null;
}

export interface ValidationResult {
  is_valid: boolean;
  hard_conflicts: number;
  warnings: string[];
  conflicts: SchedulingConflict[];
}

export interface ResolvedEntry extends TimetableEntry {
  slot?: TimeSlot;
  room?: Room;
  session?: CourseSession;
  course?: Course;
  staff: StaffMember[];
  groups: StudentGroup[];
}
