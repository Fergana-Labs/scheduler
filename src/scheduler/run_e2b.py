"""Run the onboarding agent in an e2b cloud sandbox with control plane.

We mean "control plane" in the following sense: https://browser-use.com/posts/two-ways-to-sandbox-agents

Architecture:
1. Starts a FastAPI control plane server locally (holds Google OAuth tokens)
2. Generates a session token and registers it on the control plane
3. Spins up an e2b sandbox with only the slim sandbox agent code
4. The sandbox agent calls the control plane over HTTP — no tokens in the sandbox

Requires:
    - E2B_API_KEY env var
    - ANTHROPIC_API_KEY env var
    - Google OAuth token.json (used by the control plane, never sent to sandbox)
"""

import os
import secrets
import sys
import threading
import time
from pathlib import Path

import uvicorn
from e2b_code_interpreter import Sandbox

from scheduler.config import config
from scheduler.controlplane.server import app, register_session

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _collect_sandbox_files() -> list[dict]:
    """Collect only the files needed inside the sandbox.

    The sandbox only needs:
    - scheduler/sandbox/ (the agent + api_client)
    - scheduler/config.py (for reading env vars — though sandbox onboarding
      reads env directly, config.py is still imported transitively)
    - pyproject.toml (for pip install)
    """
    files = []
    sandbox_dir = PROJECT_ROOT / "src" / "scheduler" / "sandbox"
    for py_file in sandbox_dir.rglob("*.py"):
        rel_path = py_file.relative_to(PROJECT_ROOT / "src")
        files.append({
            "path": f"/home/user/scheduler/src/{rel_path}",
            "data": py_file.read_text(),
        })

    # Include the top-level package init
    init_file = PROJECT_ROOT / "src" / "scheduler" / "__init__.py"
    if init_file.exists():
        files.append({
            "path": "/home/user/scheduler/src/scheduler/__init__.py",
            "data": init_file.read_text(),
        })

    # Minimal pyproject.toml for sandbox deps only
    files.append({
        "path": "/home/user/scheduler/pyproject.toml",
        "data": _sandbox_pyproject(),
    })

    return files


def _sandbox_pyproject() -> str:
    """Generate a minimal pyproject.toml for the sandbox."""
    return """\
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "scheduler"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "claude-agent-sdk>=0.1.0",
    "httpx>=0.27.0",
]

[tool.setuptools.packages.find]
where = ["src"]
"""


def _start_control_plane() -> threading.Thread:
    """Start the FastAPI control plane server in a background thread."""
    thread = threading.Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={
            "host": config.control_plane_host,
            "port": config.control_plane_port,
            "log_level": "warning",
        },
        daemon=True,
    )
    thread.start()
    time.sleep(1)  # Give uvicorn a moment to bind
    return thread


def run_onboarding_in_sandbox(control_plane_url: str | None = None):
    """Spin up an e2b sandbox and run the onboarding agent inside it.

    Args:
        control_plane_url: Public URL of the control plane. If None,
            starts a local server (you'll need ngrok or similar for
            the sandbox to reach it).
    """
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        print("Error: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    # Start local control plane if no URL provided
    start_local = control_plane_url is None
    if start_local:
        print("Starting control plane server...")
        _start_control_plane()
        control_plane_url = f"http://localhost:{config.control_plane_port}"
        print(f"Control plane running at {control_plane_url}")
        print(
            "Note: For the e2b sandbox to reach this, you need the control plane "
            "on a public URL (e.g., deploy it or use ngrok)."
        )

    # Generate session token and register it
    session_token = secrets.token_urlsafe(32)
    print("Registering session on control plane...")
    register_session(session_token, user_id="default")
    print("Session registered.")

    # Create the sandbox
    print("Creating e2b sandbox...")
    sandbox = Sandbox.create(
        "claude",
        envs={
            "ANTHROPIC_API_KEY": anthropic_key,
            "CONTROL_PLANE_URL": control_plane_url,
            "SESSION_TOKEN": session_token,
            "ONBOARDING_LOOKBACK_DAYS": str(config.onboarding_lookback_days),
        },
    )

    try:
        # Install Python
        print("Installing Python in sandbox...")
        result = sandbox.commands.run(
            "apt-get update -qq && apt-get install -y -qq python3 python3-pip python3-venv "
            "> /dev/null 2>&1",
        )
        if result.exit_code != 0:
            print(f"Failed to install Python: {result.stderr}")
            return

        # Upload only sandbox files (no auth, no Google client libs)
        print("Uploading sandbox agent files...")
        files = _collect_sandbox_files()
        sandbox.files.write_files(files)

        # Install sandbox dependencies
        print("Installing sandbox dependencies...")
        result = sandbox.commands.run(
            "cd /home/user/scheduler && pip install -e '.' -q",
        )
        if result.exit_code != 0:
            print(f"Failed to install deps: {result.stderr}")
            return

        # Run the sandbox onboarding agent
        print("Running onboarding agent...\n")
        result = sandbox.commands.run(
            "cd /home/user/scheduler && python3 -m scheduler.sandbox.onboarding",
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

    finally:
        sandbox.kill()
        print("\nSandbox terminated.")


if __name__ == "__main__":
    # If a control plane URL is passed as an argument, use it.
    # Otherwise, start a local server.
    url = sys.argv[1] if len(sys.argv) > 1 else None
    run_onboarding_in_sandbox(control_plane_url=url)
