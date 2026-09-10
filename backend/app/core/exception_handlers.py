import logging
from collections.abc import Awaitable, Callable, Mapping
from http import HTTPStatus
from typing import Any, cast

from app.core.exceptions import AppError
from app.schemas.error import ErrorResponse
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import ExceptionHandler

logger = logging.getLogger(__name__)


POSTGRES_UNIQUE_VIOLATION = "23505"
POSTGRES_FOREIGN_KEY_VIOLATION = "23503"
POSTGRES_NOT_NULL_VIOLATION = "23502"
POSTGRES_CHECK_VIOLATION = "23514"

type TypedExceptionHandler[ExceptionT: Exception] = Callable[
    [Request, ExceptionT],
    Response | Awaitable[Response],
]


def _register_exception_handler[ExceptionT: Exception](
    app: FastAPI,
    exception_type: type[ExceptionT],
    handler: TypedExceptionHandler[ExceptionT],
) -> None:

    app.add_exception_handler(
        exception_type,
        cast(ExceptionHandler, handler),
    )


def _status_phrase(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Request failed"


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    safe_details = jsonable_encoder(details) if details is not None else None
    payload = ErrorResponse(
        code=code,
        message=message,
        details=safe_details,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json", exclude_none=True),
        headers=headers,
    )


def _database_sqlstate(exc: IntegrityError) -> str | None:
    original = exc.orig
    return getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    if exc.status_code >= 500:
        logger.error(
            "Application error during %s %s",
            request.method,
            request.url.path,
            exc_info=(type(exc), exc, exc.__traceback__),
        )

    return _error_response(
        status_code=exc.status_code,
        code=exc.error_code,
        message=exc.message,
        details=exc.details,
        headers=exc.headers,
    )


async def request_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    issues = [
        {
            "loc": list(error.get("loc", ())),
            "msg": error.get("msg", "Invalid value."),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]

    return _error_response(
        status_code=422,
        code="request_validation_error",
        message="The request contains invalid data.",
        details=issues,
    )


async def response_validation_error_handler(
    request: Request,
    exc: ResponseValidationError,
) -> JSONResponse:
    safe_errors = [
        {
            "loc": list(error.get("loc", ())),
            "msg": error.get("msg", "Invalid response value."),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
    logger.error(
        "Response validation failed during %s %s: %s",
        request.method,
        request.url.path,
        safe_errors,
        exc_info=(type(exc), exc, exc.__traceback__),
    )

    return _error_response(
        status_code=500,
        code="response_validation_error",
        message="The server produced an invalid response.",
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    default_code = f"http_{exc.status_code}"
    default_message = _status_phrase(exc.status_code)

    if isinstance(exc.detail, str):
        message = exc.detail or default_message
        details = None
    else:
        message = default_message
        details = exc.detail

    return _error_response(
        status_code=exc.status_code,
        code=default_code,
        message=message,
        details=details,
        headers=exc.headers,
    )


async def integrity_error_handler(
    request: Request,
    exc: IntegrityError,
) -> JSONResponse:
    sqlstate = _database_sqlstate(exc)
    logger.warning(
        "Database integrity error during %s %s; sqlstate=%s",
        request.method,
        request.url.path,
        sqlstate,
    )

    if sqlstate == POSTGRES_UNIQUE_VIOLATION:
        return _error_response(
            status_code=409,
            code="duplicate_resource",
            message="A resource with the same unique values already exists.",
        )

    if sqlstate == POSTGRES_FOREIGN_KEY_VIOLATION:
        return _error_response(
            status_code=409,
            code="foreign_key_conflict",
            message=(
                "The operation references a missing resource or a resource that is still in use."
            ),
        )

    if sqlstate == POSTGRES_NOT_NULL_VIOLATION:
        return _error_response(
            status_code=422,
            code="required_value_missing",
            message="A required database value is missing.",
        )

    if sqlstate == POSTGRES_CHECK_VIOLATION:
        return _error_response(
            status_code=422,
            code="database_constraint_violation",
            message="The submitted values violate a database constraint.",
        )

    return _error_response(
        status_code=409,
        code="database_integrity_error",
        message="The operation conflicts with existing database data.",
    )


async def operational_error_handler(
    request: Request,
    exc: OperationalError,
) -> JSONResponse:
    logger.error(
        "Database unavailable during %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return _error_response(
        status_code=503,
        code="database_unavailable",
        message="The database is temporarily unavailable.",
    )


async def sqlalchemy_error_handler(
    request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    logger.error(
        "Unexpected database error during %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return _error_response(
        status_code=500,
        code="database_error",
        message="An unexpected database error occurred.",
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.error(
        "Unhandled exception during %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return _error_response(
        status_code=500,
        code="internal_server_error",
        message="An unexpected server error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:

    _register_exception_handler(
        app,
        AppError,
        app_error_handler,
    )
    _register_exception_handler(
        app,
        RequestValidationError,
        request_validation_error_handler,
    )
    _register_exception_handler(
        app,
        ResponseValidationError,
        response_validation_error_handler,
    )
    _register_exception_handler(
        app,
        StarletteHTTPException,
        http_exception_handler,
    )
    _register_exception_handler(
        app,
        IntegrityError,
        integrity_error_handler,
    )
    _register_exception_handler(
        app,
        OperationalError,
        operational_error_handler,
    )
    _register_exception_handler(
        app,
        SQLAlchemyError,
        sqlalchemy_error_handler,
    )
    _register_exception_handler(
        app,
        Exception,
        unhandled_exception_handler,
    )
