import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Icon } from "../components/Icon";
import { Modal } from "../components/Modal";
import { Button, ErrorBanner, PageHeader, Spinner } from "../components/ui";
import {
  GroupAssignmentForm,
  StaffAssignmentForm,
} from "../features/session-assignments/AssignmentForms";
import {
  GroupAssignmentsTable,
  StaffAssignmentsTable,
} from "../features/session-assignments/AssignmentTables";
import { getErrorMessage } from "../lib/api-error";
import {
  assignmentService,
  type StaffAssignmentPayload,
} from "../services/assignment.service";
import { catalogService } from "../services/catalog.service";
import type { CourseSessionGroup, CourseSessionStaff } from "../types";
import "../styles/pages/session-assignments.css";

type DeleteTarget =
  | { type: "staff"; value: CourseSessionStaff }
  | { type: "group"; value: CourseSessionGroup };

export function SessionAssignmentsPage() {
  const queryClient = useQueryClient();
  const [sessionId, setSessionId] = useState(0);
  const [editing, setEditing] = useState<CourseSessionStaff | null>(null);
  const [deleting, setDeleting] = useState<DeleteTarget | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => { document.title = "Teaching assignments — Time's UP"; }, []);

  const sessions = useQuery({ queryKey: ["sessions"], queryFn: catalogService.sessions });
  const staff = useQuery({ queryKey: ["staff"], queryFn: catalogService.staff });
  const groups = useQuery({ queryKey: ["groups"], queryFn: () => catalogService.groups() });
  const staffLinks = useQuery({ queryKey: ["session-assignments", "staff"], queryFn: catalogService.sessionStaff });
  const groupLinks = useQuery({ queryKey: ["session-assignments", "groups"], queryFn: catalogService.sessionGroups });

  useEffect(() => {
    if (!sessionId && sessions.data?.length) setSessionId(sessions.data[0].id);
  }, [sessionId, sessions.data]);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["session-assignments"] });
  const created = (message: string) => {
    setNotice(message);
    void refresh();
  };

  const createStaff = useMutation({
    mutationFn: assignmentService.createStaff,
    onSuccess: () => created("Staff member assigned successfully."),
  });
  const updateStaff = useMutation({
    mutationFn: (payload: StaffAssignmentPayload) =>
      assignmentService.updateStaff(
        payload.course_session_id,
        payload.staff_member_id,
        {
          teaching_role: payload.teaching_role,
          is_primary: payload.is_primary,
          is_fixed: payload.is_fixed,
        },
      ),
    onSuccess: () => {
      setEditing(null);
      created("Staff assignment updated successfully.");
    },
  });
  const createGroup = useMutation({
    mutationFn: ({ courseSessionId, studentGroupId }: { courseSessionId: number; studentGroupId: number }) =>
      assignmentService.createGroup(courseSessionId, studentGroupId),
    onSuccess: () => created("Student group assigned successfully."),
  });
  const remove = useMutation({
    mutationFn: (target: DeleteTarget) => target.type === "staff"
      ? assignmentService.deleteStaff(target.value.course_session_id, target.value.staff_member_id)
      : assignmentService.deleteGroup(target.value.course_session_id, target.value.student_group_id),
    onSuccess: (response) => {
      setDeleting(null);
      created(response.message);
    },
  });

  const visibleStaff = useMemo(
    () => (staffLinks.data ?? []).filter((item) => item.course_session_id === sessionId),
    [sessionId, staffLinks.data],
  );
  const visibleGroups = useMemo(
    () => (groupLinks.data ?? []).filter((item) => item.course_session_id === sessionId),
    [sessionId, groupLinks.data],
  );
  const selectedSession = sessions.data?.find((session) => session.id === sessionId);
  const queryError = [sessions, staff, groups, staffLinks, groupLinks].find((query) => query.error)?.error;
  const mutationError = createStaff.error ?? updateStaff.error ?? createGroup.error ?? remove.error;
  const loading = [sessions, staff, groups, staffLinks, groupLinks].some((query) => query.isLoading);

  return (
    <div className="page assignments-page">
      <PageHeader
        eyebrow="Solver input"
        title="Teaching assignments"
        description="Connect each course session to its instructors and attending student groups before readiness validation."
        actions={<Link to="/inputs/sessions"><Button variant="secondary" icon="settings">Manage sessions</Button></Link>}
      />

      {notice && <div className="success-banner"><Icon name="check" /><span>{notice}</span><button type="button" onClick={() => setNotice("")}><Icon name="x" /></button></div>}
      {queryError && <ErrorBanner message={getErrorMessage(queryError)} />}
      {mutationError && <ErrorBanner message={getErrorMessage(mutationError)} />}

      <section className="panel assignment-focus">
        <label><span>Working course session</span><select value={sessionId} onChange={(event) => setSessionId(Number(event.target.value))}>{sessions.data?.map((session) => <option key={session.id} value={session.id}>{session.name}</option>)}</select></label>
        <div><strong>{selectedSession?.name ?? "Select a course session"}</strong><span>{visibleStaff.length} staff · {visibleGroups.length} groups assigned</span></div>
      </section>

      {loading ? <div className="inline-loader"><Spinner /><p>Loading teaching assignments…</p></div> : (
        <div className="assignment-grid">
          <section className="panel assignment-panel">
            <header><div><p className="eyebrow">Instructors</p><h2>Assigned staff</h2></div><span>{visibleStaff.length}</span></header>
            <StaffAssignmentsTable assignments={visibleStaff} staff={staff.data ?? []} onEdit={setEditing} onDelete={(value) => setDeleting({ type: "staff", value })} />
            <div className="assignment-panel__form"><h3>Add staff assignment</h3><StaffAssignmentForm sessions={sessions.data ?? []} selectedSessionId={sessionId} staff={staff.data ?? []} isSaving={createStaff.isPending} onSubmit={(payload) => createStaff.mutate(payload)} /></div>
          </section>
          <section className="panel assignment-panel">
            <header><div><p className="eyebrow">Attendance</p><h2>Assigned student groups</h2></div><span>{visibleGroups.length}</span></header>
            <GroupAssignmentsTable assignments={visibleGroups} groups={groups.data ?? []} onDelete={(value) => setDeleting({ type: "group", value })} />
            <div className="assignment-panel__form"><h3>Add student group</h3><GroupAssignmentForm sessions={sessions.data ?? []} selectedSessionId={sessionId} groups={groups.data ?? []} isSaving={createGroup.isPending} onSubmit={(courseSessionId, studentGroupId) => createGroup.mutate({ courseSessionId, studentGroupId })} /></div>
          </section>
        </div>
      )}

      {editing && <Modal title="Edit staff assignment" description="The staff member and course session are fixed; update the teaching responsibility." onClose={() => setEditing(null)}><StaffAssignmentForm sessions={sessions.data ?? []} selectedSessionId={sessionId} staff={staff.data ?? []} initial={editing} isSaving={updateStaff.isPending} onSubmit={(payload) => updateStaff.mutate(payload)} />{updateStaff.error && <ErrorBanner message={getErrorMessage(updateStaff.error)} />}</Modal>}
      {deleting && <Modal title="Remove assignment?" description="This removes the link only; the staff member, group and session remain available." onClose={() => setDeleting(null)}><div className="delete-confirmation">{remove.error && <ErrorBanner message={getErrorMessage(remove.error)} />}<p>The solver will no longer use this assignment for the selected session.</p><footer className="modal__actions"><Button variant="secondary" onClick={() => setDeleting(null)}>Keep assignment</Button><Button variant="danger" icon="trash" disabled={remove.isPending} onClick={() => remove.mutate(deleting)}>{remove.isPending ? "Removing…" : "Remove"}</Button></footer></div></Modal>}
    </div>
  );
}
