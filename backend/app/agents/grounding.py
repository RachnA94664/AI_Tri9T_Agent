"""The "never invent records" rule, enforced in code instead of just asking nicely.

An answer may only mention record ids (REQ-001, TC-001, RISK-001) that appeared
in the text a tool returned. Anything else is treated as invented.
"""

import re
from collections.abc import Iterable

# \b on both sides so "REQ-0011" or "XREQ-001" are not mistaken for ids.
ID_PATTERN = re.compile(r"\b(?:REQ|TC|RISK)-\d{3}\b")


def find_ids(text: str) -> set[str]:
    return set(ID_PATTERN.findall(text or ""))


def ungrounded_ids(answer: str, evidence: Iterable[str]) -> set[str]:
    """Ids that the answer mentions but that no tool result contained."""
    seen: set[str] = set()
    for chunk in evidence:
        seen |= find_ids(chunk)
    return find_ids(answer) - seen
