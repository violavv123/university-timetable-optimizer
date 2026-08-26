from typing import Any, ClassVar


ErrorDetails = dict[str, Any] | list[Any] | None


class AppError(Exception):
    """Base class for expected, client-safe application errors."""

    status_code: ClassVar[int] = 500
    code: ClassVar[str] = "application_error"
    default_message: ClassVar[str] = "An application error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: ErrorDetails = None,
        headers: dict[str, str] | None = None,
        code: str | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = details
        self.headers = dict(headers) if headers else None
        self.error_code = code or self.code
        super().__init__(self.message)


class ResourceNotFoundError(AppError):
    status_code = 404
    code = "resource_not_found"
    default_message = "The requested resource was not found."

    def __init__(
        self,
        resource: str,
        identifier: int | str | None = None,
    ) -> None:
        details: dict[str, Any] = {"resource": resource}
        if identifier is not None:
            details["identifier"] = str(identifier)
        super().__init__(f"{resource} was not found.", details=details)


class DuplicateResourceError(AppError):
    status_code = 409
    code = "duplicate_resource"
    default_message = "A resource with the same unique values already exists."

    def __init__(
        self,
        resource: str,
        *,
        fields: list[str] | None = None,
    ) -> None:
        details: dict[str, Any] = {"resource": resource}
        if fields:
            details["fields"] = fields
        super().__init__(self.default_message, details=details)


class ConflictError(AppError):
    status_code = 409
    code = "resource_conflict"
    default_message = "The operation conflicts with the current resource state."


class ResourceInUseError(ConflictError):
    code = "resource_in_use"
    default_message = "The resource is still referenced and cannot be removed."


class InvalidStateTransitionError(ConflictError):
    code = "invalid_state_transition"
    default_message = "The requested state transition is not allowed."

    def __init__(
        self,
        resource: str,
        current_state: str,
        requested_state: str,
    ) -> None:
        super().__init__(
            self.default_message,
            details={
                "resource": resource,
                "current_state": current_state,
                "requested_state": requested_state,
            },
        )


class InactiveResourceError(ConflictError):
    code = "inactive_resource"
    default_message = "The operation requires an active resource."


class BusinessRuleError(AppError):
    status_code = 422
    code = "business_rule_violation"
    default_message = "The request violates a business rule."


class InvalidReferenceError(BusinessRuleError):
    code = "invalid_reference"
    default_message = "A referenced resource is missing or incompatible."


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_required"
    default_message = "Authentication is required."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message,
            headers={"WWW-Authenticate": "Bearer"},
        )


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"
    default_message = "You do not have permission to perform this operation."


class DataImportError(BusinessRuleError):
    code = "data_import_error"
    default_message = "The imported data is invalid."


class AvailabilityConflictError(ConflictError):
    code = "availability_conflict"
    default_message = "The availability window conflicts with another window."


class GroupHierarchyError(BusinessRuleError):
    code = "invalid_group_hierarchy"
    default_message = "The student-group hierarchy is invalid."


class DependencyCycleError(BusinessRuleError):
    code = "dependency_cycle"
    default_message = "The dependency would create a cycle."


class StaffQualificationError(BusinessRuleError):
    code = "staff_not_qualified"
    default_message = "The staff member is not qualified for the teaching role."


class RoomCompatibilityError(BusinessRuleError):
    code = "room_not_compatible"
    default_message = "The room does not satisfy the session requirements."


class SlotContinuityError(BusinessRuleError):
    code = "invalid_slot_sequence"
    default_message = "The session does not fit consecutive active time slots."


class SchedulingInputError(BusinessRuleError):
    code = "invalid_scheduling_input"
    default_message = "The scheduling input is incomplete or inconsistent."


class SchedulingInfeasibleError(ConflictError):
    code = "scheduling_infeasible"
    default_message = "No feasible timetable exists for the supplied constraints."


class TimetableConflictError(ConflictError):
    code = "timetable_conflict"
    default_message = "The timetable contains conflicting assignments."


class LockedEntryError(ConflictError):
    code = "timetable_entry_locked"
    default_message = "The locked timetable entry cannot be changed by this operation."


class TimetablePublishError(ConflictError):
    code = "timetable_publish_error"
    default_message = "The timetable run cannot be published in its current state."


class SolverExecutionError(AppError):
    status_code = 500
    code = "solver_execution_error"
    default_message = "The timetable solver failed to complete."


class PersistenceError(AppError):
    status_code = 500
    code = "persistence_error"
    default_message = "The operation could not be saved."
