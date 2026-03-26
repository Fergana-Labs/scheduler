"""Configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # Google OAuth
    google_client_id: str = field(default_factory=lambda: os.environ.get("GOOGLE_CLIENT_ID", ""))
    google_client_secret: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_CLIENT_SECRET", "")
    )
    google_redirect_uri: str = field(
        default_factory=lambda: os.environ.get(
            "GOOGLE_REDIRECT_URI", "http://localhost:8080/integrations/google/callback"
        )
    )
    google_web_redirect_uri: str = field(
        default_factory=lambda: os.environ.get(
            "GOOGLE_WEB_REDIRECT_URI",
            "http://localhost:8080",
        )
    )

    # GCP
    gcp_project_id: str = field(default_factory=lambda: os.environ.get("GCP_PROJECT_ID", ""))
    gcp_region: str = field(default_factory=lambda: os.environ.get("GCP_REGION", "us-central1"))

    # Scheduling
    scheduled_calendar_name: str = field(
        default_factory=lambda: os.environ.get("SCHEDULED_CALENDAR_NAME", "Scheduled Calendar")
    )
    onboarding_lookback_days: int = field(
        default_factory=lambda: int(os.environ.get("ONBOARDING_LOOKBACK_DAYS", "60"))
    )
    watcher_poll_interval: int = field(
        default_factory=lambda: int(os.environ.get("WATCHER_POLL_INTERVAL", "300"))
    )

    # Server
    control_plane_host: str = field(
        default_factory=lambda: os.environ.get("CONTROL_PLANE_HOST", "0.0.0.0")
    )
    control_plane_port: int = field(
        default_factory=lambda: int(os.environ.get("CONTROL_PLANE_PORT", "8080"))
    )
    control_plane_public_url: str = field(
        default_factory=lambda: os.environ.get("CONTROL_PLANE_PUBLIC_URL", "")
    )
    web_app_url: str = field(
        default_factory=lambda: os.environ.get("WEB_APP_URL", "http://localhost:8080")
    )
    session_secret: str = field(
        default_factory=lambda: os.environ.get("SESSION_SECRET", "change-me-in-production")
    )

    # Local dev
    token_path: str = field(default_factory=lambda: os.environ.get("TOKEN_PATH", "token.json"))
    guides_dir: str = field(
        default_factory=lambda: os.environ.get(
            "SCHEDULER_GUIDES_DIR",
            os.path.join(
                os.path.dirname(os.environ.get("TOKEN_PATH", "token.json")) or ".",
                "local_dev_guide_artifacts",
            ),
        )
    )

    # Hardcoded for self-hosted
    deployment_mode: str = "self_hosted"
    agent_runtime: str = "local"


config = Config()
