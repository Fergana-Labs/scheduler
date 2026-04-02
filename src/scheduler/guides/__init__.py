"""Guide loading utilities for downstream agents."""

import logging
import os

from scheduler.config import config

logger = logging.getLogger(__name__)


def _use_database() -> bool:
    """Whether to use the database for guide storage (production mode)."""
    return bool(config.database_url) or config.deployment_mode == "self_hosted"


def load_guide(name: str, user_id: str | None = None) -> str | None:
    """Load a guide file by name, returning None if it doesn't exist.

    In production (DATABASE_URL set): reads from the database only.
    In local dev (no DATABASE_URL): reads from the local filesystem only.

    Args:
        name: Guide name (without extension), e.g. "scheduling_preferences".
        user_id: Optional user ID for database lookup.

    Returns:
        The guide content as a string, or None if not found anywhere.
    """
    if _use_database():
        if not user_id:
            return None
        try:
            from scheduler.db import get_guide

            guide = get_guide(user_id=user_id, name=name)
            if guide:
                return guide.content
        except Exception:
            logger.warning("Failed to load guide '%s' from database", name, exc_info=True)
        return None

    # Local dev: read from filesystem
    path = os.path.join(config.guides_dir, f"{name}.md")
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return None


def save_guide(name: str, content: str, user_id: str | None = None, source: str = "manual") -> None:
    """Save a guide to the appropriate backend(s).

    In production (DATABASE_URL set): writes to the database only.
    In local dev (no DATABASE_URL): writes to the local filesystem only.
    When both DATABASE_URL and local dev are relevant (e.g. local dev with a
    database), writes to both.

    Args:
        name: Guide name (without extension).
        content: Guide content.
        user_id: Optional user ID for database persistence.
        source: Who wrote this version — 'onboarding', 'updater', 'manual', 'regenerate'.
    """
    if _use_database() and user_id:
        try:
            from scheduler.db import upsert_guide

            upsert_guide(user_id=user_id, name=name, content=content, source=source)
        except Exception:
            logger.warning("Failed to persist guide '%s' to database", name, exc_info=True)

    if not _use_database():
        os.makedirs(config.guides_dir, exist_ok=True)
        path = os.path.join(config.guides_dir, f"{name}.md")
        with open(path, "w") as f:
            f.write(content)
