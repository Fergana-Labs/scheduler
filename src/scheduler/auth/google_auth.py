"""Google OAuth2 authentication flow.

Handles the OAuth2 flow for Gmail and Google Calendar access.
Stores credentials in token.json for reuse.

Scopes needed:
- gmail.readonly: Read emails to detect scheduling intent
- gmail.compose: Create draft replies
- calendar: Read/write to the scheduled calendar and user's primary calendar
"""

import json
import os

# Google may return extra scopes (e.g. "openid") beyond what we requested.
# oauthlib treats this scope mismatch as an error by default. Suppress it.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from scheduler.config import config

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/userinfo.email",
]


def get_credentials() -> Credentials:
    """Load stored credentials or run the OAuth flow if needed.

    Returns valid Google OAuth2 credentials. If no stored credentials exist
    or they've expired, launches the browser-based OAuth flow.
    """
    creds = None

    if os.path.exists(config.token_path):
        creds = Credentials.from_authorized_user_file(config.token_path, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_credentials(creds)
    elif not creds or not creds.valid:
        creds = run_oauth_flow()
        _save_credentials(creds)

    return creds


def run_oauth_flow() -> Credentials:
    """Run the interactive OAuth2 flow via browser.

    Opens the user's browser to Google's consent screen, starts a local
    server to receive the callback, and returns the resulting credentials.
    """
    client_config = {
        "installed": {
            "client_id": config.google_client_id,
            "client_secret": config.google_client_secret,
            "redirect_uris": [config.google_redirect_uri],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

    # prompt="consent" forces Google to return a refresh_token even if the user
    # previously authorized this app (otherwise Google omits it on re-auth).
    creds = flow.run_local_server(
        port=8080,
        redirect_uri_trailing_slash=False,
        prompt="consent",
    )
    return creds


def _save_credentials(creds: Credentials) -> None:
    """Save credentials to token.json for reuse."""
    with open(config.token_path, "w") as f:
        f.write(creds.to_json())


def load_credentials(user_id: str):
    """Load Google credentials from the database for the given user."""
    from scheduler.db import get_user_by_id, update_user_tokens

    user = get_user_by_id(user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")
    if not user.google_refresh_token:
        raise ValueError(f"User {user_id} has no Google refresh token")

    creds = Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.google_client_id,
        client_secret=config.google_client_secret,
    )
    if creds.expired:
        creds.refresh(Request())
        update_user_tokens(
            user_id=str(user.id),
            google_access_token=creds.token,
            access_token_expires_at=creds.expiry,
        )
    return creds


if __name__ == "__main__":
    creds = get_credentials()
    print("Authentication successful!")
