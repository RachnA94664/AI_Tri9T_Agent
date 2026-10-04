"""The real OpenAI wrapper, tested WITHOUT any network: its inputs and outputs are faked."""

from types import SimpleNamespace

import httpx
import openai
import pytest

from app.agents.llm import OpenAIClient
from app.domain.errors import ServiceUnavailable

REQUEST = httpx.Request("POST", "http://example.invalid")


def make_client(create) -> OpenAIClient:
    client = OpenAIClient(api_key="test-key", model="m", timeout=5, max_output_tokens=100)
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    return client


def completion(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def tool_call(arguments: str, name="get_requirement", call_id="c1"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


def test_no_api_key_means_service_unavailable_not_a_crash():
    client = OpenAIClient(api_key="", model="m", timeout=5, max_output_tokens=100)
    with pytest.raises(ServiceUnavailable):
        client.chat([{"role": "user", "content": "hi"}])


def test_text_answers_are_returned():
    client = make_client(lambda **kw: completion(content="hello"))
    assert client.chat([{"role": "user", "content": "hi"}]).content == "hello"


def test_tool_calls_are_parsed_into_name_and_arguments():
    client = make_client(
        lambda **kw: completion(tool_calls=[tool_call('{"requirement_id": "REQ-001"}')])
    )
    response = client.chat([{"role": "user", "content": "x"}], tools=[{"type": "function"}])
    assert response.tool_calls[0].name == "get_requirement"
    assert response.tool_calls[0].arguments == {"requirement_id": "REQ-001"}


@pytest.mark.parametrize("bad", ["{not json", "[1, 2]", '"text"'])
def test_garbled_tool_arguments_become_an_error_marker_not_a_crash(bad):
    client = make_client(lambda **kw: completion(tool_calls=[tool_call(bad)]))
    response = client.chat([{"role": "user", "content": "x"}], tools=[{"type": "function"}])
    assert "__invalid_json__" in response.tool_calls[0].arguments


def test_requests_are_capped_and_use_temperature_zero():
    seen = {}

    def create(**kwargs):
        seen.update(kwargs)
        return completion(content="ok")

    make_client(create).chat([{"role": "user", "content": "x"}], tools=[{"type": "function"}])
    assert seen["temperature"] == 0 and seen["max_completion_tokens"] == 100
    assert seen["tools"] == [{"type": "function"}]


def test_provider_failures_become_service_unavailable_without_leaking_details():
    def create(**kwargs):
        raise openai.APIConnectionError(request=REQUEST)

    with pytest.raises(ServiceUnavailable) as exc:
        make_client(create).chat([{"role": "user", "content": "x"}])
    assert "not available" in exc.value.message


def test_a_model_that_rejects_temperature_is_retried_without_it():
    attempts = []

    def create(**kwargs):
        attempts.append(dict(kwargs))
        if "temperature" in kwargs:
            raise openai.BadRequestError(
                "Unsupported value: 'temperature' does not support 0 with this model.",
                response=httpx.Response(400, request=REQUEST),
                body=None,
            )
        return completion(content="ok")

    response = make_client(create).chat([{"role": "user", "content": "x"}])
    assert response.content == "ok"
    assert "temperature" in attempts[0] and "temperature" not in attempts[1]
