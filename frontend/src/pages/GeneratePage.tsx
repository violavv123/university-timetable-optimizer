import { useEffect, useMemo, useState, type SubmitEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Icon } from "../components/Icon";
import { Modal } from "../components/Modal";
import { Button, ErrorBanner, PageHeader } from "../components/ui";
import { useGeneration } from "../generation/GenerationContext";
import { getErrorMessage } from "../lib/api-error";
import { humanize } from "../lib/format";
import { catalogService } from "../services/catalog.service";
import type { GenerationRequest, SchedulingAlgorithm } from "../types";

const algorithms: {
  value: SchedulingAlgorithm;
  name: string;
  description: string;
  tag?: string;
}[] = [
  { value: "HYBRID", name: "Hybrid", description: "Fast baseline with CP-SAT refinement when the dataset is small enough.", tag: "Recommended" },
  { value: "CP_SAT", name: "CP-SAT", description: "Searches time and rooms jointly for stronger optimization." },
  { value: "BEST_FIT_DECREASING", name: "Best fit", description: "Fast baseline that reduces unused room capacity." },
  { value: "FIRST_FIT_DECREASING", name: "First fit", description: "Fastest deterministic baseline for comparison." },
];

const initialForm: GenerationRequest = {
  academic_term_id: 0,
  scheduling_profile_id: 0,
  name: "",
  algorithm: "HYBRID",
  parameters: {
    time_limit_seconds: 0,
    num_search_workers: 2,
    random_seed: 0,
    spread_repeated_occurrences: true,
    unused_seat_weight: 1,
    log_search_progress: false,
  },
};

