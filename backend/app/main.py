from fastapi import FastAPI
from app.core.exception_handlers import register_exception_handlers
from fastapi.middleware.cors import CORSMiddleware

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.database import SessionLocal

app = FastAPI(
    title="University Timetable Optimizer API",
    description="API for university timetable generation and resource allocation",
    version="0.1.0",
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "message": "University Timetable Optimizer API is running"
    }

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()