import { useEffect, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Icon } from "../components/Icon";
import { Button, EmptyState, PageHeader, StatCard, StatusBadge } from "../components/ui";
import { catalogService } from "../services/catalog.service";
import { formatDate, formatDuration, humanize } from "../lib/format";

export function DashboardPage() {
  const { user } = useAuth();
  useEffect(() => { document.title = "Overview — Tempo"; }, []);

  const rooms = useQuery({ queryKey: ["rooms"], queryFn: catalogService.rooms });
  const staff = useQuery({ queryKey: ["staff"], queryFn: catalogService.staff });
  const staffAvailability = useQuery({ queryKey: ["staff-availability"], queryFn: catalogService.staffAvailability });
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: catalogService.sessions });
  const terms = useQuery({ queryKey: ["terms"], queryFn: catalogService.terms });
  const runs = useQuery({ queryKey: ["runs", "recent"], queryFn: () => catalogService.runs() });

  const activeTerm = terms.data?.find((term) => term.is_active);
  const ready = [rooms.data, staffAvailability.data, sessions.data, terms.data].every((items) => (items?.length ?? 0) > 0);
  const latestRuns = [...(runs.data?.items ?? [])].sort((a, b) => b.id - a.id).slice(0, 5);

  return (
    <div className="page">
      <PageHeader eyebrow="Workspace overview" title={`Good to see you, ${user?.username ?? "admin"}.`} description="Everything you need to prepare, generate and publish this semester’s timetable." actions={<Link to="/generate"><Button icon="spark">Generate timetable</Button></Link>} />

      <section className="stats-grid">
        <StatCard label="Teaching rooms" value={rooms.data?.length ?? "—"} detail="Active and available" icon="grid" tone="green" />
        <StatCard label="Staff members" value={staff.data?.length ?? "—"} detail="Eligible teaching staff" icon="users" tone="purple" />
        <StatCard label="Course sessions" value={sessions.data?.length ?? "—"} detail="Ready for allocation" icon="book" tone="blue" />
        <StatCard label="Active term" value={activeTerm?.name ?? "—"} detail={activeTerm ? `${formatDate(activeTerm.start_date)} – ${formatDate(activeTerm.end_date)}` : "No active term found"} icon="calendar" tone="gold" />
      </section>

      <section className="dashboard-grid">
        <article className="panel panel--runs">
          <div className="panel__header"><div><p className="eyebrow">Latest activity</p><h2>Recent timetable runs</h2></div><Link to="/runs" className="text-link">View all <Icon name="arrow" /></Link></div>
          {latestRuns.length ? <div className="run-list">
            {latestRuns.map((run) => <Link to={`/runs/${run.id}`} className="run-row" key={run.id}>
              <div className="run-row__icon"><Icon name="calendar" /></div>
              <div className="run-row__main"><strong>{run.name}</strong><span>{humanize(run.algorithm)} · {formatDate(run.created_at)}</span></div>
              <StatusBadge status={run.status} />
              <span className="run-row__time">{formatDuration(run.execution_time_ms)}</span>
              <Icon name="chevron" className="run-row__chevron" />
            </Link>)}
          </div> : <EmptyState title="No timetable runs yet" description="Your generated timetables will appear here." action={<Link to="/generate"><Button variant="secondary">Create first run</Button></Link>} />}
        </article>

        <aside className="panel readiness-card">
          <p className="eyebrow">Before you generate</p><h2>Data readiness</h2>
          <div className="readiness-ring" style={{ "--progress": ready ? "100%" : "62%" } as CSSProperties}><div><strong>{ready ? "100%" : "62%"}</strong><span>ready</span></div></div>
          <div className="mini-checklist">
            <div className={terms.data?.length ? "complete" : ""}><Icon name={terms.data?.length ? "check" : "clock"} /><span>Academic term configured</span></div>
            <div className={rooms.data?.length ? "complete" : ""}><Icon name={rooms.data?.length ? "check" : "clock"} /><span>Rooms and capacities loaded</span></div>
            <div className={sessions.data?.length ? "complete" : ""}><Icon name={sessions.data?.length ? "check" : "clock"} /><span>Course sessions prepared</span></div>
            <div className={staffAvailability.data?.length ? "complete" : ""}><Icon name={staffAvailability.data?.length ? "check" : "clock"} /><span>Staff availability assigned</span></div>
          </div>
          <Link to="/data" className="readiness-link">Review input data <Icon name="arrow" /></Link>
        </aside>
      </section>
    </div>
  );
}
