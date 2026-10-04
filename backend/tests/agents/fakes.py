"""A scripted fake AI for tests: no key, no network, no cost, same answer every time."""

import copy
import itertools

from app.agents.llm import LLMResponse, ToolCall

_ids = itertools.count(1)


class ScriptedLLM:
    """Returns the prepared responses in order and records every call it receives.

    If the code calls the AI MORE often than the test prepared for, it fails loudly:
    that is how tests prove "the AI was never asked" (use `ScriptedLLM()` with nothing).
    """

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def chat(self, messages, tools=None):
        self.calls.append({"messages": copy.deepcopy(messages), "tools": tools})
        if not self._responses:
            raise AssertionError("the AI was called more often than this test expected")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def say(text: str) -> LLMResponse:
    """The AI answers with plain text."""
    return LLMResponse(content=text)


def call(name: str, **arguments) -> LLMResponse:
    """The AI asks us to run one tool."""
    return LLMResponse(tool_calls=(ToolCall(f"call_{next(_ids)}", name, arguments),))


def calls(*specs: tuple[str, dict]) -> LLMResponse:
    """The AI asks for several tools in one go."""
    return LLMResponse(tool_calls=tuple(ToolCall(f"call_{next(_ids)}", n, a) for n, a in specs))
