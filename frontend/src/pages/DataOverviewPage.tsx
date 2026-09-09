import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Icon, type IconName } from "../components/Icon";
import { Badge, Button, ErrorBanner, PageHeader, Spinner, StatusBadge } from "../components/ui";
import { catalogService } from "../services/catalog.service";
import { API_BASE_URL } from "../services/http-client";
import { fetchPage } from "../services/pagination.service";
import { timetableService } from "../services/timetable.service";
import { getErrorMessage } from "../lib/api-error";

type Dataset = { name: string; description: string; path: string; icon: IconName; fields: string[] };

const groups: { title: string; description: string; datasets: Dataset[] }[] = [
  {
    title: "Academic structure",
    description: "The curriculum hierarchy that determines what must be scheduled.",
    datasets: [
      { name: "Faculties", description: "Institution ownership", path: "/academic/faculties", icon: "home", fields: ["code", "name"] },
      { name: "Study programs", description: "Programs and degree levels", path: "/academic/study-programs", icon: "book", fields: ["code", "name"] },
      { name: "Academic terms", description: "Scheduling periods", path: "/academic/academic-terms", icon: "calendar", fields: ["name", "term_type"] },
      { name: "Courses", description: "Course catalogue", path: "/academic/courses", icon: "book", fields: ["code", "name"] },
      { name: "Curriculum courses", description: "Semester teaching load", path: "/academic/curriculum-courses", icon: "grid", fields: ["course_type", "ects"] },
    ],
  },
  {
    title: "People and spaces",
    description: "Resources and availability that constrain possible assignments.",
    datasets: [
      { name: "Staff members", description: "Lecturers and assistants", path: "/resources/staff-members", icon: "users", fields: ["first_name", "last_name"] },
      { name: "Staff availability", description: "Weekly availability windows", path: "/resources/staff-availability", icon: "clock", fields: ["day_of_week", "availability_type"] },
      { name: "Student groups", description: "Cohorts and teaching groups", path: "/resources/student-groups", icon: "users", fields: ["name", "group_type"] },
      { name: "Rooms", description: "Capacity and room types", path: "/resources/rooms", icon: "grid", fields: ["code", "capacity"] },
      { name: "Room availability", description: "Room operating windows", path: "/resources/room-availability", icon: "clock", fields: ["day_of_week", "availability_type"] },
    ],
  },
  {
    title: "Scheduling input",
    description: "The prepared solver input for the selected teaching term.",
    datasets: [
      { name: "Profiles", description: "Limits and penalty weights", path: "/scheduling-input/scheduling-profiles", icon: "settings", fields: ["name", "slot_minutes"] },
      { name: "Time slots", description: "Weekly scheduling grid", path: "/scheduling-input/time-slots", icon: "clock", fields: ["day_of_week", "start_time"] },
      { name: "Course offerings", description: "Term-specific teaching", path: "/scheduling-input/course-offerings", icon: "book", fields: ["status", "expected_students"] },
      { name: "Course sessions", description: "Lectures, exercises and labs", path: "/scheduling-input/course-sessions", icon: "calendar", fields: ["name", "component_type"] },
    ],
  },
];

function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value).replaceAll("_", " ").toLowerCase();
}

function DatasetCard({ dataset }: { dataset: Dataset }) {
  const result = useQuery({
    queryKey: ["dataset", dataset.path],
    queryFn: () => fetchPage<Record<string, unknown>>(dataset.path, { page: 1, page_size: 3 }),
  });

  return (
    <article className="dataset-card">
      <div className="dataset-card__top"><span><Icon name={dataset.icon} /></span><Badge tone={result.error ? "danger" : result.isLoading ? "warning" : "success"}>{result.isLoading ? "Checking" : result.error ? "Unavailable" : `${result.data?.total ?? 0} records`}</Badge></div>
      <h3>{dataset.name}</h3><p>{dataset.description}</p>
      {result.data?.items.slice(0, 2).map((item, index) => <div className="dataset-sample" key={String(item.id ?? index)}>{dataset.fields.map((field) => <span key={field}>{displayValue(item[field])}</span>)}</div>)}
      {!result.isLoading && !result.data?.total && <small className="dataset-empty">No data configured yet</small>}
    </article>
  );
}

