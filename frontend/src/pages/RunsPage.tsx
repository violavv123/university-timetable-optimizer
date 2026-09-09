import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Icon } from "../components/Icon";
import { Button, EmptyState, ErrorBanner, PageHeader, Spinner, StatusBadge } from "../components/ui";
import { catalogService } from "../services/catalog.service";
import { getErrorMessage } from "../lib/api-error";
import { formatDate, formatDuration, humanize } from "../lib/format";

export function RunsPage() {
  const [status, setStatus] = useState("");
  const [termId, setTermId] = useState("");
  const [search, setSearch] = useState("");
  useEffect(() => { document.title = "Run history — Tempo"; }, []);

  const terms = useQuery({ queryKey: ["terms"], queryFn: catalogService.terms });
  const runs = useQuery({
    queryKey: ["runs", status, termId],
    queryFn: () => catalogService.runs({ status: status || undefined, academic_term_id: termId || undefined }),
    refetchInterval: (query) => query.state.data?.items.some((run) => run.status === "RUNNING" || run.status === "PENDING") ? 2500 : false,
  });
  const rows = useMemo(() => (runs.data?.items ?? []).filter((run) => run.name.toLowerCase().includes(search.toLowerCase())).sort((a, b) => b.id - a.id), [runs.data, search]);

  return (
    <div className="page">
      <PageHeader eyebrow="Optimization archive" title="Timetable runs" description="Compare results, inspect conflicts and open any generated timetable." actions={<Link to="/generate"><Button icon="spark">New run</Button></Link>} />
      <section className="panel runs-panel">
        <div className="filters-bar"><div className="search-box"><span>⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by run name…" /></div><select value={termId} onChange={(event) => setTermId(event.target.value)}><option value="">All academic terms</option>{terms.data?.map((term) => <option value={term.id} key={term.id}>{term.name}</option>)}</select><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option>{["PENDING", "RUNNING", "SUCCEEDED", "INFEASIBLE", "FAILED", "CANCELLED"].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}</select><button className="icon-button" onClick={() => runs.refetch()} aria-label="Refresh"><Icon name="refresh" /></button></div>
        {runs.isLoading ? <div className="inline-loader"><Spinner /><p>Loading timetable runs…</p></div> : runs.error ? <ErrorBanner message={getErrorMessage(runs.error)} /> : rows.length ? <div className="table-wrap"><table className="data-table"><thead><tr><th>Run</th><th>Created</th><th>Algorithm</th><th>Status</th><th>Quality</th><th>Runtime</th><th>Publication</th><th /></tr></thead><tbody>{rows.map((run) => <tr key={run.id}><td><div className="table-primary"><span className="table-icon"><Icon name="calendar" /></span><div><strong>{run.name}</strong><small>Run #{run.id} · {humanize(run.source_type)}</small></div></div></td><td>{formatDate(run.created_at)}</td><td>{humanize(run.algorithm)}</td><td><StatusBadge status={run.status} /></td><td><strong>{run.objective_score ?? "—"}</strong><small className={run.hard_conflicts ? "text-danger" : "text-success"}>{run.hard_conflicts} hard conflicts</small></td><td>{formatDuration(run.execution_time_ms)}</td><td>{run.is_published ? <span className="published-label"><Icon name="check" /> Published</span> : <span className="muted">Draft</span>}</td><td><Link className="row-action" to={`/runs/${run.id}`}>Open <Icon name="chevron" /></Link></td></tr>)}</tbody></table></div> : <EmptyState icon="history" title="No matching runs" description="Try changing the filters or generate a new timetable." />}
      </section>
    </div>
  );
}
