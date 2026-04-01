"""Singleton Gmail client for the bot account.

The bot has its own Gmail credentials (scheduling@tryscheduled.com) separate
from any user's credentials.  A single GmailClient instance is reused across
requests to avoid rebuilding the discovery document on every call.
"""

import logging
import threading

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from scheduler.config import config
from scheduler.gmail.client import GmailClient

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_client: GmailClient | None = None


def _build_bot_credentials() -> Credentials:
    """Build Google OAuth credentials for the bot account."""
    if not config.bot_gmail_refresh_token:
        raise ValueError(
            "BOT_GMAIL_REFRESH_TOKEN is not set. "
            "The bot account needs its own Gmail OAuth refresh token."
        )
    creds = Credentials(
        token=None,
        refresh_token=config.bot_gmail_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.bot_gmail_client_id,
        client_secret=config.bot_gmail_client_secret,
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/calendar",
        ],
    )
    creds.refresh(Request())
    return creds


def get_bot_gmail_client() -> GmailClient:
    """Return the singleton bot Gmail client, creating it on first call."""
    global _client
    if _client is not None:
        return _client
    with _lock:
        if _client is not None:
            return _client
        creds = _build_bot_credentials()
        _client = GmailClient(creds)
        logger.info("bot_gmail: initialized client for %s", config.bot_email)
        return _client


def reset_bot_gmail_client() -> None:
    """Close and reset the singleton (e.g. after a credential refresh error)."""
    global _client
    with _lock:
        if _client is not None:
            _client.close()
            _client = None


def bot_email_address() -> str:
    """Return the configured bot email address."""
    return config.bot_email


def is_bot_mode_configured() -> bool:
    """Return True if bot mode has the minimum required config."""
    return bool(config.bot_email and config.bot_gmail_refresh_token)
