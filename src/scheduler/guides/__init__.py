"""Guide loading utilities for downstream agents."""

import os

from scheduler.config import config


def load_guide(name: str) -> str | None:
    """Load a guide file by name, returning None if it doesn't exist.

    Args:
        name: Guide name (without extension), e.g. "scheduling_preferences".

    Returns:
        The guide content as a string, or None if the file doesn't exist.
    """
    path = os.path.join(config.guides_dir, f"{name}.md")
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return None
