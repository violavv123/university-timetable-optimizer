import { Icon } from "../../components/Icon";
import { Badge, EmptyState } from "../../components/ui";
import { humanize } from "../../lib/format";
import type {
  CourseSessionGroup,
  CourseSessionStaff,
  StaffMember,
  StudentGroup,
} from "../../types";

export function StaffAssignmentsTable({
  assignments,
  staff,
  onEdit,
  onDelete,
}: {
  assignments: CourseSessionStaff[];
  staff: StaffMember[];
  onEdit: (assignment: CourseSessionStaff) => void;
  onDelete: (assignment: CourseSessionStaff) => void;
}) {
  if (!assignments.length) {
    return <EmptyState title="No staff assigned" description="Assign at least one eligible instructor to this session." />;
  }

  return (
    <div className="table-wrap">
      <table className="data-table assignment-table">
        <thead><tr><th>Staff member</th><th>Role</th><th>Rules</th><th aria-label="Actions" /></tr></thead>
        <tbody>
          {assignments.map((assignment) => {
            const person = staff.find((item) => item.id === assignment.staff_member_id);
            return (
              <tr key={`${assignment.course_session_id}-${assignment.staff_member_id}`}>
                <td><strong>{person ? `${person.first_name} ${person.last_name}` : `Staff #${assignment.staff_member_id}`}</strong></td>
                <td>{humanize(assignment.teaching_role)}</td>
                <td><div className="assignment-badges">{assignment.is_primary && <Badge tone="success">Primary</Badge>}{assignment.is_fixed && <Badge>Fixed</Badge>}</div></td>
                <td><div className="table-actions"><button type="button" onClick={() => onEdit(assignment)} aria-label="Edit staff assignment"><Icon name="edit" /></button><button type="button" className="danger" onClick={() => onDelete(assignment)} aria-label="Delete staff assignment"><Icon name="trash" /></button></div></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function GroupAssignmentsTable({
  assignments,
  groups,
  onDelete,
}: {
  assignments: CourseSessionGroup[];
  groups: StudentGroup[];
  onDelete: (assignment: CourseSessionGroup) => void;
}) {
  if (!assignments.length) {
    return <EmptyState title="No groups assigned" description="Assign the cohort or teaching groups that attend this session." />;
  }

  return (
    <div className="table-wrap">
      <table className="data-table assignment-table">
        <thead><tr><th>Student group</th><th>Type</th><th>Students</th><th aria-label="Actions" /></tr></thead>
        <tbody>
          {assignments.map((assignment) => {
            const group = groups.find((item) => item.id === assignment.student_group_id);
            return (
              <tr key={`${assignment.course_session_id}-${assignment.student_group_id}`}>
                <td><strong>{group?.name ?? `Group #${assignment.student_group_id}`}</strong></td>
                <td>{group ? humanize(group.group_type) : "—"}</td>
                <td>{group?.student_count ?? "—"}</td>
                <td><div className="table-actions"><button type="button" className="danger" onClick={() => onDelete(assignment)} aria-label="Delete group assignment"><Icon name="trash" /></button></div></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
