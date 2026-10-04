"""POST /chat over HTTP, with a fake AI behind it."""

import pytest

from app.agents.llm import OpenAIClient
from app.api.deps import get_llm
from app.domain.errors import ServiceUnavailable
from app.main import app
from tests.agents.fakes import ScriptedLLM, call, say


def use_llm(llm):
    app.dependency_overrides[get_llm] = lambda: llm  # the `api` fixture clears this afterwards


def test_chat_answers_from_the_database(api):
    use_llm(
        ScriptedLLM(
            call("list_requirements_without_tests"),
            say("REQ-012, REQ-013, REQ-014 and REQ-015 have no test cases."),
        )
    )
    r = api.post("/chat", json={"message": "Which requirements don't have test cases?"})

    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "query" and body["grounded"] is True
    assert [x["id"] for x in body["records"]] == ["REQ-012", "REQ-013", "REQ-014", "REQ-015"]
    assert body["tool_calls"][0]["name"] == "list_requirements_without_tests"
    assert body["pending_changes"] == []


def test_chat_update_proposes_and_a_person_then_confirms_over_the_api(api):
    use_llm(
        ScriptedLLM(
            call("propose_requirement_change", requirement_id="REQ-007", status="implemented"),
            say("ok"),
        )
    )
    r = api.post("/chat", json={"message": "Set REQ-007 status to implemented"})
    proposal = r.json()["pending_changes"][0]

    assert r.status_code == 200 and proposal["change"]["status"] == "pending"
    assert api.get("/requirements/REQ-007").json()["status"] == "approved"  # not applied by chat

    pending = api.get("/changes").json()
    assert pending[0]["proposed_by"] == "update-agent"

    confirm = api.post(f"/changes/{proposal['change']['id']}/confirm", json={"actor": "rachna"})
    assert confirm.status_code == 200
    assert api.get("/requirements/REQ-007").json()["status"] == "implemented"

    sources = [e["source"] for e in api.get("/audit-log", params={"entity_id": "REQ-007"}).json()]
    assert sources == ["ui", "agent"]  # confirmed by a person (ui); proposed by the agent


def test_a_delete_request_is_refused_even_when_the_ai_is_unavailable(api):
    use_llm(ScriptedLLM(ServiceUnavailable("down")))  # would fail if it were asked
    r = api.post("/chat", json={"message": "Delete REQ-001"})

    assert r.status_code == 200 and r.json()["refused"] is True
    assert api.get("/requirements/REQ-001").status_code == 200


def test_missing_api_key_is_a_clean_503_not_a_crash(api):
    use_llm(OpenAIClient(api_key="", model="m", timeout=5, max_output_tokens=10))
    r = api.post("/chat", json={"message": "hello"})  # unclear message: needs the AI

    assert r.status_code == 503
    assert r.json()["error"]["code"] == "service_unavailable"
    assert "OPENAI_API_KEY" in r.json()["error"]["message"]  # names the setting, not the key


def test_rule_based_questions_still_fail_cleanly_when_the_ai_is_down(api):
    use_llm(ScriptedLLM(ServiceUnavailable("the AI service is not available right now")))
    r = api.post("/chat", json={"message": "Show me REQ-001"})

    assert r.status_code == 503 and r.json()["error"]["code"] == "service_unavailable"


@pytest.mark.parametrize(
    "body",
    [
        {},  # no message
        {"message": "x" * 1001},  # too long
        {"message": "hi", "source": "agent"},  # unknown field
        {"message": 123},
    ],
)
def test_bad_chat_requests_are_422(api, body):
    use_llm(ScriptedLLM())
    assert api.post("/chat", json=body).status_code == 422


def test_a_blank_message_is_422(api):
    use_llm(ScriptedLLM())
    r = api.post("/chat", json={"message": "   "})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
