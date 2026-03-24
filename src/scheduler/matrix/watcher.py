"""Matrix message watcher — sync loop with buffering, pre-filtering, and dispatch.

Mirrors the Gmail webhook handler pattern in server.py:1238-1383 but for
bridged chat messages received via Matrix.
"""

import asyncio
import logging
import re
import time
from collections import defaultdict

from scheduler.config import config
from scheduler.matrix.client import MatrixClient
from scheduler.matrix.models import ChatMessage

logger = logging.getLogger(__name__)

# How long to wait after the last message in a room before processing the batch
_BUFFER_WINDOW_SECONDS = 30

# Pre-filter thresholds
_MIN_MESSAGE_LENGTH = 5

# Regex for messages that are only emoji (with optional whitespace)
_EMOJI_ONLY_RE = re.compile(
    r"^[\s"
    r"\U0001f600-\U0001f64f"  # emoticons
    r"\U0001f300-\U0001f5ff"  # symbols & pictographs
    r"\U0001f680-\U0001f6ff"  # transport & map
    r"\U0001f1e0-\U0001f1ff"  # flags
    r"\U00002702-\U000027b0"  # dingbats
    r"\U0000fe00-\U0000fe0f"  # variation selectors
    r"\U0001f900-\U0001f9ff"  # supplemental symbols
    r"\U0001fa00-\U0001fa6f"  # chess symbols
    r"\U0001fa70-\U0001faff"  # symbols extended-A
    r"\U00002600-\U000026ff"  # misc symbols
    r"\U0000200d"             # zero width joiner
    r"\U0000203c-\U00003299"  # misc
    r"]+$"
)


def _is_emoji_only(text: str) -> bool:
    """Return True if text contains only emoji and whitespace."""
    return bool(_EMOJI_ONLY_RE.match(text))


def _passes_prefilter(msg: ChatMessage, matrix_user_id: str) -> bool:
    """Pre-filter check — returns True if the message should be processed.

    Filters applied (no LLM call):
    - Skip messages from self
    - Skip media-only messages (empty body)
    - Skip emoji-only messages
    - Skip very short messages (< 5 chars)
    """
    # Skip messages from the Matrix user themselves
    if msg.sender == matrix_user_id:
        return False

    body = msg.body.strip()

    # Skip empty / media-only messages
    if not body:
        return False

    # Skip very short messages
    if len(body) < _MIN_MESSAGE_LENGTH:
        return False

    # Skip emoji-only messages
    if _is_emoji_only(body):
        return False

    return True