function formatElapsed(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function formatRuntime(milliseconds: number | null) {
  return milliseconds === null ? "—" : `${(milliseconds / 1000).toFixed(1)} s`;
}

export function GeneratePage() {
  const navigate = useNavigate();
  const generation = useGeneration();
  const [form, setForm] = useState(initialForm);
  const [facultyId, setFacultyId] = useState(0);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [strategyInfo, setStrategyInfo] = useState<typeof algorithms[number] | null>(null);
  const faculties = useQuery({ queryKey: ["faculties"], queryFn: catalogService.faculties });
  const terms = useQuery({ queryKey: ["terms"], queryFn: catalogService.terms });
  const profiles = useQuery({ queryKey: ["profiles"], queryFn: catalogService.profiles });
  useEffect(() => { document.title = "Generate timetable — Time's UP"; }, []);
  useEffect(() => {
    if (!form.academic_term_id && terms.data?.length) {
      const term = terms.data.find((item) => item.is_active) ?? terms.data[0];
      setForm((current) => ({ ...current, academic_term_id: term.id, name: `${term.name} timetable` }));
    }
  }, [terms.data, form.academic_term_id]);

  const availableProfiles = useMemo(() => profiles.data?.filter((profile) => profile.faculty_id === facultyId) ?? [], [profiles.data, facultyId]);
  const selectedFaculty = faculties.data?.find((item) => item.id === facultyId);
  const selectedProfile = availableProfiles.find((item) => item.id === form.scheduling_profile_id);
  const selectedTerm = terms.data?.find((item) => item.id === form.academic_term_id);
  const queryError = faculties.error ?? terms.error ?? profiles.error;
  const validParameters = Number.isInteger(form.parameters.num_search_workers) && form.parameters.num_search_workers >= 1 && Number.isInteger(form.parameters.random_seed) && form.parameters.random_seed >= 0 && Number.isInteger(form.parameters.unused_seat_weight) && form.parameters.unused_seat_weight >= 0;
  const canSubmit = facultyId > 0 && Boolean(form.name.trim()) && form.academic_term_id > 0 && Boolean(selectedProfile) && validParameters && generation.status !== "running";

  function changeFaculty(nextFacultyId: number) {
    setFacultyId(nextFacultyId);
    setForm((current) => ({ ...current, scheduling_profile_id: 0 }));
  }

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit || !selectedFaculty) return;
    generation.startGeneration({ ...form, name: form.name.trim() }, `${selectedFaculty.code} — ${selectedFaculty.name}`);
  }

  const isRunning = generation.status === "running";

  return (
    <div className="page page--narrow">
      <PageHeader eyebrow="New optimization run" title="Generate a timetable" description="Choose a faculty, teaching period and strategy, then generate one timetable." />
      <form onSubmit={submit} className="generate-layout">
        <div className="generate-main">
          {queryError && <ErrorBanner message={getErrorMessage(queryError)} />}
          {generation.status === "failed" && <ErrorBanner message={generation.errorMessage} />}
          <section className="form-section panel">
            <div className="form-section__number">1</div>
            <div className="form-section__body">
              <div className="form-section__title"><h2>Faculty and teaching period</h2><p>The selected profile defines the rooms and constraints used by the solver.</p></div>
              <div className="form-grid">
                <label className="field field--full"><span>Faculty</span><select value={facultyId} onChange={(event) => changeFaculty(Number(event.target.value))} disabled={isRunning} required><option value={0}>Select a faculty first</option>{faculties.data?.map((faculty) => <option value={faculty.id} key={faculty.id}>{faculty.code} — {faculty.name}</option>)}</select></label>
                <label className="field"><span>Academic term</span><select value={form.academic_term_id} onChange={(event) => setForm({ ...form, academic_term_id: Number(event.target.value) })} disabled={isRunning} required><option value={0}>Select a term</option>{terms.data?.map((term) => <option value={term.id} key={term.id}>{term.name} · {humanize(term.term_type)}</option>)}</select></label>
                <label className="field"><span>Scheduling profile</span><select value={form.scheduling_profile_id} onChange={(event) => setForm({ ...form, scheduling_profile_id: Number(event.target.value) })} disabled={!facultyId || isRunning} required><option value={0}>{facultyId ? "Select a faculty profile" : "Choose faculty first"}</option>{availableProfiles.map((profile) => <option value={profile.id} key={profile.id}>{profile.name}</option>)}</select>{facultyId > 0 && !profiles.isLoading && !availableProfiles.length && <small className="field-help--warning">No active profile is configured for this faculty.</small>}</label>
                <label className="field field--full"><span>Run name</span><input value={form.name} maxLength={150} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="e.g. Summer semester — FIEK timetable" disabled={isRunning} required /></label>
              </div>
            </div>
          </section>

          <section className="form-section panel"><div className="form-section__number">2</div><div className="form-section__body"><div className="form-section__title"><h2>Optimization strategy</h2><p>Select a strategy to see what it does before starting the solver.</p></div><div className="algorithm-grid">{algorithms.map((algorithm) => <label className={`algorithm-card${form.algorithm === algorithm.value ? " selected" : ""}`} key={algorithm.value} onClick={() => !isRunning && setStrategyInfo(algorithm)}><input type="radio" name="algorithm" checked={form.algorithm === algorithm.value} disabled={isRunning} onChange={() => setForm({ ...form, algorithm: algorithm.value })} /><span className="algorithm-card__radio" /><span><strong>{algorithm.name}{algorithm.tag && <em>{algorithm.tag}</em>}</strong><small>{algorithm.description}</small></span></label>)}</div></div></section>

          <section className="form-section panel">
            <div className="form-section__number">3</div>
            <div className="form-section__body">
              <button type="button" className="advanced-toggle" onClick={() => setAdvancedOpen((open) => !open)}>
                <div><h2>Solver settings</h2><p>Adjust repeatability and objective preferences when needed.</p></div>
                <Icon name="chevron" className={advancedOpen ? "rotate" : ""} />
              </button>
              {advancedOpen && <div className="form-grid advanced-fields">
                <label className="field"><span>Search workers</span><input type="text" inputMode="numeric" pattern="[0-9]*" value={form.parameters.num_search_workers} disabled={isRunning} onChange={(event) => { const value = event.target.value.replace(/\D/g, ""); setForm({ ...form, parameters: { ...form.parameters, num_search_workers: value ? Math.min(2, Number(value)) : 0 } }); }} /><small>Parallel CP-SAT workers (maximum 2).</small></label>
                <label className="field"><span>Random seed</span><input type="number" min="0" step="1" value={form.parameters.random_seed} disabled={isRunning} onChange={(event) => setForm({ ...form, parameters: { ...form.parameters, random_seed: Number(event.target.value) } })} /><small>Same seed repeats choices; change it for another variation.</small></label>
                <label className="field"><span>Unused-seat weight</span><input type="number" min="0" step="1" value={form.parameters.unused_seat_weight} disabled={isRunning} onChange={(event) => setForm({ ...form, parameters: { ...form.parameters, unused_seat_weight: Number(event.target.value) } })} /><small>Penalty for empty room seats; higher values prefer tighter room fits.</small></label>
                <label className="check-field"><input type="checkbox" checked={form.parameters.spread_repeated_occurrences} disabled={isRunning} onChange={(event) => setForm({ ...form, parameters: { ...form.parameters, spread_repeated_occurrences: event.target.checked } })} /><span><strong>Spread repeated sessions</strong><small>Prefer different teaching days for repeated sessions.</small></span></label>
                <label className="check-field"><input type="checkbox" checked={form.parameters.log_search_progress} disabled={isRunning} onChange={(event) => setForm({ ...form, parameters: { ...form.parameters, log_search_progress: event.target.checked } })} /><span><strong>Log solver progress</strong><small>Print CP-SAT diagnostics in the backend terminal.</small></span></label>
              </div>}
            </div>
          </section>
        </div>

        <aside className="run-summary panel"><p className="eyebrow">{isRunning ? "Generation status" : generation.status === "succeeded" ? "Timetable ready" : "Run summary"}</p><h2>{isRunning ? "Generating timetable" : generation.status === "succeeded" ? "Review your timetable" : "Ready to optimize"}</h2>{isRunning && <div className="generation-progress" aria-live="polite"><div className="generation-progress__time"><div><strong>{formatElapsed(generation.elapsedSeconds)}</strong><span>elapsed</span></div></div></div>}<dl><div><dt>Faculty</dt><dd>{selectedFaculty?.code ?? "Not selected"}</dd></div><div><dt>Academic term</dt><dd>{selectedTerm?.name ?? "Not selected"}</dd></div><div><dt>Profile</dt><dd>{selectedProfile?.name ?? "Not selected"}</dd></div><div><dt>Algorithm</dt><dd>{humanize(form.algorithm)}</dd></div></dl>{isRunning ? <Button type="button" variant="danger" onClick={generation.abortGeneration}>Abort generation</Button> : <Button type="submit" disabled={!canSubmit}> Generate timetable</Button>}</aside>
      </form>

      {generation.status === "succeeded" && generation.results[0] && <section className="single-result panel"><div><p className="eyebrow">Generation complete</p><h2>{generation.results[0].name}</h2><p>{humanize(generation.results[0].algorithm ?? form.algorithm)} · {formatRuntime(generation.results[0].execution_time_ms)} · {generation.results[0].hard_conflicts} hard conflicts</p></div><Button type="button" onClick={() => navigate(`/runs/${generation.results[0].id}`, { state: { justGenerated: true } })}>Review timetable</Button></section>}
      {strategyInfo && <Modal title={strategyInfo.name} description="How this strategy works" onClose={() => setStrategyInfo(null)}><div className="strategy-modal__body"><p>{strategyInfo.description}</p><p>{strategyInfo.value === "FIRST_FIT_DECREASING" ? "Places each session in the first room that can accommodate it. It is usually the quickest option and is useful for a fast baseline." : strategyInfo.value === "BEST_FIT_DECREASING" ? "Places each session in the tightest suitable room, helping reduce unused capacity while remaining quick to solve." : strategyInfo.value === "CP_SAT" ? "Uses constraint programming to search room and time combinations together. It can find stronger schedules but may require more computation." : "Builds a quick room allocation first. On large faculty datasets it returns that validated baseline directly; on smaller inputs CP-SAT can refine it."}</p><footer className="modal__actions"><Button type="button" onClick={() => setStrategyInfo(null)}>Continue with {strategyInfo.name}</Button></footer></div></Modal>}
    </div>
  );
}
