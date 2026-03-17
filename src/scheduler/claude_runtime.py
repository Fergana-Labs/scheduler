"""Utilities for running nested Claude SDK sessions safely."""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator


logger = logging.getLogger(__name__)


@contextmanager
def nested_claude_session() -> Iterator[None]:
    """Clear parent CLI markers that can break nested SDK sessions."""
    original = os.environ.pop("CLAUDECODE", None)
    try:
        yield
    finally:
        if original is not None:
            os.environ["CLAUDECODE"] = original


def is_api_error_result(result: object) -> bool:
    """Return True when the SDK surfaced an API error as a string result."""
    return isinstance(result, str) and result.startswith("API Error:")
