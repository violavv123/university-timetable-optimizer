from __future__ import annotations

import argparse
import csv
from dataclasses import replace
from pathlib import Path

from app.models.enums import TimetableRunStatus
from app.scheduling.cp_sat_solver import CpSatTimetableSolver, HybridTimetableSolver
from app.scheduling.domain import RoomStrategy
from app.scheduling.greedy_solver import GreedyTimetableSolver
from app.scheduling.metrics import calculate_metrics
from tests.scheduling.factories import occurrence, room, scheduling_input, slot, start


def build_benchmark_input():
    slots = tuple(
        slot(
            slot_id,
            day=1 + (slot_id - 1) // 4,
            index=(slot_id - 1) % 4,
            start_minute=480 + ((slot_id - 1) % 4) * 45,
            week_index=slot_id - 1,
        )
        for slot_id in range(1, 13)
    )
    rooms = (
        room(1, "408", 120),
        room(2, "611", 80),
        room(3, "745", 60),
    )
    starts = tuple(start(value) for value in slots)
    allowed_pairs = frozenset(
        (candidate.start_slot_id, classroom.id)
        for candidate in starts
        for classroom in rooms
    )
    occurrences = tuple(
        replace(
            occurrence(
                session_id,
                starts[0],
                rooms[0],
                demand=25 + (session_id % 4) * 10,
                staff_id=100 + session_id,
                level_code="MSc" if session_id % 4 == 0 else "BSc",
            ),
            start_candidates=starts,
            compatible_room_ids=frozenset(classroom.id for classroom in rooms),
            allowed_start_room_pairs=allowed_pairs,
            student_resource_ids=frozenset({1000 + session_id}),
        )
        for session_id in range(1, 17)
    )
    return scheduling_input(
        slots=slots,
        rooms=rooms,
        occurrences=occurrences,
        parameters={
            "time_limit_seconds": 5.0,
            "num_search_workers": 2,
            "random_seed": 7,
            "spread_repeated_occurrences": False,
            "unused_seat_weight": 1,
        },
    )


def run_benchmark(output_path: Path) -> list[dict[str, object]]:
    data = build_benchmark_input()
    algorithms = (
        ("FFD", GreedyTimetableSolver(RoomStrategy.FFD)),
        ("BFD", GreedyTimetableSolver(RoomStrategy.BFD)),
        ("CP-SAT", CpSatTimetableSolver()),
        ("Hybrid", HybridTimetableSolver()),
    )
    rows: list[dict[str, object]] = []

    for algorithm_name, solver in algorithms:
        result = solver.solve(data)
        metrics = calculate_metrics(
            data,
            result.assignments,
            hard_conflicts=0 if result.status == TimetableRunStatus.SUCCEEDED else 1,
        )
        rows.append(
            {
                "algorithm": algorithm_name,
                "status": result.status.value,
                "execution_time_ms": result.execution_time_ms,
                **metrics.as_dict(),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare all timetable solvers on one deterministic dataset."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("performance_results.csv"),
        help="CSV file where benchmark metrics are written.",
    )
    args = parser.parse_args()
    rows = run_benchmark(args.output)

    print(
        "algorithm,status,execution_time_ms,assigned_occurrences,rooms_used,"
        "student_gap_slots,staff_gap_slots,late_bsc_slots,unused_room_seats,"
        "hard_conflicts,soft_penalty"
    )
    for row in rows:
        print(
            ",".join(
                str(row[field])
                for field in (
                    "algorithm",
                    "status",
                    "execution_time_ms",
                    "assigned_occurrences",
                    "rooms_used",
                    "student_gap_slots",
                    "staff_gap_slots",
                    "late_bsc_slots",
                    "unused_room_seats",
                    "hard_conflicts",
                    "soft_penalty",
                )
            )
        )
    print(f"Results written to {args.output}")


if __name__ == "__main__":
    main()
