import type { DayOfWeek, Id } from "./common.types";

export type AvailabilityType = "AVAILABLE" | "UNAVAILABLE" | "PREFERRED" | "AVOID";

export interface Room {
  id: Id;
  faculty_id: Id;
  code: string;
  name: string;
  capacity: number;
  room_type: "GENERAL_ROOM" | "LABORATORY";
  status: "ACTIVE" | "INACTIVE" | "MAINTENANCE";
}

export interface StaffMember {
  id: Id;
  faculty_id: Id;
  first_name: string;
  last_name: string;
  email: string | null;
  academic_title: string | null;
  staff_type: string;
  is_active: boolean;
}

export interface StudentGroup {
  id: Id;
  program_semester_id: Id;
  academic_term_id: Id;
  parent_group_id: Id | null;
  name: string;
  group_type: "COHORT" | "LECTURE_GROUP" | "NUMERICAL_GROUP" | "LAB_GROUP";
  student_count: number;
  is_active: boolean;
}

export interface StaffAvailability {
  id: Id;
  staff_member_id: Id;
  academic_term_id: Id;
  day_of_week: DayOfWeek;
  start_time: string;
  end_time: string;
  availability_type: AvailabilityType;
  preference_weight: number | null;
}

export interface RoomAvailability {
  id: Id;
  room_id: Id;
  academic_term_id: Id;
  day_of_week: DayOfWeek;
  start_time: string;
  end_time: string;
  availability_type: AvailabilityType;
  preference_weight: number | null;
}
