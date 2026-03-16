"""Google OAuth2 authentication flow.

Handles the OAuth2 flow for Gmail and Google Calendar access.
Stores credentials in token.json for reuse.

Scopes needed:
- gmail.readonly: Read emails to detect scheduling intent
- gmail.compose: Create draft replies
- calendar: Read/write to the stash calendar and user's primary calendar
"""

import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from scheduler.config import config

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar",
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
    creds = flow.run_local_server(port=8080)
    return creds


def _save_credentials(creds: Credentials) -> None:
    """Save credentials to token.json for reuse."""
    with open(config.token_path, "w") as f:
        f.write(creds.to_json())


if __name__ == "__main__":
    creds = get_credentials()
    print("Authentication successful!")
