"""Identify which registered user CC'd the bot on an email thread.

When an email arrives in the bot's inbox, we parse From/To/CC headers to find
the registered Scheduled user who triggered this interaction.
"""

import logging
import re

from scheduler.bot.gmail import bot_email_address
from scheduler.db import UserRow, get_user_by_email, get_user_by_google_email

logger = logging.getLogger(__name__)

# Match "Name <email>" or bare "email"
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[\w]+")


def _extract_addresses(header: str) -> list[str]:
    """Extract all email addresses from a header value."""
    if not header:
        return []
    return [addr.lower() for addr in _EMAIL_RE.findall(header)]


def _lookup_user(email: str) -> UserRow | None:
    """Try to find a user by email or google_email."""
    user = get_user_by_email(email)
    if user:
        return user
    return get_user_by_google_email(email)


def identify_user(
    sender: str,
    recipient: str,
    cc: str,
) -> tuple[UserRow | None, str | None]:
    """Identify the registered user and the counterparty from email headers.

    Returns (user, counterparty_email).  user is the Scheduled user who
    CC'd the bot; counterparty_email is the other person in the conversation
    (the one being scheduled with).

    Priority:
    1. From address — the person who sent the email and CC'd the bot is most
       likely the Scheduled user.
    2. To/CC addresses — if the sender isn't a user, check recipients (someone
       else CC'd the bot on a thread containing our user).
    """
    bot_addr = bot_email_address().lower()
    from_addrs = _extract_addresses(sender)
    to_addrs = _extract_addresses(recipient)
    cc_addrs = _extract_addresses(cc)

    all_addrs = set(from_addrs + to_addrs + cc_addrs) - {bot_addr}

    # Check From first — the person who sent the email is the most likely user
    for addr in from_addrs:
        if addr == bot_addr:
            continue
        user = _lookup_user(addr)
        if user and user.scheduling_mode == "bot":
            # Counterparty is whoever else is on the thread
            counterparty = _pick_counterparty(all_addrs, addr)
            logger.info("bot_identity: user=%s (from sender), counterparty=%s", user.email, counterparty)
            return user, counterparty

    # Check To/CC — maybe a non-user sent the email but our user is a recipient
    for addr in to_addrs + cc_addrs:
        if addr == bot_addr:
            continue
        user = _lookup_user(addr)
        if user and user.scheduling_mode == "bot":
            # Counterparty is the sender (since they're the non-user party)
            counterparty = from_addrs[0] if from_addrs and from_addrs[0] != bot_addr else None
            logger.info("bot_identity: user=%s (from recipient), counterparty=%s", user.email, counterparty)
            return user, counterparty

    logger.info("bot_identity: no registered bot-mode user found in headers")
    return None, None


def _pick_counterparty(all_addrs: set[str], user_email: str) -> str | None:
    """Pick the counterparty email from the remaining addresses."""
    candidates = all_addrs - {user_email.lower()}
    if len(candidates) == 1:
        return candidates.pop()
    if candidates:
        # Multiple candidates — return the first one (heuristic: it's usually
        # the To address).  The agent will figure out the full participant list
        # from reading the thread.
        return sorted(candidates)[0]
    return None
