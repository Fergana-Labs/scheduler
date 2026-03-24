"""Header-based newsletter / mass email detection.

Checks email headers and sender patterns to identify newsletters, marketing
emails, and other bulk mail — no API call required.
"""

import re


_BULK_PRECEDENCE = {"bulk", "list", "junk"}

_MARKETING_HEADERS = {
    "x-sg-eid",
    "x-mailgun-tag",
    "x-campaignid",
    "feedback-id",
}

_AUTO_SUBMITTED_SKIP = {"auto-generated", "auto-replied"}

_NOREPLY_PATTERN = re.compile(
    r"^(noreply|no-reply|newsletter|marketing|notifications|updates|digest|bounce)@",
    re.IGNORECASE,
)

_GCAL_SENDER_PATTERN = re.compile(
    r"^calendar-(notification|server)@google\.com$",
    re.IGNORECASE,
)


def _extract_email(sender: str) -> str:
    """Extract the bare email address from a 'Name <addr>' string."""
    match = re.search(r"<([^>]+)>", sender)
    return match.group(1) if match else sender


def is_mass_email(headers: dict[str, str], sender: str) -> bool:
    """Return True if the email is a newsletter or mass/bulk email.

    Uses header-based heuristics only — no API call.
    """
    # List-Unsubscribe header
    if "list-unsubscribe" in headers:
        return True

    # Precedence: bulk / list / junk
    precedence = headers.get("precedence", "").lower().strip()
    if precedence in _BULK_PRECEDENCE:
        return True

    # Marketing platform headers
    if _MARKETING_HEADERS & headers.keys():
        return True

    # Auto-submitted
    auto_submitted = headers.get("auto-submitted", "").lower().strip()
    if auto_submitted in _AUTO_SUBMITTED_SKIP:
        return True

    # Sender patterns
    addr = _extract_email(sender).lower()
    if _NOREPLY_PATTERN.match(addr):
        return True

    # Google Calendar automated invites/notifications
    if _GCAL_SENDER_PATTERN.match(addr):
        return True

    return False