export function DataOverviewPage() {
  const [termId, setTermId] = useState(0);
  const [message, setMessage] = useState("");
  const queryClient = useQueryClient();
  useEffect(() => { document.title = "Data readiness — Tempo"; }, []);

  const terms = useQuery({ queryKey: ["terms"], queryFn: catalogService.terms });
  useEffect(() => {
    if (!termId && terms.data?.length) setTermId((terms.data.find((term) => term.is_active) ?? terms.data[0]).id);
  }, [terms.data, termId]);
  const offerings = useQuery({ queryKey: ["offerings", termId], queryFn: () => catalogService.offerings(termId), enabled: termId > 0 });
  const curricula = useQuery({ queryKey: ["curricula"], queryFn: catalogService.curricula });
  const courses = useQuery({ queryKey: ["courses"], queryFn: catalogService.courses });
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: catalogService.sessions });
  const readiness = useMutation({
    mutationFn: timetableService.validateOffering,
    onSuccess: (data) => {
      setMessage(data.message);
      queryClient.invalidateQueries({ queryKey: ["offerings", termId] });
      window.setTimeout(() => setMessage(""), 4000);
    },
  });

  const offeringRows = useMemo(() => (offerings.data ?? []).map((offering) => {
    const curriculum = curricula.data?.find((item) => item.id === offering.curriculum_course_id);
    const course = courses.data?.find((item) => item.id === curriculum?.course_id);
    const count = sessions.data?.filter((session) => session.course_offering_id === offering.id).length ?? 0;
    return { ...offering, course, sessionCount: count };
  }), [offerings.data, curricula.data, courses.data, sessions.data]);

  return (
    <div className="page">
      <PageHeader eyebrow="Solver input" title="Data readiness" description="Check that the academic structure, resources and session assignments are complete before optimization." actions={<><Link to="/inputs"><Button variant="secondary" icon="settings">Manage inputs</Button></Link><a href={`${API_BASE_URL.replace(/\/api\/v1\/?$/, "")}/docs`} target="_blank" rel="noreferrer"><Button variant="ghost">API docs</Button></a></>} />
      {message && <div className="success-banner"><Icon name="check" />{message}<button onClick={() => setMessage("")}><Icon name="x" /></button></div>}
      {readiness.error && <ErrorBanner message={getErrorMessage(readiness.error)} />}
      {groups.map((group) => <section className="data-group" key={group.title}><div className="data-group__heading"><div><h2>{group.title}</h2><p>{group.description}</p></div><span>{group.datasets.length} datasets</span></div><div className="dataset-grid">{group.datasets.map((dataset) => <DatasetCard key={dataset.path} dataset={dataset} />)}</div></section>)}
      <section className="panel readiness-table">
        <div className="panel__header"><div><p className="eyebrow">Pre-flight check</p><h2>Course offering readiness</h2></div><select value={termId} onChange={(event) => setTermId(Number(event.target.value))}>{terms.data?.map((term) => <option key={term.id} value={term.id}>{term.name}</option>)}</select></div>
        {offerings.isLoading ? <div className="inline-loader"><Spinner /><p>Checking course offerings…</p></div> : <div className="table-wrap"><table className="data-table"><thead><tr><th>Course</th><th>Expected students</th><th>Sessions</th><th>Status</th><th>Readiness</th></tr></thead><tbody>{offeringRows.map((offering) => <tr key={offering.id}><td><div><strong>{offering.course?.code ?? `Offering #${offering.id}`}</strong><small>{offering.course?.name ?? "Course details unavailable"}</small></div></td><td>{offering.expected_students ?? "From student groups"}</td><td>{offering.sessionCount}</td><td><StatusBadge status={offering.status} /></td><td>{offering.status === "READY" ? <span className="published-label"><Icon name="check" /> Ready for solver</span> : <Button variant="ghost" disabled={readiness.isPending && readiness.variables === offering.id} onClick={() => readiness.mutate(offering.id)}>{readiness.isPending && readiness.variables === offering.id ? "Checking…" : "Validate"}</Button>}</td></tr>)}</tbody></table>{!offeringRows.length && <div className="empty-inline">No course offerings exist for this term.</div>}</div>}
      </section>
      <div className="data-cta"><div><Icon name="spark" /><div><strong>Inputs look complete?</strong><span>Start a solver run and review the generated week.</span></div></div><Link to="/generate"><Button>Generate timetable <Icon name="arrow" /></Button></Link></div>
    </div>
  );
}
