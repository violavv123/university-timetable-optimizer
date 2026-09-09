import type { DayOfWeek, Id } from "./common.types";

export interface SchedulingProfile {
  id: Id;
  faculty_id: Id;
  name: string;
  slot_minutes: number;
  max_lecture_students: number;
  max_numerical_students: number;
  max_lab_students: number;
  preferred_room_weight: number;
  historical_room_weight: number;
  student_gap_weight: number;
  staff_gap_weight: number;
  late_hour_weight: number;
  is_active: boolean;
}

export interface TimeSlot {
  id: Id;
  scheduling_profile_id: Id;
  day_of_week: DayOfWeek;
  slot_index: number;
  start_time: string;
  end_time: string;
  is_active: boolean;
}

export interface CourseOffering {
  id: Id;
  curriculum_course_id: Id;
  academic_term_id: Id;
  expected_students: number | null;
  status: "DRAFT" | "READY" | "CANCELLED" | "COMPLETED";
}

export interface CourseSession {
  id: Id;
  course_offering_id: Id;
  name: string;
  component_type: "LECTURE" | "NUMERICAL" | "LABORATORY";
  weekly_frequency: number;
  duration_slots: number;
  max_students: number | null;
  required_room_type: "GENERAL_ROOM" | "LABORATORY" | null;
  required_room_id: Id | null;
  is_splittable: boolean;
  is_active: boolean;
}

export interface CourseSessionStaff {
  course_session_id: Id;
  staff_member_id: Id;
  teaching_role: string;
  is_primary: boolean;
  is_fixed: boolean;
}

export interface CourseSessionGroup {
  course_session_id: Id;
  student_group_id: Id;
}
