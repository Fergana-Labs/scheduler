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

import logging
import os
import json
import secrets
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import uvicorn
from e2b_code_interpreter import Sandbox

from scheduler.config import config

logger = logging.getLogger(__name__)

_SANDBOX_LIFETIME = 600  # 10 minutes — sandbox auto-terminates after this
_SANDBOX_CMD_TIMEOUT = 600  # 10 minutes — matches sandbox lifetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _collect_common_sandbox_files() -> list[dict]:
    files = []

    init_file = PROJECT_ROOT / "src" / "scheduler" / "__init__.py"
    if init_file.exists():
        files.append({
            "path": "/home/user/scheduler/src/scheduler/__init__.py",
            "data": init_file.read_text(),
        })

    claude_runtime = PROJECT_ROOT / "src" / "scheduler" / "claude_runtime.py"
    if claude_runtime.exists():
        files.append({
            "path": "/home/user/scheduler/src/scheduler/claude_runtime.py",
            "data": claude_runtime.read_text(),
        })

    sandbox_dir = PROJECT_ROOT / "src" / "scheduler" / "sandbox"
    for py_file in sandbox_dir.rglob("*.py"):
        rel_path = py_file.relative_to(PROJECT_ROOT / "src")
        files.append({
            "path": f"/home/user/scheduler/src/{rel_path}",
            "data": py_file.read_text(),
        })

    files.append({
        "path": "/home/user/scheduler/pyproject.toml",
        "data": _sandbox_pyproject(),
    })
    return files


def _collect_onboarding_sandbox_files() -> list[dict]:
    """Collect only the files needed for sandboxed onboarding."""
    files = _collect_common_sandbox_files()

    onboarding_dir = PROJECT_ROOT / "src" / "scheduler" / "onboarding"
    files.append({
        "path": "/home/user/scheduler/src/scheduler/onboarding/__init__.py",
        "data": "",
    })
    files.append({
        "path": "/home/user/scheduler/src/scheduler/onboarding/agent.py",
        "data": (onboarding_dir / "agent.py").read_text(),
    })

    # Guide agents (preferences + style + backends)
    guides_dir = PROJECT_ROOT / "src" / "scheduler" / "guides"
    for py_file in guides_dir.glob("*.py"):
        rel_path = py_file.relative_to(PROJECT_ROOT / "src")
        files.append({
            "path": f"/home/user/scheduler/src/{rel_path}",
            "data": py_file.read_text(),
        })

    config_file = PROJECT_ROOT / "src" / "scheduler" / "config.py"
    files.append({
        "path": "/home/user/scheduler/src/scheduler/config.py",
        "data": config_file.read_text(),
    })

    return files


def _collect_drafting_sandbox_files(email_payload: dict, classification_payload: dict) -> list[dict]:
    """Collect only the files needed for sandboxed drafting."""
    files = _collect_common_sandbox_files()
    drafts_dir = PROJECT_ROOT / "src" / "scheduler" / "drafts"

    files.append({
        "path": "/home/user/scheduler/src/scheduler/drafts/__init__.py",
        "data": (drafts_dir / "__init__.py").read_text(),
    })
    files.append({
        "path": "/home/user/scheduler/src/scheduler/drafts/composer.py",
        "data": (drafts_dir / "composer.py").read_text(),
    })
    files.append({
        "path": "/home/user/scheduler/draft_email.json",
        "data": json.dumps(email_payload),
    })
    files.append({
        "path": "/home/user/scheduler/draft_classification.json",
        "data": json.dumps(classification_payload),
    })

    return files


def _collect_drafting_runtime_files(email_payload: dict, classification_payload: dict) -> list[dict]:
    """Collect only per-run payload files for a prebuilt drafting template."""
    return [
        {
            "path": "/home/user/scheduler/draft_email.json",
            "data": json.dumps(email_payload),
        },
        {
            "path": "/home/user/scheduler/draft_classification.json",
            "data": json.dumps(classification_payload),
        },
    ]


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
    "anyio>=4.0.0",
    "claude-agent-sdk>=0.1.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.0",
]

