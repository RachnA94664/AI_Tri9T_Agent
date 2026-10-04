"""Tools: validated arguments, readable errors, and least privilege."""

import pytest

from app.agents import tools
from app.services import knowledge


def test_a_tool_returns_data_on_success(seeded):
    out = tools.GET_REQUIREMENT.run(seeded, {"requirement_id": "REQ-001"})
    assert out["ok"] is True and out["result"]["id"] == "REQ-001"


def test_a_missing_record_comes_back_as_data_not_an_exception(seeded):
    out = tools.GET_REQUIREMENT.run(seeded, {"requirement_id": "REQ-099"})
    assert out == {
        "ok": False,
        "error": {"code": "not_found", "message": "requirement REQ-099 does not exist"},
    }


@pytest.mark.parametrize(
    "tool,arguments",
    [
        (tools.GET_REQUIREMENT, {}),  # missing argument
        (tools.GET_REQUIREMENT, {"requirement_id": "REQ-001", "extra": 1}),  # unknown argument
        (tools.LIST_RISKS, {"level": "extreme"}),  # not an allowed value
        (tools.GET_AUDIT_LOG, {"limit": 0}),
        (tools.GET_AUDIT_LOG, {"limit": 1000}),
        (tools.PROPOSE_CHANGE, {"requirement_id": "REQ-007", "status": "banana"}),
        (tools.LIST_REQUIREMENTS, {"surprise": True}),
        (tools.GET_REQUIREMENT, {"__invalid_json__": "{not json"}),
    ],
)
def test_bad_arguments_are_rejected_before_anything_runs(seeded, tool, arguments):
    out = tool.run(seeded, arguments)
    assert out["ok"] is False and out["error"]["code"] == "invalid_arguments"


def test_propose_tool_saves_a_pending_change_attributed_to_the_agent(seeded):
    out = tools.PROPOSE_CHANGE.run(seeded, {"requirement_id": "REQ-007", "status": "implemented"})
    assert out["ok"] is True
    assert out["result"]["change"]["status"] == "pending"
    assert out["result"]["change"]["proposed_by"] == "update-agent"
    assert knowledge.get_requirement(seeded, "REQ-007")["status"] == "approved"  # not applied
    entry = knowledge.audit_log(seeded)[0]
    assert entry["source"] == "agent" and entry["action"] == "propose"


def test_propose_with_nothing_to_change_is_an_error(seeded):
    out = tools.PROPOSE_CHANGE.run(seeded, {"requirement_id": "REQ-007"})
    assert out["ok"] is False and out["error"]["code"] == "validation_error"


def test_an_invalid_status_move_is_reported_to_the_agent(seeded):
    out = tools.PROPOSE_CHANGE.run(seeded, {"requirement_id": "REQ-007", "status": "draft"})
    assert out["ok"] is False and out["error"]["code"] == "invalid_transition"


# ---------- least privilege ----------


def test_no_tool_can_confirm_reject_apply_or_delete():
    forbidden = ("confirm", "reject", "apply", "delete", "remove", "drop")
    for tool in tools.READ_TOOLS + tools.UPDATE_TOOLS:
        assert not any(word in tool.name for word in forbidden), tool.name


def test_the_read_agent_has_no_write_tool():
    assert not any(t.writes for t in tools.READ_TOOLS)


def test_the_update_agent_can_only_propose():
    assert [t.name for t in tools.UPDATE_TOOLS if t.writes] == ["propose_requirement_change"]


def test_tool_schemas_have_the_shape_the_ai_provider_expects():
    for tool in tools.READ_TOOLS + tools.UPDATE_TOOLS:
        schema = tool.schema()
        assert schema["type"] == "function"
        fn = schema["function"]
        assert fn["name"] == tool.name and fn["description"]
        assert fn["parameters"]["type"] == "object"
        assert "title" not in fn["parameters"]  # noise removed


def test_the_propose_schema_does_not_offer_id_or_version_as_fields():
    props = tools.PROPOSE_CHANGE.schema()["function"]["parameters"]["properties"]
    assert set(props) == {"requirement_id", "title", "description", "priority", "status"}
