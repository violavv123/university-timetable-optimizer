import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { TimetableGrid } from "../components/TimetableGrid";
import { Icon } from "../components/Icon";
import { Badge, Button, ErrorBanner, FullPageLoader, PageHeader, Spinner, StatusBadge } from "../components/ui";
import { catalogService } from "../services/catalog.service";
import { timetableService } from "../services/timetable.service";
import { useGeneration } from "../generation/GenerationContext";
import { getErrorMessage } from "../lib/api-error";
import { formatDate, formatDuration, humanize } from "../lib/format";
import type { ResolvedEntry, ValidationResult } from "../types";

export function TimetablePage() {
  const id = Number(useParams().runId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const generation = useGeneration();
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [notice, setNotice] = useState("");
  useEffect(() => { document.title = "Timetable — Time's UP"; }, []);

  const run = useQuery({ queryKey: ["run", id], queryFn: () => catalogService.run(id), enabled: Number.isInteger(id) && id > 0, refetchInterval: (query) => ["RUNNING", "PENDING"].includes(query.state.data?.status ?? "") ? 2500 : false });
  const entries = useQuery({ queryKey: ["entries", id], queryFn: () => catalogService.entries(id), enabled: run.data?.status === "SUCCEEDED" });
  const slots = useQuery({ queryKey: ["slots", run.data?.scheduling_profile_id], queryFn: () => catalogService.slots(run.data!.scheduling_profile_id), enabled: Boolean(run.data?.scheduling_profile_id) });
  const rooms = useQuery({ queryKey: ["rooms"], queryFn: catalogService.rooms, enabled: Boolean(entries.data) });
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: catalogService.sessions, enabled: Boolean(entries.data) });
  const offerings = useQuery({ queryKey: ["offerings", run.data?.academic_term_id], queryFn: () => catalogService.offerings(run.data?.academic_term_id), enabled: Boolean(entries.data) });
  const curricula = useQuery({ queryKey: ["curricula"], queryFn: catalogService.curricula, enabled: Boolean(entries.data) });
  const semesters = useQuery({ queryKey: ["semesters"], queryFn: catalogService.semesters, enabled: Boolean(entries.data) });
  const programs = useQuery({ queryKey: ["programs"], queryFn: catalogService.programs, enabled: Boolean(entries.data) });
  const levels = useQuery({ queryKey: ["levels"], queryFn: catalogService.levels, enabled: Boolean(entries.data) });
  const courses = useQuery({ queryKey: ["courses"], queryFn: catalogService.courses, enabled: Boolean(entries.data) });
  const staff = useQuery({ queryKey: ["staff"], queryFn: catalogService.staff, enabled: Boolean(entries.data) });
  const sessionStaff = useQuery({ queryKey: ["session-staff"], queryFn: catalogService.sessionStaff, enabled: Boolean(entries.data) });
  const groups = useQuery({ queryKey: ["groups", run.data?.academic_term_id], queryFn: () => catalogService.groups(run.data?.academic_term_id), enabled: Boolean(entries.data) });
  const sessionGroups = useQuery({ queryKey: ["session-groups"], queryFn: catalogService.sessionGroups, enabled: Boolean(entries.data) });

  const resolved = useMemo<ResolvedEntry[]>(() => (entries.data ?? []).map((entry) => {
    const session = sessions.data?.find((item) => item.id === entry.course_session_id);
    const offering = offerings.data?.find((item) => item.id === session?.course_offering_id);
    const curriculum = curricula.data?.find((item) => item.id === offering?.curriculum_course_id);
    const semester = semesters.data?.find((item) => item.id === curriculum?.program_semester_id);
    const program = programs.data?.find((item) => item.id === semester?.study_program_id);
    const level = levels.data?.find((item) => item.id === program?.level_id);
    const staffIds = sessionStaff.data?.filter((item) => item.course_session_id === entry.course_session_id).map((item) => item.staff_member_id) ?? [];
    const groupIds = sessionGroups.data?.filter((item) => item.course_session_id === entry.course_session_id).map((item) => item.student_group_id) ?? [];
    return { ...entry, slot: slots.data?.find((item) => item.id === entry.start_slot_id), room: rooms.data?.find((item) => item.id === entry.room_id), session, course: courses.data?.find((item) => item.id === curriculum?.course_id), program, level, staff: staff.data?.filter((item) => staffIds.includes(item.id)) ?? [], groups: groups.data?.filter((item) => groupIds.includes(item.id)) ?? [] };
  }), [entries.data, sessions.data, offerings.data, curricula.data, semesters.data, programs.data, levels.data, staff.data, sessionStaff.data, groups.data, sessionGroups.data, slots.data, rooms.data, courses.data]);

  const validate = useMutation({ mutationFn: () => timetableService.validate(id), onSuccess: (result) => { setValidation(result); setNotice(result.is_valid ? "Validation passed — no hard conflicts found." : "Validation finished with conflicts."); } });
  const lock = useMutation({ mutationFn: (entry: ResolvedEntry) => timetableService.lockEntry(entry.id, !entry.is_locked), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["entries", id] }) });
  const publish = useMutation({ mutationFn: () => timetableService.publish(id), onSuccess: (publishedRun) => { queryClient.setQueryData(["run", id], publishedRun); queryClient.invalidateQueries({ queryKey: ["runs"] }); setNotice("Timetable published successfully."); } });
  const unpublish = useMutation({ mutationFn: () => timetableService.unpublish(id), onSuccess: (unpublishedRun) => { queryClient.setQueryData(["run", id], unpublishedRun); queryClient.invalidateQueries({ queryKey: ["runs"] }); setNotice("Timetable unpublished successfully."); } });
  const csvExport = useMutation({ mutationFn: () => { if (!run.data) throw new Error("The timetable is not loaded yet."); return timetableService.downloadXlsx(run.data); }, onSuccess: () => setNotice("CSV export started.") });

  if (run.isLoading) return <FullPageLoader label="Loading timetable" />;
  if (run.error || !run.data) return <div className="page"><ErrorBanner message={getErrorMessage(run.error)} /><Link to="/runs"><Button variant="secondary">Back to runs</Button></Link></div>;
  const data = run.data;
  const actionError = validate.error ?? csvExport.error ?? lock.error ?? publish.error ?? unpublish.error;
  const displayedHardConflicts = validation?.hard_conflicts ?? data.hard_conflicts;
  const parameters = data.parameters;
  const regenerate = () => {
    generation.startGeneration(
      {
        academic_term_id: data.academic_term_id,
        scheduling_profile_id: data.scheduling_profile_id,
        name: `${data.name} — regenerated`,
        algorithm: data.algorithm ?? "HYBRID",
        parameters: {
          time_limit_seconds: typeof parameters.time_limit_seconds === "number" ? parameters.time_limit_seconds : 0,
          num_search_workers: typeof parameters.num_search_workers === "number" ? Math.max(1, Math.floor(parameters.num_search_workers)) : 2,
          random_seed: typeof parameters.random_seed === "number" ? Math.max(0, Math.floor(parameters.random_seed)) : 0,
          spread_repeated_occurrences: parameters.spread_repeated_occurrences !== false,
          unused_seat_weight: typeof parameters.unused_seat_weight === "number" ? Math.max(0, Math.floor(parameters.unused_seat_weight)) : 1,
          log_search_progress: parameters.log_search_progress === true,
        },
      },
      data.name,
    );
    navigate("/generate");
  };

  return <div className="page timetable-page">
    <div className="breadcrumb"><Link to="/runs">Run history</Link><Icon name="chevron" /><span>Run #{data.id}</span></div>
    <PageHeader eyebrow={`${humanize(data.source_type)} · ${formatDate(data.created_at)}`} title={data.name} description={`${humanize(data.algorithm)} · completed in ${formatDuration(data.execution_time_ms)}`} actions={<><Button variant={data.is_published ? "secondary" : "primary"} icon={data.is_published ? "unlock" : "check"} disabled={publish.isPending || unpublish.isPending || data.status !== "SUCCEEDED" || (!data.is_published && displayedHardConflicts > 0)} title={data.status !== "SUCCEEDED" ? "Only a successfully generated timetable can be published" : (!data.is_published && displayedHardConflicts > 0) ? "Resolve hard conflicts before publishing" : undefined} onClick={() => data.is_published ? unpublish.mutate() : publish.mutate()}>{publish.isPending || unpublish.isPending ? (data.is_published ? "Unpublishing…" : "Publishing…") : data.is_published ? "Unpublish" : "Publish timetable"}</Button><Button variant="secondary" icon="download" disabled={csvExport.isPending || data.status !== "SUCCEEDED"} title={data.status !== "SUCCEEDED" ? "Export is available after successful generation" : undefined} onClick={() => csvExport.mutate()}>{csvExport.isPending ? "Exporting…" : "Export CSV"}</Button></>} />
    {notice && <div className="success-banner"><Icon name="check" /><span>{notice}</span><button onClick={() => setNotice("")}><Icon name="x" /></button></div>}
    {actionError && <ErrorBanner message={getErrorMessage(actionError)} />}
    <section className="run-metrics"><div title="Current generation state."><span>Status</span><StatusBadge status={data.status} /></div><div title="Overall solver score; lower is better."><span>Objective score</span><strong>{data.objective_score ?? "—"}</strong></div><div title="Weighted cost of soft preferences; lower is better."><span>Soft penalty</span><strong>{data.soft_penalty ?? "—"}</strong></div><div title="Hard constraint violations; should be 0."><span>Hard conflicts</span><strong className={displayedHardConflicts ? "text-danger" : "text-success"}>{displayedHardConflicts}</strong></div><div title="Scheduled session occurrences."><span>Assignments</span><strong>{entries.data?.length ?? "—"}</strong></div><Button variant="ghost" icon="check" disabled={validate.isPending || data.status !== "SUCCEEDED"} title="Re-check all hard room, time, staff, group and dependency constraints" onClick={() => validate.mutate()}>{validate.isPending ? "Checking…" : "Validate now"}</Button></section>
    {validation && !validation.is_valid && <section className="conflicts-panel panel"><div className="panel__header"><div><p className="eyebrow">Action required</p><h2>{validation.hard_conflicts} hard conflict{validation.hard_conflicts === 1 ? "" : "s"}</h2></div><Badge tone="danger">Hard conflicts found</Badge></div><div className="conflict-list">{validation.conflicts.map((conflict, index) => <div key={`${conflict.conflict_type}-${index}`}><span>!</span><div><strong>{humanize(conflict.conflict_type)}</strong><p>{conflict.message}</p></div></div>)}</div><Button type="button" variant="secondary" icon="refresh" disabled={generation.status === "running"} onClick={regenerate}>Regenerate timetable</Button></section>}
    {["PENDING", "RUNNING"].includes(data.status) ? <section className="panel solver-running"><div className="solver-orbit"><Icon name="spark" /></div><h2>The solver is working</h2><p>Time's UP is testing valid room, time, staff and group combinations. This page refreshes automatically.</p><div className="progress-line"><i /></div></section> : data.status !== "SUCCEEDED" ? <section className="panel run-failed"><h2>{humanize(data.status)}</h2><p>This run did not produce a timetable. Review input readiness and try another algorithm.</p><Link to="/generate"><Button>Start another run</Button></Link></section> : <section className="panel timetable-panel"><div className="panel__header"><div><p className="eyebrow">Weekly calendar</p><h2>Generated timetable</h2></div><span className="muted">Click a session to inspect or lock it</span></div>{entries.isLoading ? <div className="inline-loader"><Spinner /><p>Building weekly view…</p></div> : <TimetableGrid entries={resolved} slots={slots.data ?? []} lockingId={lock.variables?.id} onToggleLock={(entry) => lock.mutate(entry)} />}</section>}
  </div>;
}
