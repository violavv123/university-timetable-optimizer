from app.models.enums import SchedulingAlgorithm
from app.scheduling.cp_sat_solver import CpSatTimetableSolver, HybridTimetableSolver
from app.scheduling.greedy_solver import GreedyTimetableSolver
from app.scheduling.metrics import calculate_metrics
from app.scheduling.solver_factory import get_timetable_solver
from tests.scheduling.factories import make_input


def test_solver_factory_maps_all_supported_algorithms() -> None:
    assert isinstance(
        get_timetable_solver(SchedulingAlgorithm.FIRST_FIT_DECREASING),
        GreedyTimetableSolver,
    )
    assert isinstance(
        get_timetable_solver(SchedulingAlgorithm.BEST_FIT_DECREASING),
        GreedyTimetableSolver,
    )
    assert isinstance(get_timetable_solver(SchedulingAlgorithm.CP_SAT), CpSatTimetableSolver)
    assert isinstance(get_timetable_solver(SchedulingAlgorithm.HYBRID), HybridTimetableSolver)


def test_metrics_report_capacity_and_assignment_counts() -> None:
    data = make_input()
    outcome = get_timetable_solver(SchedulingAlgorithm.BEST_FIT_DECREASING).solve(data)

    metrics = calculate_metrics(data, outcome.assignments)

    assert metrics.assigned_occurrences == 1
    assert metrics.unassigned_occurrences == 0
    assert metrics.rooms_used == 1
    assert metrics.unused_room_seats == 10
