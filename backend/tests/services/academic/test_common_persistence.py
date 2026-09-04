import pytest
from app.core.exceptions import DuplicateResourceError
from app.models.faculty import Faculty
from app.services.common import commit_and_refresh
from sqlalchemy.orm import Session
from tests.services.academic.factories import make_faculty

pytestmark = pytest.mark.integration


def test_database_duplicate_is_translated_and_session_is_rolled_back(
    db: Session,
) -> None:
    existing = make_faculty(db, code="RACE-DUPLICATE")
    duplicate = Faculty(
        code=existing.code,
        name="Duplicate inserted after a competing request",
        is_active=True,
    )
    db.add(duplicate)

    with pytest.raises(DuplicateResourceError) as exc_info:
        commit_and_refresh(db, duplicate)

    assert exc_info.value.details == {
        "resource": "Faculty",
        "fields": ["code"],
    }

    # rollback() inside commit_transaction must leave the Session reusable.
    assert db.get(Faculty, existing.id) is not None
    recovered = make_faculty(db)
    assert recovered.id > existing.id
