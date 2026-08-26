from fastapi import FastAPI
from app.core.exception_handlers import register_exception_handlers
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI(
    title=f"{settings.app_name} API",
    description="API for university timetable generation and resource allocation",
    version="0.1.0",
    debug=settings.debug,
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "message": "University Timetable Optimizer API is running",
    }
