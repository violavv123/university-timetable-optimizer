from typing import Annotated

from app.database import get_db
from app.schemas.common import PaginationParams
from app.services.timetable.generation import TimetableSolver
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

DbSession = Annotated[Session, Depends(get_db)]
Pagination = Annotated[PaginationParams, Depends()]


def get_timetable_solver() -> TimetableSolver:
    """Dependency seam for the optimization engine added in the next phase."""

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="No timetable solver has been configured.",
    )


TimetableSolverDependency = Annotated[TimetableSolver, Depends(get_timetable_solver)]

__all__ = [
    "DbSession",
    "Pagination",
    "TimetableSolverDependency",
    "get_timetable_solver",
]
