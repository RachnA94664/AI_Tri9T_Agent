"""Read-only endpoints. They only call `services.knowledge`."""

from fastapi import APIRouter

from app.api.deps import ERRORS, SessionDep
from app.api.schemas import AuditOut, RequirementOut, RiskOut, TestCaseOut
from app.services import knowledge

router = APIRouter()


@router.get("/requirements", response_model=list[RequirementOut], tags=["requirements"])
def list_requirements(session: SessionDep):
    """All requirements."""
    return knowledge.list_requirements(session)


# NOTE: this route must be declared BEFORE "/requirements/{requirement_id}",
# otherwise "without-tests" would be read as a requirement id.
@router.get(
    "/requirements/without-tests", response_model=list[RequirementOut], tags=["requirements"]
)
def requirements_without_tests(session: SessionDep):
    """Requirements that have no test cases."""
    return knowledge.list_requirements_without_tests(session)


@router.get(
    "/requirements/{requirement_id}",
    response_model=RequirementOut,
    responses={404: ERRORS[404], 422: ERRORS[422]},
    tags=["requirements"],
)
def get_requirement(requirement_id: str, session: SessionDep):
    """One requirement by id, for example REQ-001."""
    return knowledge.get_requirement(session, requirement_id)


@router.get(
    "/requirements/{requirement_id}/test-cases",
    response_model=list[TestCaseOut],
    responses={404: ERRORS[404], 422: ERRORS[422]},
    tags=["requirements"],
)
def test_cases_for_requirement(requirement_id: str, session: SessionDep):
    """Test cases that belong to a requirement."""
    return knowledge.get_test_cases_for_requirement(session, requirement_id)


@router.get("/risks", response_model=list[RiskOut], responses={422: ERRORS[422]}, tags=["risks"])
def list_risks(session: SessionDep, level: str | None = None):
    """Risk items, highest score first. Filter with ?level=high (low, medium or high)."""
    return knowledge.list_risks(session, level)


@router.get(
    "/audit-log", response_model=list[AuditOut], responses={422: ERRORS[422]}, tags=["audit"]
)
def audit_log(session: SessionDep, limit: int = 50, entity_id: str | None = None):
    """Most recent audit entries first (1 to 500). Optional ?entity_id=REQ-001."""
    return knowledge.audit_log(session, limit, entity_id)
