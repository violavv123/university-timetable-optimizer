import type {
  CourseSessionGroup,
  CourseSessionStaff,
  MessageResponse,
} from "../types";
import { httpClient } from "./http-client";

export interface StaffAssignmentPayload {
  course_session_id: number;
  staff_member_id: number;
  teaching_role: string;
  is_primary: boolean;
  is_fixed: boolean;
}

export const assignmentService = {
  createStaff: async (payload: StaffAssignmentPayload) =>
    (await httpClient.post<CourseSessionStaff>(
      "/scheduling-input/course-session-staff",
      payload,
    )).data,

  updateStaff: async (
    courseSessionId: number,
    staffMemberId: number,
    payload: Pick<StaffAssignmentPayload, "teaching_role" | "is_primary" | "is_fixed">,
  ) =>
    (await httpClient.patch<CourseSessionStaff>(
      `/scheduling-input/course-session-staff/${courseSessionId}/${staffMemberId}`,
      payload,
    )).data,

  deleteStaff: async (courseSessionId: number, staffMemberId: number) =>
    (await httpClient.delete<MessageResponse>(
      `/scheduling-input/course-session-staff/${courseSessionId}/${staffMemberId}`,
    )).data,

  createGroup: async (courseSessionId: number, studentGroupId: number) =>
    (await httpClient.post<CourseSessionGroup>(
      "/scheduling-input/course-session-groups",
      {
        course_session_id: courseSessionId,
        student_group_id: studentGroupId,
      },
    )).data,

  deleteGroup: async (courseSessionId: number, studentGroupId: number) =>
    (await httpClient.delete<MessageResponse>(
      `/scheduling-input/course-session-groups/${courseSessionId}/${studentGroupId}`,
    )).data,
};
