import { useMemo, useState, type CSSProperties } from "react";
import { Icon } from "./Icon";
import { Badge, Button, EmptyState } from "./ui";
import { DAY_NAMES, WORK_DAYS, humanize, shortTime } from "../lib/format";
import type { DayOfWeek, ResolvedEntry, TimeSlot } from "../types";

const colorByType = { LECTURE: "green", NUMERICAL: "purple", LABORATORY: "gold" } as const;

export function TimetableGrid({ entries, slots, onToggleLock, lockingId }: { entries: ResolvedEntry[]; slots: TimeSlot[]; onToggleLock: (entry: ResolvedEntry) => void; lockingId?: number }) {
  const [selected, setSelected] = useState<ResolvedEntry | null>(null);
  const [showWeekend, setShowWeekend] = useState(false);
  const [query, setQuery] = useState("");
  const days: DayOfWeek[] = showWeekend ? [1, 2, 3, 4, 5, 6, 7] : WORK_DAYS;
  const rowIndices = useMemo(() => [...new Set(slots.map((slot) => slot.slot_index))].sort((a, b) => a - b), [slots]);
  const labels = useMemo(() => rowIndices.map((index) => slots.find((slot) => slot.slot_index === index)), [rowIndices, slots]);
  const filtered = entries.filter((entry) => `${entry.course?.name ?? ""} ${entry.course?.code ?? ""} ${entry.room?.code ?? ""} ${entry.staff.map((person) => `${person.first_name} ${person.last_name}`).join(" ")}`.toLowerCase().includes(query.toLowerCase()));

  if (!entries.length) return <EmptyState title="No assigned sessions" description="This run did not produce timetable entries." />;

  return (
    <>
      <div className="timetable-toolbar"><div className="search-box"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find a course, room or lecturer…" /></div><label className="switch-label"><input type="checkbox" checked={showWeekend} onChange={(event) => setShowWeekend(event.target.checked)} /><span className="switch" />Show weekend</label><div className="timetable-legend"><span><i className="legend-dot legend-dot--green" />Lecture</span><span><i className="legend-dot legend-dot--purple" />Exercises</span><span><i className="legend-dot legend-dot--gold" />Laboratory</span></div></div>
      <div className="timetable-scroll"><div className="timetable" style={{ "--days": days.length, "--rows": rowIndices.length } as CSSProperties}>
        <div className="timetable__corner">Time</div>{days.map((day) => <div className="timetable__day" key={day}><strong>{DAY_NAMES[day]}</strong><span>{filtered.filter((entry) => entry.slot?.day_of_week === day).length} sessions</span></div>)}
        <div className="timetable__times">{labels.map((slot, index) => <div key={rowIndices[index]}><strong>{shortTime(slot?.start_time)}</strong><span>{shortTime(slot?.end_time)}</span></div>)}</div>
        {days.map((day) => <div className="timetable__column" key={day} style={{ gridTemplateRows: `repeat(${rowIndices.length}, minmax(82px, 1fr))` }}>{rowIndices.map((row) => <div className="timetable__cell" key={row} />)}{filtered.filter((entry) => entry.slot?.day_of_week === day).map((entry) => {
          const start = rowIndices.indexOf(entry.slot?.slot_index ?? -1) + 1;
          const span = Math.max(1, Math.min(entry.session?.duration_slots ?? 1, rowIndices.length - start + 1));
          const color = entry.session ? colorByType[entry.session.component_type] : "green";
          return <button key={entry.id} className={`schedule-card schedule-card--${color}${entry.is_locked ? " schedule-card--locked" : ""}`} style={{ gridRow: `${start} / span ${span}` }} onClick={() => setSelected(entry)}><span className="schedule-card__time">{shortTime(entry.slot?.start_time)} · {entry.session?.duration_slots ?? 1} slot{(entry.session?.duration_slots ?? 1) > 1 ? "s" : ""}</span><strong>{entry.course?.code ?? entry.session?.name ?? `Session ${entry.course_session_id}`}</strong><small>{entry.course?.name ?? entry.session?.name}</small><span className="schedule-card__meta"><b>{entry.room?.code ?? `Room ${entry.room_id}`}</b>{entry.is_locked && <Icon name="lock" />}</span></button>;
        })}</div>)}
      </div></div>
      {selected && <div className="drawer-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelected(null); }}><aside className="detail-drawer"><button className="drawer-close" onClick={() => setSelected(null)} aria-label="Close"><Icon name="x" /></button><p className="eyebrow">Session details</p><h2>{selected.course?.name ?? selected.session?.name}</h2><p className="drawer-code">{selected.course?.code} · {humanize(selected.session?.component_type)}</p><div className="drawer-badges"><Badge tone={selected.session?.component_type === "LABORATORY" ? "warning" : "purple"}>{humanize(selected.session?.component_type)}</Badge>{selected.is_locked && <Badge tone="neutral">Locked</Badge>}</div><dl className="detail-list"><div><dt><Icon name="clock" />When</dt><dd>{selected.slot ? `${DAY_NAMES[selected.slot.day_of_week]}, ${shortTime(selected.slot.start_time)}–${shortTime(selected.slot.end_time)}` : "—"}</dd></div><div><dt><Icon name="grid" />Room</dt><dd>{selected.room ? `${selected.room.code} · ${selected.room.capacity} seats` : `Room #${selected.room_id}`}</dd></div><div><dt><Icon name="users" />Teaching staff</dt><dd>{selected.staff.length ? selected.staff.map((person) => `${person.first_name} ${person.last_name}`).join(", ") : "Not assigned"}</dd></div><div><dt><Icon name="book" />Student groups</dt><dd>{selected.groups.length ? selected.groups.map((group) => group.name).join(", ") : "Not assigned"}</dd></div><div><dt><Icon name="history" />Occurrence</dt><dd>{selected.occurrence_number} of {selected.session?.weekly_frequency ?? "—"} · {humanize(selected.assignment_source)}</dd></div></dl><Button variant={selected.is_locked ? "secondary" : "primary"} icon={selected.is_locked ? "unlock" : "lock"} disabled={lockingId === selected.id} onClick={() => onToggleLock(selected)}>{lockingId === selected.id ? "Saving…" : selected.is_locked ? "Unlock placement" : "Lock placement"}</Button><p className="drawer-hint">Locked placements are preserved when you create a re-optimized run.</p></aside></div>}
    </>
  );
}
