"""Google Calendar API client for the scheduled calendar."""

from dataclasses import dataclass
from datetime import datetime, timezone

from googleapiclient.discovery import build


@dataclass
class Event:
    """Represents a calendar event."""

    id: str | None
    summary: str
    start: datetime
    end: datetime
    description: str = ""
    source: str = ""  # Where this commitment was found (gmail, text, slack, etc.)


def _parse_event_datetime(event_data: dict, field: str) -> datetime:
    """Parse a datetime from a Google Calendar event's start/end field.

    Google Calendar events can have either 'dateTime' (timed events)
    or 'date' (all-day events).
    """
    dt_str = event_data[field].get("dateTime")
    if dt_str:
        return datetime.fromisoformat(dt_str)
    # All-day event — just a date string like "2026-03-17"
    # Must attach UTC tzinfo so sorting can compare with timed (aware) events
    return datetime.fromisoformat(event_data[field]["date"]).replace(tzinfo=timezone.utc)


def _event_from_api(event_data: dict) -> Event:
    """Convert a Google Calendar API event dict to our Event dataclass."""
    return Event(
        id=event_data.get("id"),
        summary=event_data.get("summary", "(no title)"),
        start=_parse_event_datetime(event_data, "start"),
        end=_parse_event_datetime(event_data, "end"),
        description=event_data.get("description", ""),
    )


