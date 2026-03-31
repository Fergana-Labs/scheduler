"""Gmail push notification setup and renewal.

Registers Gmail to send push notifications via Google Cloud Pub/Sub
when new emails arrive. Must be renewed before expiration (~ 7 days).

Prerequisites:
  1. Create a Pub/Sub topic in Google Cloud Console
  2. Grant gmail-api-push@system.gserviceaccount.com "Pub/Sub Publisher" on the topic
  3. Create a push subscription pointing to your /webhooks/gmail endpoint
  4. Set GMAIL_PUBSUB_TOPIC in env (e.g. "projects/my-project/topics/gmail-push")
"""

import logging

from google.auth.exceptions import RefreshError

from scheduler.config import config
from scheduler.db import get_all_user_ids, get_user_by_id, update_gmail_history_id, update_onboarding_status
from scheduler.gmail.client import GmailClient

logger = logging.getLogger(__name__)


def setup_gmail_watch(user_id: str) -> dict:
    """Register Gmail push notifications for a user.

    Args:
        user_id: The user's ID in our database.

    Returns:
        Dict with 'historyId' and 'expiration' from Gmail.

    Raises:
        ValueError: If GMAIL_PUBSUB_TOPIC is not configured.
    """
    if not config.gmail_pubsub_topic:
        raise ValueError(
            "GMAIL_PUBSUB_TOPIC is not set. "
            "Set it to your Pub/Sub topic, e.g. 'projects/my-project/topics/gmail-push'"
        )

    from scheduler.auth.google_auth import load_credentials

    creds = load_credentials(user_id)
    gmail = GmailClient(creds)

    result = gmail.watch(config.gmail_pubsub_topic)

    # Store the initial history ID so we have a baseline for diffs
    update_gmail_history_id(user_id, result["historyId"])

    logger.info(
        "gmail_watch: registered for user=%s, historyId=%s, expires=%s",
        user_id,
        result["historyId"],
        result["expiration"],
    )

    return result


def renew_all_watches() -> dict:
    """Renew Gmail push notification watches for all users.

    Calling watch() again before expiration is safe — Gmail treats it as
    a renewal and returns a fresh expiration.

    Returns:
        Dict with 'renewed' count and 'failed' list of (user_id, error).
    """
    user_ids = get_all_user_ids()

    renewed = 0
    failed = []

    for user_id in user_ids:
        user = get_user_by_id(user_id)
        if not user or not user.google_refresh_token:
            logger.info("gmail_watch: skipping disconnected user=%s", user_id)
            continue
        if not user.system_enabled:
            logger.info("gmail_watch: skipping disabled user=%s", user_id)
            continue
        if not user.gmail_history_id:
            logger.info("gmail_watch: skipping user=%s with no gmail_history_id (incomplete onboarding)", user_id)
            continue
        if user.onboarding_status == "failed":
            logger.info("gmail_watch: skipping user=%s pending re-auth", user_id)
            continue

        try:
            setup_gmail_watch(user_id)
            renewed += 1
        except RefreshError as e:
            # Retry once — a single RefreshError can be transient (Google rate
            # limiting, brief outage).  Only mark the user for re-auth if the
            # retry also fails with RefreshError.
            logger.warning("gmail_watch: RefreshError for user=%s, retrying once: %s", user_id, e)
            try:
                setup_gmail_watch(user_id)
                renewed += 1
                logger.info("gmail_watch: retry succeeded for user=%s", user_id)
            except RefreshError as e2:
                logger.warning("gmail_watch: retry also failed for user=%s, marking for re-auth: %s", user_id, e2)
                update_onboarding_status(str(user_id), "failed")
                failed.append((user_id, str(e2)))
            except Exception as e2:
                logger.error("gmail_watch: retry failed with non-auth error for user=%s: %s", user_id, e2)
                failed.append((user_id, str(e2)))
        except Exception as e:
            logger.error("gmail_watch: failed to renew for user=%s: %s", user_id, e)
            failed.append((user_id, str(e)))

    logger.info("gmail_watch: renewed %d/%d watches", renewed, len(user_ids))
    return {"renewed": renewed, "failed": failed}
