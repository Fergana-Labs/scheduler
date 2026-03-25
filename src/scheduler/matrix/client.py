"""Matrix client wrapper around matrix-nio.

Abstracts the Matrix homeserver connection (Beeper or self-hosted Synapse)
and provides a clean interface for the watcher and composer to use.
"""

import logging
from datetime import datetime, timezone
from typing import Callable, Awaitable

from nio import (
    AsyncClient,
    MatrixRoom,
    RoomCreateResponse,
    RoomMessageImage,
    RoomMessageText,
    SyncResponse,
)

from scheduler.matrix.models import ChatMessage

logger = logging.getLogger(__name__)

# Known bridge bot prefixes used by mautrix bridges to identify platforms
_BRIDGE_PLATFORM_HINTS = {
    "whatsapp": "whatsapp",
    "whatsappbot": "whatsapp",
    "instagram": "instagram",
    "instagrambot": "instagram",
    "meta": "instagram",
    "metabot": "instagram",
    "linkedin": "linkedin",
    "linkedinbot": "linkedin",
    "signal": "signal",
    "signalbot": "signal",
    "telegram": "telegram",
    "telegrambot": "telegram",
    "slackbot": "slack",
    "slack": "slack",
    "discordbot": "discord",
    "discord": "discord",
}


class MatrixClient:
    """Wrapper around nio.AsyncClient for receiving and sending bridged chat messages."""

    def __init__(self, homeserver_url: str, access_token: str, user_id: str):
        self._homeserver_url = homeserver_url
        self._access_token = access_token
        self._user_id = user_id
        self._client = AsyncClient(homeserver_url)
        self._client.access_token = access_token
        self._client.user_id = user_id

    async def connect(self) -> None:
        """Perform an initial sync to establish the sync token."""
        logger.info("matrix_client: connecting to %s as %s", self._homeserver_url, self._user_id)
        resp = await self._client.sync(timeout=10000, full_state=True)
        if isinstance(resp, SyncResponse):
            logger.info("matrix_client: initial sync complete, next_batch=%s", resp.next_batch)
        else:
            logger.error("matrix_client: initial sync failed: %s", resp)

    async def sync_forever(
        self,
        callback: Callable[[ChatMessage], Awaitable[None]],
        timeout: int = 30000,
    ) -> None:
        """Long-poll sync loop. Calls callback for each new text message.

        Args:
            callback: Async function to call for each new ChatMessage.
            timeout: Sync timeout in milliseconds (how long to long-poll).
        """

        async def _on_message(room: MatrixRoom, event: RoomMessageText) -> None:
            platform = self.get_room_platform(room)
            display_name = room.user_name(event.sender) or event.sender

            ts = datetime.fromtimestamp(event.server_timestamp / 1000, tz=timezone.utc)

            msg = ChatMessage(
                event_id=event.event_id,
                room_id=room.room_id,
                sender=event.sender,
                sender_display_name=display_name,
                body=event.body,
                timestamp=ts,
                platform=platform,
            )
            await callback(msg)

        self._client.add_event_callback(_on_message, RoomMessageText)

        logger.info("matrix_client: starting sync_forever loop")
        await self._client.sync_forever(timeout=timeout, full_state=False)

    async def get_room_messages(self, room_id: str, limit: int = 20) -> list[ChatMessage]:
        """Fetch recent messages from a room for conversation context.

        Args:
            room_id: The Matrix room ID.
            limit: Maximum number of messages to return.

        Returns:
            List of ChatMessage, oldest first.
        """
        room = self._client.rooms.get(room_id)

        resp = await self._client.room_messages(
            room_id,
            start="",
            limit=limit,
        )

        messages: list[ChatMessage] = []
        if hasattr(resp, "chunk"):
            for event in reversed(resp.chunk):  # reversed: oldest first
                if isinstance(event, RoomMessageText):
                    platform = self.get_room_platform(room) if room else "matrix"
                    display_name = (
                        room.user_name(event.sender) if room else None
                    ) or event.sender

                    ts = datetime.fromtimestamp(
                        event.server_timestamp / 1000, tz=timezone.utc
                    )

                    messages.append(
                        ChatMessage(
                            event_id=event.event_id,
                            room_id=room_id,
                            sender=event.sender,
                            sender_display_name=display_name,
                            body=event.body,
                            timestamp=ts,
                            platform=platform,
                        )
                    )

        return messages

    async def send_message(self, room_id: str, body: str) -> str | None:
        """Send a text message to a Matrix room.

        Args:
            room_id: The room to send to.
            body: The message text.

        Returns:
            The event_id of the sent message, or None on failure.
        """
        resp = await self._client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={"msgtype": "m.text", "body": body},
        )

        if hasattr(resp, "event_id"):
            logger.info("matrix_client: sent message to %s, event_id=%s", room_id, resp.event_id)
            return resp.event_id

        logger.error("matrix_client: failed to send message to %s: %s", room_id, resp)
        return None

    def get_room_platform(self, room: MatrixRoom | None) -> str:
        """Determine the source platform for a room based on bridge bot membership.

        Checks room members for known bridge bot user IDs (e.g. @whatsappbot:beeper.com).
        Falls back to "matrix" if no bridge is detected.

        Args:
            room: The MatrixRoom object (from nio's room state).

        Returns:
            Platform string like "whatsapp", "instagram", "signal", etc.
        """
        if room is None:
            return "matrix"

        for member in room.users:
            # Bridge bots typically have usernames like @whatsappbot:server
            localpart = member.split(":")[0].lstrip("@").lower()
            for hint, platform in _BRIDGE_PLATFORM_HINTS.items():
                if hint in localpart:
                    return platform

        return "matrix"

    async def get_or_create_dm(self, user_id: str) -> str | None:
        """Get an existing DM room with a user, or create one.

        Args:
            user_id: The Matrix user ID to DM (e.g. @whatsappbot:matrix.example.com).

        Returns:
            The room_id, or None on failure.
        """
        # Check existing rooms for a DM with this user
        for room_id, room in self._client.rooms.items():
            members = list(room.users.keys()) if hasattr(room.users, 'keys') else list(room.users)
            if len(members) == 2 and user_id in members:
                return room_id

        # Create a new DM
        resp = await self._client.room_create(
            is_direct=True,
            invite=[user_id],
        )
        if isinstance(resp, RoomCreateResponse):
            logger.info("matrix_client: created DM with %s, room_id=%s", user_id, resp.room_id)
            return resp.room_id

        logger.error("matrix_client: failed to create DM with %s: %s", user_id, resp)
        return None

    async def get_bot_responses(
        self, room_id: str, after_timestamp: float = 0, limit: int = 10
    ) -> list[dict]:
        """Read recent messages from a bridge bot DM, including images.

        Returns messages from the bot (not from self) as dicts with:
        - type: "text" or "image"
        - body: message text or image description
        - url: mxc:// URL for images (can be converted to HTTP)
        - timestamp: Unix timestamp in seconds

        Args:
            room_id: The DM room ID.
            after_timestamp: Only return messages after this Unix timestamp.
            limit: Max messages to fetch.
        """
        resp = await self._client.room_messages(room_id, start="", limit=limit)

        results: list[dict] = []
        if not hasattr(resp, "chunk"):
            return results

        for event in resp.chunk:
            ts = event.server_timestamp / 1000
            if ts <= after_timestamp:
                continue
            # Skip messages from self
            if event.sender == self._user_id:
                continue

            if isinstance(event, RoomMessageText):
                results.append({
                    "type": "text",
                    "body": event.body,
                    "timestamp": ts,
                })
            elif isinstance(event, RoomMessageImage):
                # Convert mxc:// URL to downloadable HTTP URL
                mxc_url = event.url
                http_url = None
                if mxc_url and mxc_url.startswith("mxc://"):
                    server_name, media_id = mxc_url[6:].split("/", 1)
                    http_url = (
                        f"{self._homeserver_url}/_matrix/media/v3/download/"
                        f"{server_name}/{media_id}"
                    )
                results.append({
                    "type": "image",
                    "body": event.body or "image",
                    "url": http_url,
                    "mxc_url": mxc_url,
                    "timestamp": ts,
                })

        # Return newest first
        results.sort(key=lambda m: m["timestamp"], reverse=True)
        return results

    async def disconnect(self) -> None:
        """Clean up the client connection."""
        await self._client.close()
        logger.info("matrix_client: disconnected")