[tool.setuptools.packages.find]
where = ["src"]
"""


def _start_control_plane() -> threading.Thread:
    """Start the FastAPI control plane server in a background thread."""
    from scheduler.controlplane.server import app

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


def _register_sandbox_session(user_id: str) -> str:
    from scheduler.controlplane.server import register_session

    session_token = secrets.token_urlsafe(32)
    print("Registering session on control plane...")
    register_session(session_token, user_id=user_id)
    print("Session registered.")
    return session_token


def _create_sandbox(*, control_plane_url: str, session_token: str, extra_envs: dict[str, str] | None = None):
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        print("Error: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    print("Creating e2b sandbox...")
    envs = {
        "ANTHROPIC_API_KEY": anthropic_key,
        "CONTROL_PLANE_URL": control_plane_url,
        "SESSION_TOKEN": session_token,
    }
    if extra_envs:
        envs.update(extra_envs)
    template = config.e2b_template_id.strip() or "claude"
    return Sandbox.create(
        template,
        envs=envs,
        timeout=_SANDBOX_LIFETIME,
    )


def _prepare_sandbox(sandbox: Sandbox, files: list[dict]) -> bool:
    if config.e2b_template_id.strip():
        print(f"Using prebuilt E2B template {config.e2b_template_id}; skipping runtime provisioning.")
        if files:
            print("Uploading runtime payload...")
            sandbox.files.write_files(files)
        return True

    print("Installing Python in sandbox...")
    result = sandbox.commands.run(
        "apt-get update -qq && apt-get install -y -qq python3 python3-pip python3-venv "
        "> /dev/null 2>&1",
    )
    if result.exit_code != 0:
        print(f"Failed to install Python: {result.stderr}")
        return False

    print("Uploading sandbox agent files...")
    sandbox.files.write_files(files)

    print("Installing sandbox dependencies...")
    result = sandbox.commands.run("cd /home/user/scheduler && pip install -e '.' -q")
    if result.exit_code != 0:
        print(f"Failed to install deps: {result.stderr}")
        return False
    return True


def _launch_single_onboarding_agent(
    agent_name: str,
    session_token: str,
    control_plane_url: str,
    lookback_days: int,
) -> None:
    """Spin up one e2b sandbox for a single onboarding agent."""
    sandbox = _create_sandbox(
        control_plane_url=control_plane_url,
        session_token=session_token,
        extra_envs={
            "ONBOARDING_LOOKBACK_DAYS": str(lookback_days),
            "ONBOARDING_AGENT": agent_name,
        },
    )

    try:
        files = _collect_onboarding_sandbox_files()
        if not _prepare_sandbox(sandbox, files):
            raise RuntimeError(f"Failed to prepare sandbox for {agent_name}")

        print(f"Running onboarding agent: {agent_name}...\n")
        try:
            result = sandbox.commands.run(
                "cd /home/user/scheduler && python3 -m scheduler.sandbox.onboarding",
                timeout=_SANDBOX_CMD_TIMEOUT,
                on_stdout=lambda msg: logger.info("e2b[%s]: %s", agent_name, msg),
                on_stderr=lambda msg: logger.warning("e2b[%s]: %s", agent_name, msg),
            )
            if result.exit_code != 0:
                raise RuntimeError(
                    f"e2b {agent_name} sandbox exited with code {result.exit_code}: {result.stderr[:500] if result.stderr else 'no stderr'}"
                )
        except TimeoutError:
            logger.error("e2b %s sandbox timed out after %ds", agent_name, _SANDBOX_CMD_TIMEOUT)
            raise RuntimeError(f"{agent_name} sandbox timed out after {_SANDBOX_CMD_TIMEOUT}s")
        except RuntimeError:
            raise
        except Exception as e:
            logger.error("e2b %s sandbox failed: %s", agent_name, e)
            raise RuntimeError(f"{agent_name} sandbox failed: {e}") from e
    finally:
        try:
            sandbox.kill()
        except Exception:
            pass
        print(f"\nSandbox for {agent_name} terminated.")


def launch_onboarding_in_sandbox(
    user_id: str,
    control_plane_url: str,
    lookback_days: int | None = None,
    on_agent_done: Callable[[str, bool], None] | None = None,
):
    """Spin up three e2b sandboxes (one per agent) and run them in parallel.

    *on_agent_done(agent_name, success)* is called as each agent finishes.
    """
    import concurrent.futures

    session_token = _register_sandbox_session(user_id)
    effective_lookback = lookback_days or config.onboarding_lookback_days
    agents = ["backfill", "preferences", "style"]
    errors: list[str] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(
                _launch_single_onboarding_agent,
                agent_name,
                session_token,
                control_plane_url,
                effective_lookback,
            ): agent_name
            for agent_name in agents
        }
        for future in concurrent.futures.as_completed(futures):
            agent_name = futures[future]
            try:
                future.result()
                logger.info("Onboarding agent %s completed successfully", agent_name)
                if on_agent_done:
                    on_agent_done(agent_name, True)
            except Exception as e:
                logger.error("Onboarding agent %s failed: %s", agent_name, e)
                errors.append(f"{agent_name}: {e}")
                if on_agent_done:
                    on_agent_done(agent_name, False)

    if errors:
        raise RuntimeError(f"Onboarding failed for: {'; '.join(errors)}")


def launch_draft_composer_in_sandbox(
    user_id: str,
    control_plane_url: str,
    email_payload: dict,
    classification_payload: dict,
    *,
    autopilot: bool,
    user_email: str = "",
) -> dict | None:
    """Spin up an e2b sandbox and run the draft composer agent inside it."""
    session_token = _register_sandbox_session(user_id)
    sandbox = _create_sandbox(
        control_plane_url=control_plane_url,
        session_token=session_token,
        extra_envs={
            "AUTOPILOT_ENABLED": "1" if autopilot else "0",
            "USER_EMAIL": user_email,
        },
    )

    try:
        files = (
            _collect_drafting_runtime_files(email_payload, classification_payload)
            if config.e2b_template_id.strip()
            else _collect_drafting_sandbox_files(email_payload, classification_payload)
        )
        if not _prepare_sandbox(
            sandbox,
            files,
        ):
            return None

        print("Running draft composer agent...\n")
        result = sandbox.commands.run(
            "cd /home/user/scheduler && python3 -m scheduler.sandbox.drafting",
            timeout=_SANDBOX_CMD_TIMEOUT,
            on_stdout=lambda msg: logger.info("e2b[drafting]: %s", msg),
            on_stderr=lambda msg: logger.warning("e2b[drafting]: %s", msg),
        )
        if result.exit_code != 0:
            logger.error("e2b drafting sandbox exited with code %d", result.exit_code)
            raise RuntimeError(f"e2b drafting sandbox failed (exit code {result.exit_code})")

        # Parse structured output: "COMPOSE_RESULT:<json>"
        for line in reversed(result.stdout.strip().splitlines()):
            if line.startswith("COMPOSE_RESULT:"):
                raw = line.removeprefix("COMPOSE_RESULT:")
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    return None
        return None
    finally:
        try:
            sandbox.kill()
        except Exception:
            pass  # sandbox may have already expired
        print("\nSandbox terminated.")


def run_onboarding_in_sandbox(control_plane_url: str | None = None):
    """Dev entry point for running onboarding in e2b."""
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

    launch_onboarding_in_sandbox(
        user_id="default",
        control_plane_url=control_plane_url,
        lookback_days=config.onboarding_lookback_days,
    )


if __name__ == "__main__":
    # If a control plane URL is passed as an argument, use it.
    # Otherwise, start a local server.
    url = sys.argv[1] if len(sys.argv) > 1 else None
    run_onboarding_in_sandbox(control_plane_url=url)
