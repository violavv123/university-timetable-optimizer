# University Timetable Optimizer

> Bachelor thesis project — automated generation of university course timetables using constraint programming and heuristic scheduling algorithms.

## Overview

Building a university timetable by hand means juggling room capacities, staff availability, student-group overlaps, elective clashes, and course-dependency rules all at once — a classic combinatorial optimization problem. This project implements a full system that turns a faculty's academic and resource data into a conflict-free weekly timetable automatically.

It consists of:

- A **FastAPI backend** that models the academic structure of a faculty (faculties, study programs, curricula, courses, staff, rooms, student groups) and exposes a REST API to manage that data and to generate, inspect, and re-optimize timetables.
- A **scheduling engine** offering multiple interchangeable algorithms — two greedy heuristics and a CP-SAT constraint-programming solver (optionally hybridized with a greedy warm start) — selectable per run.
- A **React + TypeScript frontend** for managing the input data and visualizing generated timetables.

The thesis contribution is centered on the scheduling engine: formalizing the timetabling problem as a constraint-satisfaction/optimization problem, implementing and comparing a heuristic baseline against an exact CP-SAT formulation, and evaluating solution quality and performance trade-offs on realistic faculty-sized data.

## Table of Contents

- [Problem Statement](#problem-statement)
- [Features](#features)
- [Architecture](#architecture)
- [Scheduling Algorithms](#scheduling-algorithms)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [API Overview](#api-overview)
- [Running Tests](#running-tests)
- [Thesis Context](#thesis-context)
- [License](#license)

## Problem Statement

Given, for one academic term:

- a set of **course sessions** (lecture / numerical / laboratory occurrences) that each need to occur one or more times per week,
- a pool of **rooms** with type and capacity constraints,
- **staff** and their availability/preference windows,
- **student groups** (cohorts, lecture groups, lab groups) that must not have overlapping sessions,
- explicit **dependencies** between sessions (e.g. a lab must follow its lecture, some sessions must fall on the same or different days, or run back-to-back), and
- a fixed grid of **time slots**,

the goal is to assign every session occurrence a `(start slot, room)` pair such that:

- no room, staff member, or student group is double-booked,
- all hard constraints (allowed/forbidden time windows, dependencies, room type/capacity requirements) are respected, and
- soft objectives are minimized — e.g. placement preference penalties and schedule "gaps" (idle periods) for staff and students.

This is an instance of the **University Course Timetabling Problem (UCTP)**, a well-studied NP-hard scheduling problem.

## Features

- **Full academic data model**: faculties → study programs → program semesters → curricula → courses → course offerings → course sessions, with academic years/terms.
- **Resource management**: rooms (with type/capacity/status), room availability, staff members and their course assignments/availability, student groups.
- **Scheduling input configuration**: time slots, scheduling profiles, session-to-session dependencies, per-session time constraints (allowed/forbidden/preferred/fixed windows), and program room preferences.
- **Four selectable scheduling algorithms** per timetable run (see below), with locked/preserved assignments supported for re-optimization.
- **Timetable lifecycle**: generate → inspect diagnostics/metrics → publish → re-optimize, with full session-assignment views.
- **JWT-based admin authentication** for all protected API routes.
- **Idempotent database seeding** with a realistic multi-program faculty fixture for demoing and testing.
- **React dashboard** for data entry, run management, and timetable visualization.

## Architecture

```
                        ┌──────────────────────────┐
                        │      React Frontend       │
                        │  (Vite + TS + React Query)│
                        └────────────┬─────────────┘
                                     │ REST (Axios)
                        ┌────────────▼─────────────┐
                        │       FastAPI Backend      │
                        │ ┌───────────────────────┐  │
                        │ │ Routers (auth, academic,│ │
                        │ │ resources, scheduling-  │ │
                        │ │ input, timetable)       │ │
                        │ └──────────┬────────────┘  │
                        │            │                │
                        │ ┌──────────▼────────────┐  │
                        │ │ Services layer          │ │
                        │ │ (validation + business  │ │
                        │ │  logic per domain)      │ │
                        │ └──────────┬────────────┘  │
                        │            │                │
                        │ ┌──────────▼────────────┐  │
                        │ │ Scheduling engine       │ │
                        │ │ (solver_factory ->      │ │
                        │ │  Greedy / CP-SAT /      │ │
                        │ │  Hybrid solver)         │ │
                        │ └──────────┬────────────┘  │
                        │            │                │
                        │ ┌──────────▼────────────┐  │
                        │ │ SQLAlchemy models +     │ │
                        │ │ Alembic migrations      │ │
                        │ └──────────┬────────────┘  │
                        └────────────┼───────────────┘
                                     │
                              ┌──────▼──────┐
                              │ PostgreSQL   │
                              └─────────────┘
```

Each router is protected by an `require_admin` JWT dependency (except `/auth/token`). Business rules (uniqueness, cross-entity validation, availability conflicts, curriculum consistency, etc.) live in the `services` layer, keeping routers thin and the scheduling engine decoupled from the web layer — the solvers only depend on a `SchedulingInput` domain object built by `input_loader`, not on the database session directly.

## Scheduling Algorithms

Selectable via `SchedulingAlgorithm` on a timetable run:

| Algorithm | Approach |
|---|---|
| `FIRST_FIT_DECREASING` | Greedy heuristic: orders session occurrences by decreasing "difficulty" (constraint tightness) and assigns each to the first feasible `(slot, room)` pair. |
| `BEST_FIT_DECREASING` | Same greedy ordering, but picks the room that best fits the session's requirements (e.g. tightest capacity match) among feasible options. |
| `CP_SAT` | Exact constraint-programming formulation solved with Google OR-Tools CP-SAT: each occurrence gets `start_option`/`room_option` integer decision variables, `NoOverlap`-style interval constraints enforce room/staff/student-group exclusivity, dependency constraints link related occurrences, and a weighted objective minimizes placement penalties plus staff/student schedule gaps. |
| `HYBRID` | Runs the CP-SAT model but warm-starts it with a solution from the `BEST_FIT_DECREASING` greedy solver via solver hints, to help the search converge faster. |

All algorithms share the same validated `SchedulingInput`/`SolverResult` domain contracts, a common metrics module (`app/scheduling/metrics.py`) for objective/penalty reporting, and result validation (`app/scheduling/result_validator.py`) that checks the final assignment set for hard-constraint violations regardless of which solver produced it.

## Tech Stack

**Backend**
- Python 3.13, FastAPI, Pydantic v2 / pydantic-settings
- SQLAlchemy 2.x + Alembic (PostgreSQL)
- Google OR-Tools (CP-SAT) for the exact solver
- JWT auth (PyJWT) with Argon2 password hashing
- pytest, ruff, mypy

**Frontend**
- React 19 + TypeScript, Vite
- TanStack React Query for data fetching/caching
- React Router
- Axios

## Project Structure

```
university-timetable-optimizer/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI app + CORS + health check
│   │   ├── config.py               # Settings (env-driven)
│   │   ├── database.py             # SQLAlchemy session/engine setup
│   │   ├── core/                   # Security (JWT/auth) & exception handling
│   │   ├── models/                 # SQLAlchemy ORM models + enums
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   ├── routers/                # API endpoints (academic, resources,
│   │   │                            #   scheduling_input, timetable, auth)
│   │   ├── services/                # Business logic per domain area
│   │   ├── scheduling/              # Domain model, solvers, validators, metrics
│   │   └── seeds/                   # Idempotent demo/test data fixture
│   ├── migrations/                 # Alembic migrations
│   ├── tests/                      # pytest suite (unit + service + solver)
│   ├── requirements.txt / requirements-dev.txt
│   └── pyproject.toml              # ruff/mypy/pytest config
└── frontend/
    ├── src/
    │   ├── pages/                   # Dashboard, Data Overview, Generate,
    │   │                            #   Input Management, Login, Runs, Timetable...
    │   ├── services/                # API client layer (axios + typed calls)
    │   ├── types/                   # Shared TS domain types
    │   └── styles/
    └── package.json
```

## Getting Started

### Prerequisites

- Python 3.13+
- Node.js 20+
- PostgreSQL 14+ (a running instance and an empty database)

### Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt   # or requirements.txt for a production-only install

cp .env.example .env
# Edit .env: set DATABASE_URL to your Postgres instance, and generate
# ADMIN_PASSWORD_HASH (argon2) and JWT_SECRET_KEY, e.g.:
python -c "from app.core.security import hash_password; print(hash_password('choose-a-password'))"
python -c "import secrets; print(secrets.token_urlsafe(48))"

alembic upgrade head              # apply database migrations

python -m app.seeds.seed_database             # load demo fixture data
python -m app.seeds.seed_database --reset     # or: wipe and reseed atomically

uvicorn app.main:app --reload     # http://127.0.0.1:8000
```

Interactive API docs are then available at `http://127.0.0.1:8000/docs`.

### Frontend setup

```bash
cd frontend
cp .env.example .env    # VITE_API_URL, defaults to http://127.0.0.1:8000/api
npm install
npm run dev              # http://localhost:5173
```

Log in with the `ADMIN_USERNAME` / password you configured on the backend.

## API Overview

All routes are namespaced under `/api/v1`. Every group besides `/auth` requires a bearer token obtained from `/auth/token`.

| Group | Purpose |
|---|---|
| `/auth` | Login (`POST /token`) and current-user lookup (`GET /me`) |
| `/academic` | Faculties, levels, study programs, program semesters, academic years/terms, courses, curricula, elective groups |
| `/resources` | Rooms, room availability, staff members, staff-course assignments, staff availability, student groups |
| `/scheduling-input` | Time slots, scheduling profiles, course offerings/sessions, session dependencies, time constraints, program room preferences |
| `/timetable` | Trigger timetable generation runs, inspect run status/diagnostics, view/edit session assignments, publish and re-optimize timetables |

## Running Tests

```bash
cd backend
pytest                       # full suite (unit tests run without extra setup)
pytest -m integration        # requires a migrated PostgreSQL test database
ruff check .                 # lint
mypy .                       # type-check
```

The `backend/tests/scheduling/` package contains dedicated tests for each solver (greedy strategies, CP-SAT, dependency rules, metrics, and room heuristics), independent of the API and database layers.

## Thesis Context

- **Author:** _Viola Resyli_
- **Institution / Faculty:** _"Universiteti i Prishtinës" - "Fakulteti i Inxhinierisë Elektrike Kompjuterike"_
- **Supervisor:** _Prof. Avni Rexhepi_
- **Academic year:** _2025/26_