class MatrixWatcher:
    """Watches Matrix rooms for new messages and dispatches to classifier/composer.

    Features:
    - Message buffering: batches messages per room, processes 30s after last message
    - Pre-filtering: skips group chats (configurable), media-only, emoji, short messages
    - Dedup: uses try_claim_message() with Matrix event_id
    """

    def __init__(
        self,
        user_id: str,
        homeserver_url: str,
        access_token: str,
        matrix_user_id: str,
        *,
        skip_group_chats: bool = True,
    ):
        self._user_id = user_id
        self._matrix_user_id = matrix_user_id
        self._skip_group_chats = skip_group_chats
        self._client = MatrixClient(homeserver_url, access_token, matrix_user_id)

        # room_id -> list of buffered messages
        self._buffer: dict[str, list[ChatMessage]] = defaultdict(list)
        # room_id -> timestamp of last message received
        self._last_message_time: dict[str, float] = {}
        # Track running flush tasks so we can cancel on stop
        self._flush_tasks: dict[str, asyncio.Task] = {}
        self._running = False

    async def start(self) -> None:
        """Connect to Matrix and start the sync loop."""
        logger.info("matrix_watcher: starting for user=%s", self._user_id)
        await self._client.connect()
        self._running = True

        # Start sync loop — this runs forever until cancelled
        await self._client.sync_forever(self._on_message)

    async def stop(self) -> None:
        """Stop the watcher and disconnect."""
        self._running = False
        for task in self._flush_tasks.values():
            task.cancel()
        self._flush_tasks.clear()
        await self._client.disconnect()
        logger.info("matrix_watcher: stopped for user=%s", self._user_id)

    async def _on_message(self, msg: ChatMessage) -> None:
        """Callback for each new message from the sync loop."""
        # Pre-filter
        if not _passes_prefilter(msg, self._matrix_user_id):
            return

        # Skip group chats if configured (rooms with > 2 members, excluding bridge bots)
        if self._skip_group_chats:
            room = self._client._client.rooms.get(msg.room_id)
            if room and len(room.users) > 2:
                # Count non-bot members (bridge bots have specific patterns)
                human_members = [
                    u for u in room.users
                    if not u.split(":")[0].lstrip("@").lower().endswith("bot")
                ]
                if len(human_members) > 2:
                    logger.debug(
                        "matrix_watcher: skipping group chat message in %s", msg.room_id
                    )
                    return

        # Buffer the message
        self._buffer[msg.room_id].append(msg)
        self._last_message_time[msg.room_id] = time.monotonic()

        # Cancel any existing flush timer for this room and start a new one
        existing_task = self._flush_tasks.get(msg.room_id)
        if existing_task and not existing_task.done():
            existing_task.cancel()

        self._flush_tasks[msg.room_id] = asyncio.create_task(
            self._delayed_flush(msg.room_id)
        )

    async def _delayed_flush(self, room_id: str) -> None:
        """Wait for the buffer window, then flush the room's message batch."""
        await asyncio.sleep(_BUFFER_WINDOW_SECONDS)

        if not self._running:
            return

        messages = self._buffer.pop(room_id, [])
        self._last_message_time.pop(room_id, None)
        self._flush_tasks.pop(room_id, None)

        if not messages:
            return

        await self._process_batch(room_id, messages)

    async def _process_batch(self, room_id: str, messages: list[ChatMessage]) -> None:
        """Process a batch of buffered messages from a single room."""
        from scheduler.db import try_claim_message

        # Dedup: claim all event IDs atomically
        unclaimed: list[ChatMessage] = []
        for msg in messages:
            if try_claim_message(self._user_id, msg.event_id):
                unclaimed.append(msg)
            else:
                logger.info(
                    "matrix_watcher: event %s already claimed, skipping", msg.event_id
                )

        if not unclaimed:
            return

        platform = unclaimed[0].platform
        sender_name = unclaimed[0].sender_display_name

        # Concatenate the batch into a single text block for classification
        batch_text = "\n".join(m.body for m in unclaimed)

        logger.info(
            "matrix_watcher: processing %d message(s) from %s in room %s (platform=%s)",
            len(unclaimed),
            sender_name,
            room_id,
            platform,
        )

        # Classify the chat messages
        try:
            from scheduler.classifier.intent import classify_chat_message, SchedulingIntent

            # Fetch prior context from the room
            context_messages = await self._client.get_room_messages(room_id, limit=20)

            classification = classify_chat_message(
                messages=batch_text,
                sender=sender_name,
                platform=platform,
                context_messages=[
                    {"sender": m.sender_display_name, "body": m.body}
                    for m in context_messages
                ],
            )

            if classification.intent == SchedulingIntent.DOESNT_NEED_DRAFT:
                logger.info(
                    "matrix_watcher: messages in %s not scheduling-related, skipping",
                    room_id,
                )
                return

            logger.info(
                "matrix_watcher: messages in %s classified as %s (confidence=%.2f), composing draft",
                room_id,
                classification.intent.value,
                classification.confidence,
            )

            # Compose a chat draft reply
            from scheduler.drafts.chat_composer import ChatDraftComposer, ChatDraftBackend

            backend = ChatDraftBackend(
                matrix_client=self._client,
                user_id=self._user_id,
            )
            composer = ChatDraftComposer(backend, user_id=self._user_id)

            pending_reply_id = composer.compose_and_create_draft(
                room_id=room_id,
                sender_name=sender_name,
                platform=platform,
                classification=classification,
                batch_text=batch_text,
            )

            if pending_reply_id:
                logger.info(
                    "matrix_watcher: created pending reply %s for room %s",
                    pending_reply_id,
                    room_id,
                )
            else:
                logger.info(
                    "matrix_watcher: no draft needed for room %s",
                    room_id,
                )

        except Exception:
            logger.exception(
                "matrix_watcher: failed to process messages in room %s", room_id
            )
