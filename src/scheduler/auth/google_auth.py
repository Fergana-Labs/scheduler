"""Google OAuth2 authentication flow.

Handles the OAuth2 flow for Gmail and Google Calendar access.
Stores credentials in token.json for reuse.

Scopes needed:
- gmail.readonly: Read emails to detect scheduling intent
- gmail.compose: Create draft replies
- calendar: Read/write to the stash calendar and user's primary calendar
"""

from google.oauth2.credentials import Credentials

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
    # TODO: Implement
    # 1. Check if token.json exists and load credentials
    # 2. If credentials are expired but have a refresh token, refresh them
    # 3. If no valid credentials, run the OAuth flow:
    #    - Create OAuth flow from client config
    #    - Launch local server to handle redirect
    #    - Save resulting credentials to token.json
    raise NotImplementedError


def run_oauth_flow() -> Credentials:
    """Run the interactive OAuth2 flow via browser.

    Opens the user's browser to Google's consent screen, starts a local
    server to receive the callback, and returns the resulting credentials.
    """
    # TODO: Implement using google_auth_oauthlib.flow.InstalledAppFlow
    raise NotImplementedError


if __name__ == "__main__":
    creds = get_credentials()
    print("Authentication successful!")
