"""Singleton Gmail client for the bot account.

The bot uses a Google service account with domain-wide delegation to
impersonate scheduling@tryscheduled.com.  A single GmailClient instance
is reused across requests to avoid rebuilding the discovery document on
every call.
"""

import json
import logging
import threading

from google.auth.transport.requests import Request
from google.oauth2 import service_account

from scheduler.config import config
from scheduler.gmail.client import GmailClient

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_client: GmailClient | None = None

BOT_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
]


def _build_bot_credentials() -> service_account.Credentials:
    """Build service-account credentials that impersonate the bot email."""
    if not config.bot_service_account_json:
        raise ValueError(
            "BOT_SERVICE_ACCOUNT_JSON is not set. "
            "Provide the service-account key JSON as a string."
        )
    info = json.loads(config.bot_service_account_json)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=BOT_SCOPES, subject=config.bot_email
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
    return bool(config.bot_email and config.bot_service_account_json)
