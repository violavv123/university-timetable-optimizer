import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { TimetableGrid } from "../components/TimetableGrid";
import { Icon } from "../components/Icon";
import { Badge, Button, ErrorBanner, FullPageLoader, PageHeader, Spinner, StatusBadge } from "../components/ui";
import { catalogService } from "../services/catalog.service";
import { timetableService } from "../services/timetable.service";
import { getErrorMessage } from "../lib/api-error";
import { formatDate, formatDuration, humanize } from "../lib/format";
import type { ResolvedEntry, TimetableRun, ValidationResult } from "../types";

export function TimetablePage() {
  const id = Number(useParams().runId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [notice, setNotice] = useState("");
  useEffect(() => { document.title = "Timetable — Tempo"; }, []);

  const run = useQuery({ queryKey: ["run", id], queryFn: () => catalogService.run(id), enabled: Number.isInteger(id) && id > 0, refetchInterval: (query) => ["RUNNING", "PENDING"].includes(query.state.data?.status ?? "") ? 2500 : false });
  const entries = useQuery({ queryKey: ["entries", id], queryFn: () => catalogService.entries(id), enabled: run.data?.status === "SUCCEEDED" });
  const slots = useQuery({ queryKey: ["slots", run.data?.scheduling_profile_id], queryFn: () => catalogService.slots(run.data!.scheduling_profile_id), enabled: Boolean(run.data?.scheduling_profile_id) });
  const rooms = useQuery({ queryKey: ["rooms"], queryFn: catalogService.rooms, enabled: Boolean(entries.data) });
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: catalogService.sessions, enabled: Boolean(entries.data) });
  const offerings = useQuery({ queryKey: ["offerings", run.data?.academic_term_id], queryFn: () => catalogService.offerings(run.data?.academic_term_id), enabled: Boolean(entries.data) });
  const curricula = useQuery({ queryKey: ["curricula"], queryFn: catalogService.curricula, enabled: Boolean(entries.data) });
  const courses = useQuery({ queryKey: ["courses"], queryFn: catalogService.courses, enabled: Boolean(entries.data) });
  const staff = useQuery({ queryKey: ["staff"], queryFn: catalogService.staff, enabled: Boolean(entries.data) });
  const sessionStaff = useQuery({ queryKey: ["session-staff"], queryFn: catalogService.sessionStaff, enabled: Boolean(entries.data) });
  const groups = useQuery({ queryKey: ["groups", run.data?.academic_term_id], queryFn: () => catalogService.groups(run.data?.academic_term_id), enabled: Boolean(entries.data) });
  const sessionGroups = useQuery({ queryKey: ["session-groups"], queryFn: catalogService.sessionGroups, enabled: Boolean(entries.data) });

  const resolved = useMemo<ResolvedEntry[]>(() => (entries.data ?? []).map((entry) => {
    const session = sessions.data?.find((item) => item.id === entry.course_session_id);
    const offering = offerings.data?.find((item) => item.id === session?.course_offering_id);
    const curriculum = curricula.data?.find((item) => item.id === offering?.curriculum_course_id);
    const staffIds = sessionStaff.data?.filter((item) => item.course_session_id === entry.course_session_id).map((item) => item.staff_member_id) ?? [];
    const groupIds = sessionGroups.data?.filter((item) => item.course_session_id === entry.course_session_id).map((item) => item.student_group_id) ?? [];
    return { ...entry, slot: slots.data?.find((item) => item.id === entry.start_slot_id), room: rooms.data?.find((item) => item.id === entry.room_id), session, course: courses.data?.find((item) => item.id === curriculum?.course_id), staff: staff.data?.filter((item) => staffIds.includes(item.id)) ?? [], groups: groups.data?.filter((item) => groupIds.includes(item.id)) ?? [] };
  }), [entries.data, sessions.data, offerings.data, curricula.data, staff.data, sessionStaff.data, groups.data, sessionGroups.data, slots.data, rooms.data, courses.data]);

  const refreshRun = (updated: TimetableRun) => { queryClient.setQueryData(["run", id], updated); queryClient.invalidateQueries({ queryKey: ["runs"] }); };
  const validate = useMutation({ mutationFn: () => timetableService.validate(id), onSuccess: (result) => { setValidation(result); setNotice(result.is_valid ? "Validation passed — no hard conflicts found." : "Validation finished with conflicts."); } });
  const publication = useMutation({ mutationFn: (publish: boolean) => publish ? timetableService.publish(id) : timetableService.unpublish(id), onSuccess: (updated) => { refreshRun(updated); setNotice(updated.is_published ? "Timetable published successfully." : "Timetable returned to draft."); } });
  const lock = useMutation({ mutationFn: (entry: ResolvedEntry) => timetableService.lockEntry(entry.id, !entry.is_locked), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["entries", id] }) });
  const reoptimize = useMutation({ mutationFn: () => timetableService.reoptimize(id, { academic_term_id: run.data!.academic_term_id, scheduling_profile_id: run.data!.scheduling_profile_id, name: `${run.data!.name} — re-optimized`, algorithm: run.data!.algorithm ?? "HYBRID", parameters: { time_limit_seconds: 30, num_search_workers: 8, random_seed: 0, spread_repeated_occurrences: true, unused_seat_weight: 1, log_search_progress: false } }), onSuccess: (updated) => navigate(`/runs/${updated.id}`) });

  if (run.isLoading) return <FullPageLoader label="Loading timetable" />;
  if (run.error || !run.data) return <div className="page"><ErrorBanner message={getErrorMessage(run.error)} /><Link to="/runs"><Button variant="secondary">Back to runs</Button></Link></div>;
  const data = run.data;
  const actionError = validate.error ?? publication.error ?? lock.error ?? reoptimize.error;

  return <div className="page timetable-page">
    <div className="breadcrumb"><Link to="/runs">Run history</Link><Icon name="chevron" /><span>Run #{data.id}</span></div>
    <PageHeader eyebrow={`${humanize(data.source_type)} · ${formatDate(data.created_at)}`} title={data.name} description={`${humanize(data.algorithm)} · completed in ${formatDuration(data.execution_time_ms)}`} actions={<><Button variant="secondary" icon="refresh" disabled={reoptimize.isPending || data.status !== "SUCCEEDED"} onClick={() => reoptimize.mutate()}>{reoptimize.isPending ? "Optimizing…" : "Re-optimize"}</Button><Button variant="secondary" icon="download" disabled={!data.is_published} title={!data.is_published ? "Publish the timetable before exporting" : undefined} onClick={() => timetableService.downloadCsv(data)}>Export CSV</Button><Button icon={data.is_published ? "unlock" : "check"} disabled={publication.isPending || data.status !== "SUCCEEDED" || (!data.is_published && (validation ? !validation.is_valid : data.hard_conflicts > 0))} onClick={() => publication.mutate(!data.is_published)}>{publication.isPending ? "Saving…" : data.is_published ? "Unpublish" : "Publish"}</Button></>} />
    {notice && <div className="success-banner"><Icon name="check" /><span>{notice}</span><button onClick={() => setNotice("")}><Icon name="x" /></button></div>}
    {actionError && <ErrorBanner message={getErrorMessage(actionError)} />}
    <section className="run-metrics"><div><span>Status</span><StatusBadge status={data.status} /></div><div><span>Objective score</span><strong>{data.objective_score ?? "—"}</strong></div><div><span>Soft penalty</span><strong>{data.soft_penalty ?? "—"}</strong></div><div><span>Hard conflicts</span><strong className={data.hard_conflicts ? "text-danger" : "text-success"}>{data.hard_conflicts}</strong></div><div><span>Assignments</span><strong>{entries.data?.length ?? "—"}</strong></div><div><span>Publication</span><Badge tone={data.is_published ? "success" : "neutral"}>{data.is_published ? "Published" : "Draft"}</Badge></div><Button variant="ghost" icon="check" disabled={validate.isPending || data.status !== "SUCCEEDED"} onClick={() => validate.mutate()}>{validate.isPending ? "Checking…" : "Validate now"}</Button></section>
    {validation && !validation.is_valid && <section className="conflicts-panel panel"><div className="panel__header"><div><p className="eyebrow">Action required</p><h2>{validation.hard_conflicts} hard conflict{validation.hard_conflicts === 1 ? "" : "s"}</h2></div><Badge tone="danger">Cannot publish</Badge></div><div className="conflict-list">{validation.conflicts.map((conflict, index) => <div key={`${conflict.conflict_type}-${index}`}><span>!</span><div><strong>{humanize(conflict.conflict_type)}</strong><p>{conflict.message}</p></div></div>)}</div></section>}
    {["PENDING", "RUNNING"].includes(data.status) ? <section className="panel solver-running"><div className="solver-orbit"><Icon name="spark" /></div><h2>The solver is working</h2><p>Tempo is testing valid room, time, staff and group combinations. This page refreshes automatically.</p><div className="progress-line"><i /></div></section> : data.status !== "SUCCEEDED" ? <section className="panel run-failed"><h2>{humanize(data.status)}</h2><p>This run did not produce a timetable. Review input readiness and try another algorithm.</p><Link to="/generate"><Button>Start another run</Button></Link></section> : <section className="panel timetable-panel"><div className="panel__header"><div><p className="eyebrow">Weekly calendar</p><h2>Generated timetable</h2></div><span className="muted">Click a session to inspect or lock it</span></div>{entries.isLoading ? <div className="inline-loader"><Spinner /><p>Building weekly view…</p></div> : <TimetableGrid entries={resolved} slots={slots.data ?? []} lockingId={lock.variables?.id} onToggleLock={(entry) => lock.mutate(entry)} />}</section>}
  </div>;
}
