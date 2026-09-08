from typing import Annotated

from app.database import get_db
from app.scheduling.solver_factory import DatabaseConfiguredTimetableSolver
from app.schemas.common import PaginationParams
from app.services.timetable.generation import TimetableSolver
from fastapi import Depends
from sqlalchemy.orm import Session

DbSession = Annotated[Session, Depends(get_db)]
Pagination = Annotated[PaginationParams, Depends()]


def get_timetable_solver() -> TimetableSolver:
    return DatabaseConfiguredTimetableSolver()


TimetableSolverDependency = Annotated[TimetableSolver, Depends(get_timetable_solver)]

__all__ = [
    "DbSession",
    "Pagination",
    "TimetableSolverDependency",
    "get_timetable_solver",
]
