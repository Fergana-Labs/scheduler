"""Snapshot Gmail threads to JSON fixture files for eval."""

import json
from datetime import datetime

from scheduler.auth.google_auth import get_credentials
from scheduler.classifier.intent import classify_email
from scheduler.gmail.client import GmailClient


def snapshot_thread(thread_id: str) -> dict:
    """Fetch a Gmail thread and return it as a serializable dict."""
    creds = get_credentials()
    gmail = GmailClient(creds)
    messages = gmail.get_thread(thread_id)

    serialized = []
    for m in messages:
        serialized.append({
            "id": m.id,
            "thread_id": m.thread_id,
            "sender": m.sender,
            "recipient": m.recipient,
            "cc": m.cc,
            "subject": m.subject,
            "body": m.body,
            "date": m.date.isoformat(),
            "snippet": m.snippet,
        })

    # Classify the latest message
    latest = messages[-1]
    classification = classify_email(latest.subject, latest.body, latest.sender)

    return {
        "thread_id": thread_id,
        "messages": serialized,
        "classification": {
            "intent": classification.intent.value,
            "confidence": classification.confidence,
            "summary": classification.summary,
            "proposed_times": classification.proposed_times,
            "participants": classification.participants,
            "duration_minutes": classification.duration_minutes,
            "is_sales_email": classification.is_sales_email,
        },
        "metadata": {
            "snapshot_date": datetime.now().isoformat(),
            "notes": "",
        },
    }


def save_snapshot(thread_id: str, output_path: str) -> str:
    """Snapshot a thread and write it to a JSON file."""
    data = snapshot_thread(thread_id)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    return output_path
