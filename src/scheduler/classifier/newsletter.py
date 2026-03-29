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

_SCHEDULING_TOOL_SENDERS = re.compile(
    r"^(notifications?@calendly\.com"
    r"|notifications?@cal\.com"
    r"|no-?reply@zoom\.us"
    r"|no-?reply@meet\.google\.com"
    r")$",
    re.IGNORECASE,
)

_GCAL_INVITE_BODY_PATTERN = re.compile(
    r"Invitation from Google Calendar|"
    r"has invited you to the following event|"
    r"Going \(yes - maybe - no\)|"
    r"This event has been changed|"
    r"This event has been canceled|"
    r"You are receiving this email at the account .+ because you are subscribed",
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

    # Scheduling tool notification senders (Calendly, Cal.com, Zoom)
    if _SCHEDULING_TOOL_SENDERS.match(addr):
        return True

    return False


def is_automated_calendar_email(headers: dict[str, str], sender: str, body: str) -> bool:
    """Return True if this looks like an automated calendar invite/notification.

    Catches Google Calendar invites sent "on behalf of" the organizer, where
    the sender is a real person's address but the body is GCal boilerplate.
    """
    return bool(_GCAL_INVITE_BODY_PATTERN.search(body))
