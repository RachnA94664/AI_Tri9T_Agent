"""Load prompt text from the prompts/ folder. Prompts are files so they can be reviewed
and changed without touching code."""

from functools import lru_cache
from pathlib import Path

PROMPT_DIR = Path(__file__).parent / "prompts"


@lru_cache
def load_prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8").strip()
