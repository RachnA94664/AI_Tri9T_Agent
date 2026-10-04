"""Decide what a message is asking for. Rules first, the AI only when the rules cannot tell.

Intents:
  query         read or search the data
  update        propose a change to a requirement
  out_of_scope  not about our data (or the AI could not tell)
  refused       something the system never does (delete, confirm/reject by chat)
"""

import re
from dataclasses import dataclass

from app.agents.grounding import ID_PATTERN
from app.agents.llm import LLMClient
from app.agents.prompt_loader import load_prompt

FLAGS = re.IGNORECASE

# Never allowed through chat, whatever the wording or the "reason" given.
DELETE_WORDS = re.compile(r"\b(delete|remove|drop|erase|destroy|purge|wipe|truncate)\b", FLAGS)
# Confirming or rejecting a change is a human action in the UI, not a chat action.
CONFIRM_WORDS = re.compile(
    r"\b(confirm|apply|accept|reject|cancel|approve)\b.*\b(change|proposal|pending)\b", FLAGS
)

QUESTION_START = re.compile(
    r"^\s*(when|what|who|which|where|how|why|is|are|was|were|did|does|do|show|list|give|find"
    r"|get|tell|display|count|see)\b",
    FLAGS,
)
UPDATE_VERB = re.compile(
    r"\b(update|change|set|mark|move|promote|rename|edit|modify|make|approve)\b", FLAGS
)
FIELD_WORD = re.compile(r"\b(status|priority|title|description)\b", FLAGS)
DATA_WORDS = re.compile(
    r"\b(requirements?|test cases?|tests?|risks?|audit|history|high[- ]risk|without)\b", FLAGS
)


@dataclass(frozen=True)
class Route:
    intent: str  # query | update | out_of_scope | refused
    reason: str
    used_llm: bool = False


def route_by_rules(message: str) -> Route | None:
    """Return a Route if the rules are sure, or None if the message is unclear."""
    if DELETE_WORDS.search(message):
        return Route("refused", "deleting or removing data is not something I can do")
    if CONFIRM_WORDS.search(message):
        return Route("refused", "I can only propose changes; a person confirms them in the app")

    has_id = bool(ID_PATTERN.search(message))
    if QUESTION_START.match(message):
        return Route("query", "reads like a question or a request to show data")
    if UPDATE_VERB.search(message) and (has_id or FIELD_WORD.search(message)):
        return Route("update", "asks to change a requirement")
    if has_id or DATA_WORDS.search(message):
        return Route("query", "mentions our data")
    return None


def route_with_llm(llm: LLMClient, message: str) -> Route:
    """Ask the AI to classify a message the rules could not. Anything odd means out_of_scope."""
    response = llm.chat(
        [
            {"role": "system", "content": load_prompt("router")},
            {"role": "user", "content": message},
        ]
    )
    word = (response.content or "").strip().lower().strip(".'\"` ")
    if word in ("query", "update"):
        return Route(word, "classified by the AI", used_llm=True)
    return Route("out_of_scope", "not about requirements, test cases or risks", used_llm=True)


def route(llm: LLMClient, message: str) -> Route:
    return route_by_rules(message) or route_with_llm(llm, message)
