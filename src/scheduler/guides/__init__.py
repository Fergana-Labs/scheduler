"""Guide loading utilities for downstream agents."""

import logging

logger = logging.getLogger(__name__)


def load_guide(name: str, user_id: str | None = None) -> str | None:
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


def save_guide(name: str, content: str, user_id: str | None = None) -> None:
    if not user_id:
        return
    try:
        from scheduler.db import upsert_guide

        upsert_guide(user_id=user_id, name=name, content=content)
    except Exception:
        logger.warning("Failed to persist guide '%s' to database", name, exc_info=True)