class CalendarClient:
    """Wrapper around the Google Calendar API.

    Manages the "scheduled calendar" — a real Google Calendar that serves as the
    single source of truth for all commitments, whether or not they have
    formal calendar invites.
    """

    def __init__(self, credentials, scheduled_calendar_name: str = "Scheduled Calendar", extra_calendar_ids: list[str] | None = None):
        self._credentials = credentials
        self._scheduled_calendar_name = scheduled_calendar_name
        self._extra_calendar_ids = extra_calendar_ids or []
        self._service = None
        self._scheduled_calendar_id = None
        self._user_timezone = None

    def _get_service(self):
        """Build and cache the Calendar API service."""
        if self._service is None:
            self._service = build("calendar", "v3", credentials=self._credentials)
        return self._service

    def get_user_timezone(self) -> str:
        """IANA timezone string from the user's primary calendar. Falls back to UTC."""
        if self._user_timezone:
            return self._user_timezone

        try:
            service = self._get_service()
            cal = service.calendars().get(calendarId="primary").execute()
            self._user_timezone = cal.get("timeZone", "UTC")
        except Exception:
            self._user_timezone = "UTC"

        return self._user_timezone

    def _event_dt_body(self, dt: datetime) -> dict:
        """Build a start/end dict for the Google Calendar API."""
        if dt.tzinfo:
            return {"dateTime": dt.isoformat()}
        return {"dateTime": dt.isoformat(), "timeZone": self.get_user_timezone()}

    def get_or_create_scheduled_calendar(self) -> str:
        """Get the scheduled calendar ID, creating it if it doesn't exist.

        Returns:
            The calendar ID of the scheduled calendar.
        """
        if self._scheduled_calendar_id:
            return self._scheduled_calendar_id

        service = self._get_service()
        calendar_list = service.calendarList().list().execute()

        for cal in calendar_list.get("items", []):
            if cal.get("summary") == self._scheduled_calendar_name:
                self._scheduled_calendar_id = cal["id"]
                return self._scheduled_calendar_id

        # Not found — create it
        new_cal = service.calendars().insert(body={
            "summary": self._scheduled_calendar_name,
            "description": "Scheduled Calendar",
        }).execute()
        self._scheduled_calendar_id = new_cal["id"]
        return self._scheduled_calendar_id

    def list_calendars(self) -> list[dict]:
        """Return all calendars visible to the user.

        Each entry has 'id', 'summary', and 'primary' (bool).
        """
        service = self._get_service()
        calendars = []
        page_token = None

        while True:
            result = service.calendarList().list(
                pageToken=page_token,
                showHidden=True,
            ).execute()
            for item in result.get("items", []):
                calendars.append({
                    "id": item["id"],
                    "summary": item.get("summary", "(no title)"),
                    "primary": item.get("primary", False),
                })
            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return calendars

    def _list_events(
        self, calendar_id: str, time_min: datetime, time_max: datetime
    ) -> list[Event]:
        """List events from a single calendar in a time range."""
        service = self._get_service()
        events = []
        page_token = None

        while True:
            result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min.isoformat() + "Z" if not time_min.tzinfo else time_min.isoformat(),
                timeMax=time_max.isoformat() + "Z" if not time_max.tzinfo else time_max.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token,
            ).execute()

            for item in result.get("items", []):
                events.append(_event_from_api(item))

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return events

    def get_all_events(
        self, time_min: datetime, time_max: datetime, include_primary: bool = True
    ) -> list[Event]:
        """Get all events across primary calendar and scheduled calendar.

        This is the main availability check — it combines the user's real
        calendar with the scheduled calendar to get a complete picture.

        Args:
            time_min: Start of the time range.
            time_max: End of the time range.
            include_primary: Whether to also check the user's primary calendar.

        Returns:
            All events in the time range, from both calendars, sorted by start time.
        """
        scheduled_id = self.get_or_create_scheduled_calendar()
        events = self._list_events(scheduled_id, time_min, time_max)

        if include_primary:
            primary_events = self._list_events("primary", time_min, time_max)
            events.extend(primary_events)

        for cal_id in self._extra_calendar_ids:
            if cal_id == "primary" or cal_id == scheduled_id:
                continue
            events.extend(self._list_events(cal_id, time_min, time_max))

        events.sort(key=lambda e: e.start)
        return events

    def add_event(self, event: Event) -> str:
        """Add an event to the scheduled calendar.

        Args:
            event: The event to add.

        Returns:
            The ID of the created event.
        """
        service = self._get_service()
        scheduled_id = self.get_or_create_scheduled_calendar()

        body = {
            "summary": event.summary,
            "start": self._event_dt_body(event.start),
            "end": self._event_dt_body(event.end),
            "description": event.description,
        }
        if event.source:
            body["description"] = f"[source: {event.source}]\n{event.description}"

        result = service.events().insert(calendarId=scheduled_id, body=body).execute()
        return result["id"]

    def update_event(self, event_id: str, event: Event) -> None:
        """Update an existing event on the scheduled calendar."""
        service = self._get_service()
        scheduled_id = self.get_or_create_scheduled_calendar()

        body = {
            "summary": event.summary,
            "start": self._event_dt_body(event.start),
            "end": self._event_dt_body(event.end),
            "description": event.description,
        }
        service.events().update(
            calendarId=scheduled_id, eventId=event_id, body=body
        ).execute()

    def find_event(self, summary: str, time_min: datetime, time_max: datetime) -> Event | None:
        """Find an event by summary text within a time range.

        Useful for deduplication — checking if we already have this commitment.
        """
        scheduled_id = self.get_or_create_scheduled_calendar()
        events = self._list_events(scheduled_id, time_min, time_max)

        summary_lower = summary.lower()
        for event in events:
            if summary_lower in event.summary.lower():
                return event
        return None

    def create_invite_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        attendee_emails: list[str],
        description: str = "",
        location: str = "",
        add_google_meet: bool = False,
    ) -> str:
        """Create an event on the PRIMARY calendar with attendees.

        Google Calendar automatically sends invite emails to all attendees.
        If add_google_meet is True, a Google Meet link is attached to the event.
        """
        service = self._get_service()

        body = {
            "summary": summary,
            "start": self._event_dt_body(start),
            "end": self._event_dt_body(end),
            "description": description,
            "attendees": [{"email": email} for email in attendee_emails],
        }

        if location:
            body["location"] = location

        if add_google_meet:
            body["conferenceData"] = {
                "createRequest": {
                    "requestId": f"meet-{start.isoformat()}-{attendee_emails[0]}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                },
            }

        result = service.events().insert(
            calendarId="primary",
            body=body,
            sendUpdates="all",
            conferenceDataVersion=1 if add_google_meet else 0,
        ).execute()
        return result["id"]
