from app.core.security import require_admin
from app.routers.academic import router as academic_router
from app.routers.auth import router as auth_router
from app.routers.resources import router as resources_router
from app.routers.scheduling_input import router as scheduling_input_router
from app.routers.timetable import router as timetable_router
from fastapi import APIRouter, Depends

api_router = APIRouter()
api_router.include_router(auth_router)

protected_router = APIRouter(
    dependencies=[Depends(require_admin)],
)
protected_router.include_router(academic_router)
protected_router.include_router(resources_router)
protected_router.include_router(scheduling_input_router)
protected_router.include_router(timetable_router)

api_router.include_router(protected_router)

__all__ = ["api_router"]
