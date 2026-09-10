import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Icon } from "../components/Icon";
import { Button, ErrorBanner, PageHeader, Spinner } from "../components/ui";
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
  {
    value: "HYBRID",
    name: "Hybrid",
    description: "Creates a fast initial timetable, then lets CP-SAT improve it.",
    tag: "Recommended",
  },
  {
    value: "CP_SAT",
    name: "CP-SAT",
    description: "Searches jointly across time and rooms for stronger optimization.",
  },
  {
    value: "BEST_FIT_DECREASING",
    name: "Best fit",
    description: "A fast baseline that prefers rooms with the least wasted capacity.",
  },
  {
    value: "FIRST_FIT_DECREASING",
    name: "First fit",
    description: "The fastest deterministic baseline for comparison runs.",
  },
];

const initialForm: GenerationRequest = {
  academic_term_id: 0,
  scheduling_profile_id: 0,
  name: "",
  algorithm: "HYBRID",
  parameters: {
    time_limit_seconds: 30,
    num_search_workers: 8,
    random_seed: 0,
    spread_repeated_occurrences: true,
    unused_seat_weight: 1,
    log_search_progress: false,
  },
};

function formatElapsed(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

export function GeneratePage() {
  const navigate = useNavigate();
  const generation = useGeneration();
  const [form, setForm] = useState(initialForm);
  const [facultyId, setFacultyId] = useState(0);
  const [timeLimitInput, setTimeLimitInput] = useState("30");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [submittedHere, setSubmittedHere] = useState(false);
  const faculties = useQuery({ queryKey: ["faculties"], queryFn: catalogService.faculties });
  const terms = useQuery({ queryKey: ["terms"], queryFn: catalogService.terms });
  const profiles = useQuery({ queryKey: ["profiles"], queryFn: catalogService.profiles });

  useEffect(() => { document.title = "Generate timetable — Tempo"; }, []);
  useEffect(() => {
    if (!form.academic_term_id && terms.data?.length) {
      const term = terms.data.find((item) => item.is_active) ?? terms.data[0];
      setForm((current) => ({ ...current, academic_term_id: term.id, name: `${term.name} timetable` }));
    }
  }, [terms.data, form.academic_term_id]);
  useEffect(() => {
    if (submittedHere && generation.status === "succeeded" && generation.result) {
      setSubmittedHere(false);
      navigate(`/runs/${generation.result.id}`, { state: { justGenerated: true } });
    }
  }, [generation.result, generation.status, navigate, submittedHere]);

  const availableProfiles = useMemo(
    () => profiles.data?.filter((profile) => profile.faculty_id === facultyId) ?? [],
    [profiles.data, facultyId],
  );
  const selectedFaculty = faculties.data?.find((item) => item.id === facultyId);
  const selectedProfile = availableProfiles.find((item) => item.id === form.scheduling_profile_id);
  const selectedTerm = terms.data?.find((item) => item.id === form.academic_term_id);
  const queryError = faculties.error ?? terms.error ?? profiles.error;
  const canSubmit = useMemo(
    () => facultyId > 0 && Boolean(form.name.trim()) && form.academic_term_id > 0 && Boolean(selectedProfile) && Number(timeLimitInput) >= 1 && generation.status !== "running",
    [facultyId, form, generation.status, selectedProfile, timeLimitInput],
  );

  function changeFaculty(nextFacultyId: number) {
    setFacultyId(nextFacultyId);
    setForm((current) => ({ ...current, scheduling_profile_id: 0 }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit || !selectedFaculty) return;
    setSubmittedHere(true);
    generation.startGeneration(
      {
        ...form,
        name: form.name.trim(),
        parameters: {
          ...form.parameters,
          time_limit_seconds: Number(timeLimitInput),
        },
      },
      `${selectedFaculty.code} — ${selectedFaculty.name}`,
    );
  }

  const isRunning = generation.status === "running";

  return (
    <div className="page page--narrow">
      <PageHeader
        eyebrow="New optimization run"
        title="Generate a timetable"
        description="Select a faculty first. Tempo then uses only that faculty’s profile, rooms, programs, groups and ready course sessions."
      />
      <form onSubmit={submit} className="generate-layout">
        <div className="generate-main">
          {queryError && <ErrorBanner message={getErrorMessage(queryError)} />}
          {generation.status === "failed" && <ErrorBanner message={generation.errorMessage} />}

          <section className="form-section panel">
            <div className="form-section__number">1</div>
            <div className="form-section__body">
              <div className="form-section__title">
                <h2>Faculty and teaching period</h2>
                <p>The selected scheduling profile determines the faculty scope used by the backend.</p>
              </div>
              <div className="form-grid">
                <label className="field field--full">
                  <span>Faculty</span>
                  <select value={facultyId} onChange={(event) => changeFaculty(Number(event.target.value))} disabled={isRunning} required>
                    <option value={0}>Select a faculty first</option>
                    {faculties.data?.map((faculty) => <option value={faculty.id} key={faculty.id}>{faculty.code} — {faculty.name}</option>)}
                  </select>
                  <small>One run generates a timetable for one faculty.</small>
                </label>
                <label className="field">
                  <span>Academic term</span>
                  <select value={form.academic_term_id} onChange={(event) => setForm({ ...form, academic_term_id: Number(event.target.value) })} disabled={isRunning} required>
                    <option value={0}>Select a term</option>
                    {terms.data?.map((term) => <option value={term.id} key={term.id}>{term.name} · {humanize(term.term_type)}</option>)}
                  </select>
                </label>
                <label className="field">
                  <span>Scheduling profile</span>
                  <select value={form.scheduling_profile_id} onChange={(event) => setForm({ ...form, scheduling_profile_id: Number(event.target.value) })} disabled={!facultyId || isRunning} required>
                    <option value={0}>{facultyId ? "Select a faculty profile" : "Choose faculty first"}</option>
                    {availableProfiles.map((profile) => <option value={profile.id} key={profile.id}>{profile.name}</option>)}
                  </select>
                  {facultyId > 0 && !profiles.isLoading && !availableProfiles.length && <small className="field-help--warning">This faculty has no active scheduling profile. Add one under Input data.</small>}
                </label>
                <label className="field field--full">
                  <span>Run name</span>
                  <input value={form.name} maxLength={150} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="e.g. Summer semester — FIEK final timetable" disabled={isRunning} required />
                  <small>A unique, clear name helps when comparing runtimes later.</small>
                </label>
              </div>
            </div>
          </section>

          <section className="form-section panel">
            <div className="form-section__number">2</div>
            <div className="form-section__body">
              <div className="form-section__title">
                <h2>Optimization strategy</h2>
                <p>All options enforce hard constraints; they differ in speed and optimization depth.</p>
              </div>
              <div className="algorithm-grid">
                {algorithms.map((algorithm) => (
                  <label className={`algorithm-card${form.algorithm === algorithm.value ? " selected" : ""}`} key={algorithm.value}>
                    <input type="radio" name="algorithm" checked={form.algorithm === algorithm.value} disabled={isRunning} onChange={() => setForm({ ...form, algorithm: algorithm.value })} />
                    <span className="algorithm-card__radio" />
                    <span><strong>{algorithm.name}{algorithm.tag && <em>{algorithm.tag}</em>}</strong><small>{algorithm.description}</small></span>
                  </label>
                ))}
              </div>
              <p className="comparison-hint">Run history records each algorithm’s runtime and score, so separate runs can be compared clearly.</p>
            </div>
          </section>

          <section className="form-section panel">
            <div className="form-section__number">3</div>
            <div className="form-section__body">
              <button type="button" className="advanced-toggle" onClick={() => setAdvancedOpen((open) => !open)}>
                <div><h2>Solver settings</h2><p>Fine-tune runtime and repeatability. The default 30-second limit is suitable for a demo.</p></div>
                <Icon name="chevron" className={advancedOpen ? "rotate" : ""} />
              </button>
              {advancedOpen && <div className="form-grid advanced-fields">
                <label className="field"><span>Time limit (seconds)</span><input type="text" inputMode="numeric" pattern="[0-9]*" value={timeLimitInput} disabled={isRunning} aria-invalid={timeLimitInput === "" || Number(timeLimitInput) < 1} onChange={(event) => setTimeLimitInput(event.target.value.replace(/\D/g, ""))} /><small>{timeLimitInput === "" || Number(timeLimitInput) < 1 ? "Enter at least 1 second." : "Maximum CP-SAT search time. Lower this value for faster demo runs."}</small></label>
                <label className="field"><span>Search workers</span><input type="number" min="1" step="1" value={form.parameters.num_search_workers} disabled={isRunning} onChange={(event) => setForm({ ...form, parameters: { ...form.parameters, num_search_workers: Number(event.target.value) } })} /><small>Parallel CPU workers used by CP-SAT; 8 is a balanced default.</small></label>
                <label className="field"><span>Random seed</span><input type="number" min="0" step="1" value={form.parameters.random_seed} disabled={isRunning} onChange={(event) => setForm({ ...form, parameters: { ...form.parameters, random_seed: Number(event.target.value) } })} /><small>Use the same seed to make comparison runs reproducible.</small></label>
                <label className="field"><span>Unused-seat weight</span><input type="number" min="0" step="1" value={form.parameters.unused_seat_weight} disabled={isRunning} onChange={(event) => setForm({ ...form, parameters: { ...form.parameters, unused_seat_weight: Number(event.target.value) } })} /><small>Higher values prefer rooms that fit attendance more closely.</small></label>
                <label className="check-field"><input type="checkbox" checked={form.parameters.spread_repeated_occurrences} disabled={isRunning} onChange={(event) => setForm({ ...form, parameters: { ...form.parameters, spread_repeated_occurrences: event.target.checked } })} /><span><strong>Spread repeated sessions</strong><small>Prefer different teaching days when a session occurs more than once per week.</small></span></label>
                <label className="check-field"><input type="checkbox" checked={form.parameters.log_search_progress} disabled={isRunning} onChange={(event) => setForm({ ...form, parameters: { ...form.parameters, log_search_progress: event.target.checked } })} /><span><strong>Log solver progress</strong><small>Print detailed CP-SAT diagnostics in the backend terminal.</small></span></label>
              </div>}
            </div>
          </section>
        </div>

        <aside className="run-summary panel">
          <p className="eyebrow">{isRunning ? "Generation status" : "Run summary"}</p>
          <h2>{isRunning ? "Solver is working" : "Ready to optimize"}</h2>
          {isRunning && <div className="generation-progress" aria-live="polite">
            <div className="generation-progress__time"><Spinner /><div><strong>{formatElapsed(generation.elapsedSeconds)}</strong><span>elapsed</span></div></div>
            <div className="progress-line"><i /></div>
            <ol>
              <li className="complete"><Icon name="check" /><span>Request accepted</span></li>
              <li className="active"><Spinner small /><span>Testing room and time combinations</span></li>
              <li><Icon name="clock" /><span>Validate and save the result</span></li>
            </ol>
            <p>You can open another page. Progress and completion will stay visible at the top.</p>
          </div>}
          <dl>
            <div><dt>Faculty</dt><dd>{selectedFaculty?.code ?? "Not selected"}</dd></div>
            <div><dt>Academic term</dt><dd>{selectedTerm?.name ?? "Not selected"}</dd></div>
            <div><dt>Profile</dt><dd>{selectedProfile?.name ?? "Not selected"}</dd></div>
            <div><dt>Slot duration</dt><dd>{selectedProfile ? `${selectedProfile.slot_minutes} minutes` : "—"}</dd></div>
            <div><dt>Algorithm</dt><dd>{humanize(form.algorithm)}</dd></div>
            <div><dt>Time limit</dt><dd>{timeLimitInput ? `${timeLimitInput} seconds` : "Not entered"}</dd></div>
          </dl>
          {!isRunning && <div className="summary-note"><Icon name="spark" /><p>The result opens automatically. After validation and publication, use Export CSV on the timetable page.</p></div>}
          <Button type="submit" disabled={!canSubmit}>{isRunning ? <><Spinner small /> Optimizing…</> : <><Icon name="play" /> Generate timetable</>}</Button>
          <small className="summary-footnote">Generation can continue while you use Run history or Input data.</small>
        </aside>
      </form>
    </div>
  );
}
