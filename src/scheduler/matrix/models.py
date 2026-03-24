"""Data models for Matrix chat integration."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ChatMessage:
    """A single message received from a Matrix room (bridged from WhatsApp, Instagram, etc.)."""

    event_id: str
    room_id: str
    sender: str
    sender_display_name: str
    body: str
    timestamp: datetime
    platform: str  # e.g. "whatsapp", "instagram", "linkedin", "signal", "matrix"


@dataclass
class PendingReply:
    """A draft reply awaiting user review/approval before being sent."""

    id: str
    user_id: str
    platform: str
    room_id: str
    sender_name: str
    conversation_context: list[dict[str, Any]] | None
    proposed_reply: str
    status: str  # "pending", "approved", "dismissed"
    created_at: datetime
    updated_at: datetime
