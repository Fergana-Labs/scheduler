"""One-time migration: strip HTML from sent_body and recompute diff metrics."""

import difflib
import html
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import psycopg2


def _conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        from scheduler.db import _conn as default_conn
        return default_conn()
    return psycopg2.connect(url)


def strip_html(text: str) -> str:
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    return html.unescape(text)


def main():
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, original_body, sent_body FROM composed_drafts WHERE sent_at IS NOT NULL AND sent_body IS NOT NULL"
        )
        rows = cur.fetchall()
        print(f"Found {len(rows)} sent drafts to fix")

        updated = 0
        for row_id, original_body, sent_body in rows:
            # Check if sent_body contains HTML
            if '<' not in sent_body:
                continue

            plain_sent = strip_html(sent_body)

            # Recompute diff metrics
            original_norm = " ".join(original_body.split())
            sent_norm = " ".join(plain_sent.split())
            matcher = difflib.SequenceMatcher(None, original_norm, sent_norm)
            similarity = matcher.ratio()

            was_edited = similarity < 0.98
            edit_distance_ratio = 1.0 - similarity

            chars_added = 0
            chars_removed = 0
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == "replace":
                    chars_removed += i2 - i1
                    chars_added += j2 - j1
                elif tag == "delete":
                    chars_removed += i2 - i1
                elif tag == "insert":
                    chars_added += j2 - j1

            cur.execute(
                """
                UPDATE composed_drafts
                SET sent_body = %s, was_edited = %s, edit_distance_ratio = %s,
                    chars_added = %s, chars_removed = %s
                WHERE id = %s
                """,
                (plain_sent, was_edited, edit_distance_ratio, chars_added, chars_removed, row_id),
            )
            updated += 1

        conn.commit()
        print(f"Updated {updated} drafts")


if __name__ == "__main__":
    main()
