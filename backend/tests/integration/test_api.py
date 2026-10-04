"""HTTP-level tests: status codes, the error shape, and the safety rules."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import knowledge


def propose(api, req_id="REQ-007", patch=None, who="rachna"):
    patch = patch or {"status": "implemented"}
    return api.post("/changes", json={"requirement_id": req_id, "patch": patch, "proposed_by": who})


# ---------- reading ----------


def test_health_reports_database_ok(api):
    r = api.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_list_requirements(api):
    r = api.get("/requirements")
    assert r.status_code == 200
    assert len(r.json()) == 15


def test_get_one_requirement(api):
    r = api.get("/requirements/REQ-001")
    assert r.status_code == 200
    assert r.json()["id"] == "REQ-001" and r.json()["version"] == 1


def test_unknown_requirement_is_404_with_the_standard_error_shape(api):
    r = api.get("/requirements/REQ-099")
    assert r.status_code == 404
    error = r.json()["error"]
    assert error["code"] == "not_found" and "REQ-099" in error["message"]


def test_malformed_id_is_422(api):
    r = api.get("/requirements/banana")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_without_tests_route_is_not_mistaken_for_an_id(api):
    r = api.get("/requirements/without-tests")
    assert r.status_code == 200
    assert [x["id"] for x in r.json()] == ["REQ-012", "REQ-013", "REQ-014", "REQ-015"]


def test_test_cases_for_a_requirement(api):
    r = api.get("/requirements/REQ-001/test-cases")
    assert [t["id"] for t in r.json()] == ["TC-001", "TC-002", "TC-003", "TC-027"]


def test_test_cases_for_unknown_requirement_is_404(api):
    assert api.get("/requirements/REQ-099/test-cases").status_code == 404


def test_high_risks(api):
    r = api.get("/risks", params={"level": "high"})
    assert [x["id"] for x in r.json()] == ["RISK-002"]
    assert r.json()[0]["score"] == 15


def test_bad_risk_level_is_422(api):
    assert api.get("/risks", params={"level": "extreme"}).status_code == 422


@pytest.mark.parametrize("limit", ["0", "501", "abc"])
def test_bad_audit_limit_is_422(api, limit):
    assert api.get("/audit-log", params={"limit": limit}).status_code == 422


# ---------- propose / confirm / reject ----------


def test_propose_returns_201_and_applies_nothing(api):
    r = propose(api)
    assert r.status_code == 201
    body = r.json()
    assert body["change"]["status"] == "pending"
    assert body["preview"] == {"status": {"old": "approved", "new": "implemented"}}
    assert api.get("/requirements/REQ-007").json()["status"] == "approved"  # unchanged
    assert len(api.get("/changes").json()) == 1


def test_invalid_transition_is_409(api):
    r = propose(api, patch={"status": "draft"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "invalid_transition"
    assert api.get("/changes").json() == []


def test_propose_for_unknown_requirement_is_404(api):
    assert propose(api, req_id="REQ-099").status_code == 404


def test_confirm_applies_the_change_and_bumps_the_version(api):
    change_id = propose(api).json()["change"]["id"]

    r = api.post(f"/changes/{change_id}/confirm", json={"actor": "rachna"})

    assert r.status_code == 200
    assert r.json()["already_applied"] is False
    assert r.json()["requirement"]["version"] == 2
    assert api.get("/requirements/REQ-007").json()["status"] == "implemented"


def test_confirming_twice_is_harmless(api):
    change_id = propose(api).json()["change"]["id"]
    api.post(f"/changes/{change_id}/confirm", json={"actor": "rachna"})

    r = api.post(f"/changes/{change_id}/confirm", json={"actor": "rachna"})

    assert r.status_code == 200 and r.json()["already_applied"] is True
    assert api.get("/requirements/REQ-007").json()["version"] == 2


def test_stale_change_is_409(api):
    first = propose(api, patch={"status": "implemented"}).json()["change"]["id"]
    second = propose(api, patch={"status": "obsolete"}).json()["change"]["id"]
    api.post(f"/changes/{first}/confirm", json={"actor": "rachna"})

    r = api.post(f"/changes/{second}/confirm", json={"actor": "rachna"})

    assert r.status_code == 409 and r.json()["error"]["code"] == "conflict"
    assert api.get("/requirements/REQ-007").json()["status"] == "implemented"


def test_reject_then_confirm_is_409(api):
    change_id = propose(api).json()["change"]["id"]
    assert api.post(f"/changes/{change_id}/reject", json={"actor": "rachna"}).status_code == 200
    assert api.post(f"/changes/{change_id}/confirm", json={"actor": "rachna"}).status_code == 409
    assert api.get("/requirements/REQ-007").json()["status"] == "approved"


def test_confirm_unknown_change_is_404(api):
    assert api.post("/changes/9999/confirm", json={"actor": "rachna"}).status_code == 404


def test_change_id_must_be_a_number(api):
    assert api.post("/changes/abc/confirm", json={"actor": "rachna"}).status_code == 422


# ---------- audit log ----------


def test_audit_log_records_proposal_and_update(api):
    change_id = propose(api).json()["change"]["id"]
    api.post(f"/changes/{change_id}/confirm", json={"actor": "rachna"})

    entries = api.get("/audit-log", params={"entity_id": "REQ-007"}).json()

    assert [e["action"] for e in entries] == ["update", "propose"]  # newest first
    assert entries[0]["old_value"] == {"status": "approved"}
    assert entries[0]["new_value"] == {"status": "implemented"}
    assert all(e["source"] == "ui" for e in entries)


# ---------- safety rules ----------


def test_client_cannot_claim_to_be_an_agent(api):
    body = {
        "requirement_id": "REQ-007",
        "patch": {"status": "implemented"},
        "proposed_by": "rachna",
        "source": "agent",  # not allowed: the server decides the source
    }
    r = api.post("/changes", json=body)
    assert r.status_code == 422


def test_client_cannot_set_the_version_or_id_through_a_patch(api):
    assert propose(api, patch={"version": 99}).status_code == 422
    assert propose(api, patch={"id": "REQ-500"}).status_code == 422


def test_missing_body_fields_are_422(api):
    r = api.post("/changes", json={"requirement_id": "REQ-007"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_records_cannot_be_edited_or_deleted_directly(api, method):
    r = getattr(api, method)("/requirements/REQ-001")
    assert r.status_code == 405


def test_unexpected_errors_do_not_leak_details(api, monkeypatch):
    def boom(_session):
        raise RuntimeError("secret database password is hunter2")

    monkeypatch.setattr(knowledge, "list_requirements", boom)
    quiet_client = TestClient(app, raise_server_exceptions=False)

    r = quiet_client.get("/requirements")

    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    assert "hunter2" not in r.text


# ---------- CORS ----------


def test_cors_allows_the_configured_frontend(api):
    r = api.options(
        "/requirements",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_blocks_other_origins(api):
    r = api.options(
        "/requirements",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in r.headers
