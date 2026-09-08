from __future__ import annotations

from app.models.enums import SchedulingAlgorithm
from app.models.timetable_run import TimetableRun
from app.scheduling.cp_sat_solver import CpSatTimetableSolver, HybridTimetableSolver
from app.scheduling.domain import RoomStrategy, TimetableSolver
from app.scheduling.greedy_solver import GreedyTimetableSolver
from app.services.timetable.types import SolverOutcome
from sqlalchemy.orm import Session


def get_timetable_solver(algorithm: SchedulingAlgorithm) -> TimetableSolver:
    if algorithm == SchedulingAlgorithm.FIRST_FIT_DECREASING:
        return GreedyTimetableSolver(RoomStrategy.FFD)
    if algorithm == SchedulingAlgorithm.BEST_FIT_DECREASING:
        return GreedyTimetableSolver(RoomStrategy.BFD)
    if algorithm == SchedulingAlgorithm.CP_SAT:
        return CpSatTimetableSolver()
    if algorithm == SchedulingAlgorithm.HYBRID:
        return HybridTimetableSolver()
    raise ValueError(f"Unsupported scheduling algorithm: {algorithm}")


class DatabaseConfiguredTimetableSolver:
    """Select the concrete engine from the persisted run configuration."""

    def __call__(self, db: Session, run: TimetableRun) -> SolverOutcome:
        if run.algorithm is None:
            raise ValueError("Generated timetable runs require an algorithm.")
        solver = get_timetable_solver(run.algorithm)
        return solver(db, run)


__all__ = ["DatabaseConfiguredTimetableSolver", "get_timetable_solver"]
