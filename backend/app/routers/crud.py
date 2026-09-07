from collections.abc import Callable
from typing import Annotated, Any

from app.routers.dependencies import DbSession, Pagination
from app.schemas.common import MessageResponse, PaginatedResponse
from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

GetService = Callable[[Session, int], Any]
ListService = Callable[..., Any]
CreateService = Callable[[Session, Any], Any]
UpdateService = Callable[[Session, int, Any], Any]
DeleteService = Callable[[Session, int], MessageResponse]
PositivePathId = Annotated[int, Path(gt=0)]


class EmptyFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")


def register_crud_routes(
    router: APIRouter,
    *,
    path: str,
    resource_name: str,
    read_schema: type[BaseModel],
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    get_service: GetService,
    list_service: ListService,
    create_service: CreateService,
    update_service: UpdateService,
    delete_service: DeleteService,
    filters_schema: type[BaseModel] = EmptyFilters,
) -> None:
    """Register the standard list/get/create/update/delete HTTP contract."""

    operation_prefix = resource_name.replace(" ", "_").lower()
    filters_dependency = Depends(filters_schema)

    def list_resources(
        db: DbSession,
        pagination: Pagination,
        filters: BaseModel = filters_dependency,
    ) -> Any:
        return list_service(
            db,
            pagination,
            **filters.model_dump(exclude_none=True),
        )

    list_resources.__name__ = f"list_{operation_prefix}s"
    list_resources.__annotations__["filters"] = filters_schema

    def create_resource(
        payload: Any,
        db: DbSession,
    ) -> Any:
        return create_service(db, payload)

    create_resource.__name__ = f"create_{operation_prefix}"
    create_resource.__annotations__["payload"] = create_schema
    create_resource.__annotations__["return"] = read_schema

    def read_resource(
        resource_id: PositivePathId,
        db: DbSession,
    ) -> Any:
        return get_service(db, resource_id)

    read_resource.__name__ = f"get_{operation_prefix}"
    read_resource.__annotations__["return"] = read_schema

    def update_resource(
        payload: Any,
        resource_id: PositivePathId,
        db: DbSession,
    ) -> Any:
        return update_service(db, resource_id, payload)

    update_resource.__name__ = f"update_{operation_prefix}"
    update_resource.__annotations__["payload"] = update_schema
    update_resource.__annotations__["return"] = read_schema

    def delete_resource(
        resource_id: PositivePathId,
        db: DbSession,
    ) -> MessageResponse:
        return delete_service(db, resource_id)

    delete_resource.__name__ = f"delete_{operation_prefix}"

    router.add_api_route(
        path,
        list_resources,
        methods=["GET"],
        response_model=PaginatedResponse[read_schema],  # type: ignore[valid-type]
        operation_id=f"list_{operation_prefix}s",
        summary=f"List {resource_name}s",
    )
    router.add_api_route(
        path,
        create_resource,
        methods=["POST"],
        response_model=read_schema,
        status_code=status.HTTP_201_CREATED,
        operation_id=f"create_{operation_prefix}",
        summary=f"Create {resource_name}",
    )
    router.add_api_route(
        f"{path}/{{resource_id}}",
        read_resource,
        methods=["GET"],
        response_model=read_schema,
        operation_id=f"get_{operation_prefix}",
        summary=f"Get {resource_name}",
    )
    router.add_api_route(
        f"{path}/{{resource_id}}",
        update_resource,
        methods=["PATCH"],
        response_model=read_schema,
        operation_id=f"update_{operation_prefix}",
        summary=f"Update {resource_name}",
    )
    router.add_api_route(
        f"{path}/{{resource_id}}",
        delete_resource,
        methods=["DELETE"],
        response_model=MessageResponse,
        operation_id=f"delete_{operation_prefix}",
        summary=f"Delete {resource_name}",
    )


__all__ = ["EmptyFilters", "register_crud_routes"]
