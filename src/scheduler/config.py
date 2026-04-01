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
    scheduled_calendar_name: str = field(
        default_factory=lambda: os.environ.get("SCHEDULED_CALENDAR_NAME", "Scheduled Calendar")
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
        default_factory=lambda: int(os.environ.get("CONTROL_PLANE_PORT", "8080"))
    )
    gmail_pubsub_topic: str = field(
        default_factory=lambda: os.environ.get("GMAIL_PUBSUB_TOPIC", "")
    )
    web_app_url: str = field(
        default_factory=lambda: os.environ.get("WEB_APP_URL", "http://localhost:3000")
    )
    google_web_redirect_uri: str = field(
        default_factory=lambda: os.environ.get(
            "GOOGLE_WEB_REDIRECT_URI",
            "http://localhost:8080",
        )
    )
    session_secret: str = field(
        default_factory=lambda: os.environ.get("SESSION_SECRET", "change-me-in-production")
    )
    deployment_mode: str = field(
        default_factory=lambda: os.environ.get(
            "SCHEDULER_DEPLOYMENT_MODE", "self_hosted"
        ).strip().lower().replace("-", "_")
    )
    gmail_webhook_token: str = field(
        default_factory=lambda: os.environ.get("GMAIL_WEBHOOK_TOKEN", "")
    )
    guides_dir: str = field(
        default_factory=lambda: os.environ.get(
            "SCHEDULER_GUIDES_DIR",
            os.path.join(
                os.path.dirname(os.environ.get("TOKEN_PATH", "token.json")) or ".",
                "local_dev_guide_artifacts",
            ),
        )
    )
    agent_runtime: str = field(
        default_factory=lambda: os.environ.get(
            "AGENT_RUNTIME",
            os.environ.get("ONBOARDING_RUNTIME", "local"),
        )
    )
    control_plane_public_url: str = field(
        default_factory=lambda: os.environ.get(
            "CONTROL_PLANE_PUBLIC_URL",
            os.environ.get("CONTROL_PLANE_URL", ""),
        )
    )
    e2b_template_id: str = field(
        default_factory=lambda: os.environ.get("E2B_TEMPLATE_ID", "")
    )
    auth0_domain: str = field(
        default_factory=lambda: os.environ.get("AUTH0_DOMAIN", "")
    )
    auth0_client_id: str = field(
        default_factory=lambda: os.environ.get("AUTH0_CLIENT_ID", "")
    )
    auth0_client_secret: str = field(
        default_factory=lambda: os.environ.get("AUTH0_CLIENT_SECRET", "")
    )
    auth0_audience: str = field(
        default_factory=lambda: os.environ.get("AUTH0_AUDIENCE", "")
    )
    postmark_server_token: str = field(
        default_factory=lambda: os.environ.get("POSTMARK_SERVER_TOKEN", "")
    )
    postmark_from_email: str = field(
        default_factory=lambda: os.environ.get(
            "POSTMARK_FROM_EMAIL", "sam@tryscheduled.com"
        )
    )
    postmark_bot_email: str = field(
        default_factory=lambda: os.environ.get(
            "POSTMARK_BOT_EMAIL", "bot@tryscheduled.com"
        )
    )
    admin_emails: list[str] = field(
        default_factory=lambda: [
            e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()
        ]
    )

    # Bot mode fields (third-party CC-based scheduling)
    bot_email: str = field(
        default_factory=lambda: os.environ.get("BOT_EMAIL", "")
    )
    bot_gmail_refresh_token: str = field(
        default_factory=lambda: os.environ.get("BOT_GMAIL_REFRESH_TOKEN", "")
    )
    bot_gmail_client_id: str = field(
        default_factory=lambda: os.environ.get(
            "BOT_GMAIL_CLIENT_ID",
            os.environ.get("GOOGLE_CLIENT_ID", ""),
        )
    )
    bot_gmail_client_secret: str = field(
        default_factory=lambda: os.environ.get(
            "BOT_GMAIL_CLIENT_SECRET",
            os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        )
    )
    bot_gmail_pubsub_topic: str = field(
        default_factory=lambda: os.environ.get(
            "BOT_GMAIL_PUBSUB_TOPIC",
            os.environ.get("GMAIL_PUBSUB_TOPIC", ""),
        )
    )
    bot_gmail_webhook_token: str = field(
        default_factory=lambda: os.environ.get("BOT_GMAIL_WEBHOOK_TOKEN", "")
    )

    # Self-hosted fields (only used when deployment_mode == "self_hosted")
    sqlite_db_path: str = field(
        default_factory=lambda: os.environ.get("SQLITE_DB_PATH", "/tmp/scheduler.db")
    )
    gcs_bucket: str = field(default_factory=lambda: os.environ.get("GCS_BUCKET", ""))


config = Config()
