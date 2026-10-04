"""The ONLY place that talks to the AI provider.

Everything else depends on the small `LLMClient` interface below. That gives us:
  * tests that use a fake AI (no key, no cost, deterministic)
  * the freedom to change provider without touching the agents
Messages use the common "chat" format: dicts with a role and content.
"""

import json
import logging
from dataclasses import dataclass
from typing import Protocol

import openai

from app.core.config import get_settings
from app.domain.errors import ServiceUnavailable

logger = logging.getLogger("app.llm")


@dataclass(frozen=True)
class ToolCall:
    """The model asking us to run one of our tools."""

    id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class LLMResponse:
    """What the model said: text, or tool calls, or both."""

    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


class LLMClient(Protocol):
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse: ...


class OpenAIClient:
    """Real client. Created lazily so the app starts (and rule-based paths work) without a key."""

    def __init__(self, api_key: str, model: str, timeout: float, max_output_tokens: int):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_output_tokens = max_output_tokens
        self._client: openai.OpenAI | None = None

    def _get_client(self) -> openai.OpenAI:
        if not self._api_key:
            raise ServiceUnavailable("the AI service is not configured (OPENAI_API_KEY is empty)")
        if self._client is None:
            # max_retries: the SDK retries rate limits / server errors with backoff.
            self._client = openai.OpenAI(
                api_key=self._api_key, timeout=self._timeout, max_retries=2
            )
        return self._client

    def _create(self, kwargs: dict):
        client = self._get_client()
        try:
            return client.chat.completions.create(**kwargs)
        except openai.BadRequestError as exc:
            # Some models do not accept `temperature`; retry once without it.
            if "temperature" in kwargs and "temperature" in str(exc).lower():
                retry = {k: v for k, v in kwargs.items() if k != "temperature"}
                return client.chat.completions.create(**retry)
            raise

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": 0,  # as repeatable as the model allows
            "max_completion_tokens": self._max_output_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        try:
            completion = self._create(kwargs)
        except ServiceUnavailable:
            raise
        except openai.OpenAIError as exc:
            # Log the kind of failure for us; tell the user nothing sensitive.
            logger.error("AI request failed: %s", type(exc).__name__)
            raise ServiceUnavailable("the AI service is not available right now") from exc

        message = completion.choices[0].message
        calls: list[ToolCall] = []
        for tc in message.tool_calls or []:
            function = getattr(tc, "function", None)
            if function is None:
                continue
            try:
                arguments = json.loads(function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {"__invalid_json__": function.arguments}
            if not isinstance(arguments, dict):
                arguments = {"__invalid_json__": function.arguments}
            calls.append(ToolCall(id=tc.id, name=function.name, arguments=arguments))
        return LLMResponse(content=message.content, tool_calls=tuple(calls))


def build_llm() -> LLMClient:
    s = get_settings()
    return OpenAIClient(
        api_key=s.openai_api_key,
        model=s.openai_model,
        timeout=s.openai_timeout_seconds,
        max_output_tokens=s.llm_max_output_tokens,
    )
