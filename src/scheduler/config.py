"""Configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    google_client_id: str = field(default_factory=lambda: os.environ.get("GOOGLE_CLIENT_ID", ""))
    google_client_secret: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_CLIENT_SECRET", "")
    )
    google_redirect_uri: str = field(
        default_factory=lambda: os.environ.get(
            "GOOGLE_REDIRECT_URI", "http://localhost:8080/integrations/google/callback"
        )
    )
    stash_calendar_name: str = field(
        default_factory=lambda: os.environ.get("STASH_CALENDAR_NAME", "Stash Calendar")
    )
    anthropic_api_key: str = field(
        default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", "")
    )
    onboarding_lookback_days: int = field(
        default_factory=lambda: int(os.environ.get("ONBOARDING_LOOKBACK_DAYS", "60"))
    )
    watcher_poll_interval: int = field(
        default_factory=lambda: int(os.environ.get("WATCHER_POLL_INTERVAL", "60"))
    )
    database_url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", ""))
    token_path: str = field(default_factory=lambda: os.environ.get("TOKEN_PATH", "token.json"))
    control_plane_host: str = field(
        default_factory=lambda: os.environ.get("CONTROL_PLANE_HOST", "0.0.0.0")
    )
    control_plane_port: int = field(
        default_factory=lambda: int(os.environ.get("CONTROL_PLANE_PORT", "8000"))
    )
    guides_dir: str = field(
        default_factory=lambda: os.environ.get(
            "SCHEDULER_GUIDES_DIR",
            os.path.join(
                os.path.dirname(os.environ.get("TOKEN_PATH", "token.json")) or ".",
                "guides",
            ),
        )
    )


config = Config()
