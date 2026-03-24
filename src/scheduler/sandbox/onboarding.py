"""Sandbox onboarding — runs a single onboarding agent inside e2b.

Each agent (backfill, preferences, style) runs in its own sandbox.
The host launches three sandboxes in parallel. This module is the
entry point for each sandbox, selected via the ONBOARDING_AGENT env var.
"""

import logging
import os
import sys
from collections.abc import Awaitable, Callable

import anyio

from scheduler.onboarding.agent import _run_backfill_async as _run_backfill
from scheduler.guides.preferences import run_preferences_agent
from scheduler.guides.style import run_style_agent
from scheduler.sandbox.api_client import ControlPlaneClient

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_INITIAL_BACKOFF_S = 10


async def _with_retry(name: str, fn: Callable[..., Awaitable], *args) -> None:
    """Run *fn* with exponential backoff on API overload errors."""
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            await fn(*args)
            return
        except RuntimeError as exc:
            if "529" not in str(exc) and "Overloaded" not in str(exc):
                raise
            if attempt == _MAX_RETRIES:
                raise
            delay = _INITIAL_BACKOFF_S * (2 ** (attempt - 1))
            logger.warning(
                "%s: API overloaded (attempt %d/%d), retrying in %ds",
                name, attempt, _MAX_RETRIES, delay,
            )
            await anyio.sleep(delay)


async def _run_single(agent_name: str):
    control_plane_url = os.environ["CONTROL_PLANE_URL"]
    session_token = os.environ["SESSION_TOKEN"]
    lookback_days = int(os.environ.get("ONBOARDING_LOOKBACK_DAYS", "60"))

    backend = ControlPlaneClient(control_plane_url, session_token)

    if agent_name == "backfill":
        await _with_retry("backfill", _run_backfill, backend, lookback_days)
    elif agent_name == "preferences":
        await _with_retry("preferences", run_preferences_agent, backend)
    elif agent_name == "style":
        await _with_retry("style", run_style_agent, backend)
    else:
        raise ValueError(f"Unknown agent: {agent_name}")


def run_onboarding():
    """Entry point — runs the agent specified by ONBOARDING_AGENT env var."""
    agent_name = os.environ.get("ONBOARDING_AGENT")
    if not agent_name:
        print("Error: ONBOARDING_AGENT env var not set", file=sys.stderr)
        sys.exit(1)
    anyio.run(_run_single, agent_name)


if __name__ == "__main__":
    run_onboarding()
