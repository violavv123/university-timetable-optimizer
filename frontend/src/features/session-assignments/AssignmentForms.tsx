import { useEffect, useState, type SubmitEvent } from "react";
import { Button } from "../../components/ui";
import type {
  CourseSession,
  CourseSessionStaff,
  StaffMember,
  StudentGroup,
} from "../../types";
import type { StaffAssignmentPayload } from "../../services/assignment.service";

interface SharedProps {
  sessions: CourseSession[];
  selectedSessionId: number;
  isSaving: boolean;
}

interface StaffFormProps extends SharedProps {
  staff: StaffMember[];
  initial?: CourseSessionStaff;
  onSubmit: (payload: StaffAssignmentPayload) => void;
}

export function StaffAssignmentForm({
  sessions,
  selectedSessionId,
  staff,
  initial,
  isSaving,
  onSubmit,
}: StaffFormProps) {
  const [sessionId, setSessionId] = useState(initial?.course_session_id ?? selectedSessionId);
  const [staffId, setStaffId] = useState(initial?.staff_member_id ?? 0);
  const [role, setRole] = useState(initial?.teaching_role ?? "LECTURER");
  const [isPrimary, setIsPrimary] = useState(initial?.is_primary ?? false);
  const [isFixed, setIsFixed] = useState(initial?.is_fixed ?? true);

  useEffect(() => {
    if (!initial) setSessionId(selectedSessionId);
  }, [initial, selectedSessionId]);

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit({
      course_session_id: sessionId,
      staff_member_id: staffId,
      teaching_role: role,
      is_primary: isPrimary,
      is_fixed: isFixed,
    });
  }

  return (
    <form className="assignment-form" onSubmit={submit}>
      <label>
        <span>Course session</span>
        <select
          value={sessionId}
          disabled={Boolean(initial)}
          required
          onChange={(event) => setSessionId(Number(event.target.value))}
        >
          <option value={0}>Select a session</option>
          {sessions.map((session) => (
            <option key={session.id} value={session.id}>{session.name}</option>
          ))}
        </select>
      </label>
      <label>
        <span>Staff member</span>
        <select
          value={staffId}
          disabled={Boolean(initial)}
          required
          onChange={(event) => setStaffId(Number(event.target.value))}
        >
          <option value={0}>Select a staff member</option>
          {staff.map((person) => (
            <option key={person.id} value={person.id}>
              {person.first_name} {person.last_name}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>Teaching role</span>
        <select value={role} onChange={(event) => setRole(event.target.value)}>
          <option value="LECTURER">Lecturer</option>
          <option value="NUMERICAL_INSTRUCTOR">Numerical instructor</option>
          <option value="LAB_INSTRUCTOR">Laboratory instructor</option>
        </select>
      </label>
      <div className="assignment-checks">
        <label><input type="checkbox" checked={isPrimary} onChange={(event) => setIsPrimary(event.target.checked)} /> Primary instructor</label>
        <label><input type="checkbox" checked={isFixed} onChange={(event) => setIsFixed(event.target.checked)} /> Fixed assignment</label>
      </div>
      <Button type="submit" disabled={isSaving || !sessionId || !staffId}>
        {isSaving ? "Saving…" : initial ? "Save assignment" : "Assign staff"}
      </Button>
    </form>
  );
}

interface GroupFormProps extends SharedProps {
  groups: StudentGroup[];
  onSubmit: (courseSessionId: number, studentGroupId: number) => void;
}

export function GroupAssignmentForm({
  sessions,
  selectedSessionId,
  groups,
  isSaving,
  onSubmit,
}: GroupFormProps) {
  const [sessionId, setSessionId] = useState(selectedSessionId);
  const [groupId, setGroupId] = useState(0);

  useEffect(() => setSessionId(selectedSessionId), [selectedSessionId]);

  return (
    <form
      className="assignment-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(sessionId, groupId);
      }}
    >
      <label>
        <span>Course session</span>
        <select value={sessionId} required onChange={(event) => setSessionId(Number(event.target.value))}>
          <option value={0}>Select a session</option>
          {sessions.map((session) => <option key={session.id} value={session.id}>{session.name}</option>)}
        </select>
      </label>
      <label>
        <span>Student group</span>
        <select value={groupId} required onChange={(event) => setGroupId(Number(event.target.value))}>
          <option value={0}>Select a group</option>
          {groups.map((group) => <option key={group.id} value={group.id}>{group.name} · {group.student_count} students</option>)}
        </select>
      </label>
      <p className="assignment-form__note">A session can include multiple compatible student groups.</p>
      <Button type="submit" disabled={isSaving || !sessionId || !groupId}>
        {isSaving ? "Saving…" : "Assign group"}
      </Button>
    </form>
  );
}
