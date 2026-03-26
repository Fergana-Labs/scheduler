"""Control plane API — exposes Gmail and Calendar operations over HTTP.

Self-hosted single-user version. Holds Google OAuth tokens and provides
authenticated endpoints for the web UI and sandbox agent.
"""

import asyncio
import base64
import html
import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
import urllib.parse
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from scheduler.auth.google_auth import SCOPES, load_credentials
from scheduler.calendar.client import CalendarClient, Event
from scheduler.config import config
from scheduler.gmail.client import GmailClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

_WATCH_RENEWAL_INTERVAL = 12 * 3600  # 12 hours
_onboarding_status: dict[str, dict] = {}  # user_id -> {"status": ..., "error": ...}
_onboarding_lock = threading.Lock()
_UNKNOWN_GMAIL_WEBHOOK_TTL = 300  # 5 minutes
_unknown_gmail_webhook_emails: dict[str, float] = {}


def _is_cached_unknown_gmail_webhook_email(email_address: str) -> bool:
    now = time.time()
    expires_at = _unknown_gmail_webhook_emails.get(email_address)
    if expires_at is None:
        return False
    if expires_at <= now:
        del _unknown_gmail_webhook_emails[email_address]
        return False
    return True


def _cache_unknown_gmail_webhook_email(email_address: str) -> None:
    _unknown_gmail_webhook_emails[email_address] = time.time() + _UNKNOWN_GMAIL_WEBHOOK_TTL


def _is_gmail_404(exc: Exception) -> bool:
    from googleapiclient.errors import HttpError
    return isinstance(exc, HttpError) and exc.resp.status == 404


async def _watch_renewal_loop():
    """Background loop: renew Gmail watches and clean up old processed messages."""
    await asyncio.sleep(60)  # let server finish starting
    while True:
        try:
            from scheduler.db import cleanup_processed_messages
            from scheduler.gmail.watch import renew_all_watches

            result = await asyncio.to_thread(renew_all_watches)
            logger.info("watch_renewal_loop: %s", result)
            deleted = await asyncio.to_thread(cleanup_processed_messages)
            if deleted:
                logger.info("watch_renewal_loop: cleaned up %d old processed_messages rows", deleted)
            from scheduler.db import cleanup_composed_drafts, cleanup_old_analytics
            draft_deleted = await asyncio.to_thread(cleanup_composed_drafts)
            if draft_deleted:
                logger.info("watch_renewal_loop: cleaned up %d old composed_drafts rows", draft_deleted)
            analytics_deleted = await asyncio.to_thread(cleanup_old_analytics)
            if analytics_deleted:
                logger.info("watch_renewal_loop: cleaned up %d old analytics_events rows", analytics_deleted)
        except Exception:
            logger.exception("watch_renewal_loop: failed")
        await asyncio.sleep(_WATCH_RENEWAL_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_watch_renewal_loop())
    yield
    task.cancel()


app = FastAPI(title="Scheduler Control Plane", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.web_app_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# --- HMAC session auth ---


def _sign_session(user_id: str, email: str) -> str:
    """Create an HMAC-signed session token encoding user_id and email."""
    payload = json.dumps({"user_id": user_id, "email": email})
    sig = hmac.new(config.session_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}|{sig}".encode()).decode()


def _verify_session(token: str) -> dict | None:
    """Verify and decode an HMAC-signed session token."""
    try:
        decoded = base64.urlsafe_b64decode(token).decode()
        payload, sig = decoded.rsplit("|", 1)
        expected = hmac.new(config.session_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        return json.loads(payload)
    except Exception:
        return None


def get_authenticated_user(request: Request) -> dict:
    """Validate HMAC session token from Authorization header."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header[7:]

    session = _verify_session(token)
    if session:
        return session

    raise HTTPException(status_code=401, detail="Invalid token")


get_web_session = get_authenticated_user
get_web_user = get_authenticated_user


# --- Google OAuth routes ---


# Temporary store for Google connect OAuth state tokens
_google_connect_states: dict[str, float] = {}


@app.get("/auth/google/connect")
def auth_google_connect(token: str | None = None):
    """Start Google API token OAuth flow. Requires authenticated session token via query param."""
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    legacy = _verify_session(token)
    if not legacy:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = legacy["user_id"]

    state_data = f"{secrets.token_urlsafe(32)}|user_id={user_id}|auth_token={token}"
    _google_connect_states[state_data] = time.time()

    params = {
        "client_id": config.google_client_id,
        "redirect_uri": f"{config.google_web_redirect_uri}/auth/google/callback",
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state_data,
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url)


@app.get("/auth/google/callback")
def auth_google_connect_callback(
    code: str | None = None, state: str | None = None, error: str | None = None
):
    """Handle Google OAuth callback for the Connect flow."""
    if error:
        return RedirectResponse(f"{config.web_app_url}?error={error}")

    if not code or not state:
        return RedirectResponse(f"{config.web_app_url}?error=missing_params")

    # Validate state
    issued_at = _google_connect_states.pop(state, None)
    if not issued_at or (time.time() - issued_at > 600):
        return RedirectResponse(f"{config.web_app_url}?error=invalid_state")

    # Extract user_id and auth_token from state
    parts = state.split("|")
    state_dict = {}
    for part in parts[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            state_dict[k] = v
    user_id = state_dict.get("user_id")
    auth_token = state_dict.get("auth_token")

    if not user_id:
        return RedirectResponse(f"{config.web_app_url}?error=invalid_state")

    import httpx

    token_response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": config.google_client_id,
            "client_secret": config.google_client_secret,
            "redirect_uri": f"{config.google_web_redirect_uri}/auth/google/callback",
            "grant_type": "authorization_code",
        },
    )

    if token_response.status_code != 200:
        logger.error("Google token exchange failed: %s", token_response.text)
        return RedirectResponse(f"{config.web_app_url}?error=token_exchange_failed")

    tokens = token_response.json()
    google_access_token = tokens["access_token"]
    google_refresh_token = tokens.get("refresh_token")

    if not google_refresh_token:
        return RedirectResponse(f"{config.web_app_url}?error=no_refresh_token")

    from scheduler.db import update_google_tokens

    expires_in = tokens.get("expires_in")
    expires_at = None
    if expires_in:
        from datetime import timedelta
        expires_at = datetime.now() + timedelta(seconds=expires_in)

    update_google_tokens(
        user_id=user_id,
        google_refresh_token=google_refresh_token,
        google_access_token=google_access_token,
        access_token_expires_at=expires_at,
    )

    from scheduler.db import get_user_by_id as _get_user
    db_user = _get_user(user_id)
    is_onboarded = _is_onboarded(user_id, scheduled_calendar_id=db_user.scheduled_calendar_id if db_user else None)

    from starlette.background import BackgroundTask

    token_param = f"token={auth_token}" if auth_token else ""

    if is_onboarded:
        logger.info("google_connect: returning user=%s, renewing gmail watch", user_id)
        background = BackgroundTask(_renew_gmail_watch, user_id)
        redirect_url = f"{config.web_app_url}/settings?{token_param}"
    else:
        logger.info("google_connect: starting onboarding for user=%s", user_id)
        with _onboarding_lock:
            if _onboarding_status.get(user_id, {}).get("status") == "running":
                logger.info("google_connect: onboarding already running for user=%s", user_id)
                background = None
            else:
                background = BackgroundTask(_run_onboarding, user_id)
        redirect_url = f"{config.web_app_url}/onboarding?{token_param}"

    return RedirectResponse(redirect_url, background=background)


# --- Legacy Google OAuth (direct sign-in) ---

_oauth_states: dict[str, float] = {}

_STATIC_DIR = Path(__file__).parent / "static"


@app.get("/settings", response_class=HTMLResponse)
def settings_page():
    """Serve the bundled settings UI."""
    return (_STATIC_DIR / "settings.html").read_text()


@app.get("/auth/google")
def auth_google_redirect(signin: str | None = None):
    """Redirect the user to Google's OAuth consent screen."""
    is_signin = signin == "1"
    state_data = f"{secrets.token_urlsafe(32)}|signin={1 if is_signin else 0}"
    _oauth_states[state_data] = time.time()

    params = {
        "client_id": config.google_client_id,
        "redirect_uri": config.google_web_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "select_account" if is_signin else "consent",
        "state": state_data,
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url)


@app.get("/auth/login")
def auth_login(signup: str | None = None):
    """Start interactive login — redirects to Google OAuth."""
    redirect = "/auth/google?signin=1" if signup == "1" else "/auth/google"
    return RedirectResponse(redirect)


@app.get("/")
def root_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    """Handle the OAuth callback at the root path (Google redirects to http://localhost:8080).

    If no OAuth query params are present, returns a simple health check.
    """
    if not code and not state and not error:
        return {"status": "ok", "service": "scheduler-control-plane"}
    return auth_google_callback(code=code, state=state, error=error)


def auth_google_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    """Handle the OAuth callback from Google.

    Exchanges the authorization code for tokens, upserts the user in the
    database, and redirects to the web app with a signed session cookie.
    """
    if error:
        return RedirectResponse(f"{config.web_app_url}?error={error}")

    if not code or not state:
        return RedirectResponse(f"{config.web_app_url}?error=missing_params")

    issued_at = _oauth_states.pop(state, None)
    if not issued_at or (time.time() - issued_at > 600):
        return RedirectResponse(f"{config.web_app_url}?error=invalid_state")

    is_signin = state.endswith("|signin=1")

    import httpx

    token_response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": config.google_client_id,
            "client_secret": config.google_client_secret,
            "redirect_uri": config.google_web_redirect_uri,
            "grant_type": "authorization_code",
        },
    )

    if token_response.status_code != 200:
        logger.error("OAuth token exchange failed: %s", token_response.text)
        return RedirectResponse(f"{config.web_app_url}?error=token_exchange_failed")

    tokens = token_response.json()
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")

    userinfo_response = httpx.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    if userinfo_response.status_code != 200:
        logger.error("Userinfo request failed: status=%s body=%s", userinfo_response.status_code, userinfo_response.text)
        return RedirectResponse(f"{config.web_app_url}?error=userinfo_failed")

    email = userinfo_response.json().get("email")
    if not email:
        return RedirectResponse(f"{config.web_app_url}?error=no_email")

    from scheduler.db import get_user_by_email, upsert_user

    if refresh_token:
        expires_in = tokens.get("expires_in")
        expires_at = None
        if expires_in:
            from datetime import timedelta
            expires_at = datetime.now() + timedelta(seconds=expires_in)

        user, is_new = upsert_user(
            email=email,
            google_refresh_token=refresh_token,
            google_access_token=access_token,
            access_token_expires_at=expires_at,
        )
    else:
        user = get_user_by_email(email)
        if not user:
            logger.warning("sign-in attempt for unknown user: %s", email)
            return RedirectResponse(f"{config.web_app_url}?error=account_not_found")

    is_onboarded = _is_onboarded(str(user.id), scheduled_calendar_id=user.scheduled_calendar_id)

    from starlette.background import BackgroundTask

    if is_onboarded:
        logger.info("sign-in: returning user=%s, renewing gmail watch", user.id)
        background = BackgroundTask(_renew_gmail_watch, str(user.id))
        redirect_url = f"{config.web_app_url}/settings"
    else:
        logger.info("onboarding: starting all agents for user=%s after OAuth", user.id)
        with _onboarding_lock:
            if _onboarding_status.get(str(user.id), {}).get("status") == "running":
                logger.info("onboarding: already running for user=%s", user.id)
                background = None
            else:
                background = BackgroundTask(_run_onboarding, str(user.id))
        redirect_url = f"{config.web_app_url}/onboarding"

    session_token = _sign_session(str(user.id), email)
    separator = "&" if "?" in redirect_url else "?"
    redirect_url_with_token = f"{redirect_url}{separator}session={session_token}"
    return RedirectResponse(redirect_url_with_token, background=background)


@app.get("/auth/me")
def auth_me(session: dict = Depends(get_authenticated_user)):
    return {"user_id": session["user_id"], "email": session["email"]}


# --- Serialization helpers ---


def _serialize_email(email) -> dict:
    return {
        "id": email.id,
        "thread_id": email.thread_id,
        "sender": email.sender,
        "recipient": email.recipient,
        "cc": email.cc,
        "subject": email.subject,
        "body": email.body,
        "date": email.date.isoformat(),
        "snippet": email.snippet,
    }


def _serialize_event(event) -> dict:
    return {
        "id": event.id,
        "summary": event.summary,
        "start": event.start.isoformat(),
        "end": event.end.isoformat(),
        "description": event.description,
    }


# --- Request models ---


class SearchEmailsRequest(BaseModel):
    query: str
    max_results: int = 50


class CreateDraftRequest(BaseModel):
    thread_id: str
    to: str
    cc: str = ""
    subject: str
    body: str
    thread_context: list[dict] | None = None


class SendEmailRequest(BaseModel):
    thread_id: str
    to: str
    cc: str = ""
    subject: str
    body: str


class GetEventsRequest(BaseModel):
    start_date: str
    end_date: str
    include_primary: bool = True


class FindEventRequest(BaseModel):
    summary: str
    start_date: str
    end_date: str


class AddEventRequest(BaseModel):
    summary: str
    start: str
    end: str
    description: str = ""


class UpdateBrandingRequest(BaseModel):
    enabled: bool


class UpdateAutopilotRequest(BaseModel):
    enabled: bool


class UpdateSystemEnabledRequest(BaseModel):
    enabled: bool


class WriteGuideRequest(BaseModel):
    name: str
    content: str


# --- Session store (sandbox agent auth) ---

sessions: dict[str, dict] = {}
_SESSION_TTL = 600  # 10 minutes


def register_session(session_token: str, user_id: str) -> None:
    """Register a session with Google credentials for a user."""
    _cleanup_expired_sessions()

    from scheduler.db import get_user_by_id

    creds = load_credentials(user_id)
    gmail = GmailClient(creds)

    db_user = get_user_by_id(user_id)
    extra_ids = (db_user.calendar_ids or []) if db_user else []
    calendar = CalendarClient(creds, config.scheduled_calendar_name, extra_calendar_ids=extra_ids)
    calendar.get_or_create_scheduled_calendar()

    sessions[session_token] = {
        "user_id": user_id,
        "gmail": gmail,
        "calendar": calendar,
        "created_at": time.time(),
    }


def _cleanup_expired_sessions() -> None:
    now = time.time()
    expired = [tok for tok, s in sessions.items() if now - s["created_at"] > _SESSION_TTL]
    for tok in expired:
        del sessions[tok]


def get_session(authorization: str = Header()) -> dict:
    """Validate the session token from the Authorization header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.removeprefix("Bearer ")
    session = sessions.get(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session token")

    if time.time() - session["created_at"] > _SESSION_TTL:
        del sessions[token]
        raise HTTPException(status_code=401, detail="Invalid or expired session token")

    return session


# --- Gmail routes ---


@app.post("/api/v1/gmail/search")
def gmail_search(req: SearchEmailsRequest, session: dict = Depends(get_session)):
    gmail: GmailClient = session["gmail"]
    emails = gmail.search(query=req.query, max_results=req.max_results)
    return {"emails": [_serialize_email(e) for e in emails]}


@app.get("/api/v1/gmail/thread/{thread_id}")
def gmail_thread(thread_id: str, session: dict = Depends(get_session)):
    gmail: GmailClient = session["gmail"]
    messages = gmail.get_thread(thread_id)
    return {"messages": [_serialize_email(e) for e in messages]}


@app.get("/api/v1/gmail/message/{message_id}")
def gmail_message(message_id: str, session: dict = Depends(get_session)):
    gmail: GmailClient = session["gmail"]
    email = gmail.get_email(message_id)
    return {"email": _serialize_email(email)}


@app.post("/api/v1/gmail/draft")
def gmail_draft(req: CreateDraftRequest, session: dict = Depends(get_session)):
    gmail: GmailClient = session["gmail"]
    from scheduler.db import get_user_by_id

    user = get_user_by_id(session["user_id"])
    body = req.body
    content_type = "plain"
    if user and user.scheduled_branding_enabled:
        html_body = html.escape(body).replace("\n", "<br>")
        html_body += '<br><br>sent by <a href="https://tryscheduled.com">Scheduled.</a>'
        body = html_body
        content_type = "html"

    draft_id = gmail.create_draft(
        thread_id=req.thread_id, to=req.to, subject=req.subject, body=body, content_type=content_type, cc=req.cc
    )

    from scheduler import analytics
    analytics.record_draft_composed(
        user_id=session["user_id"],
        thread_id=req.thread_id,
        draft_id=draft_id,
        thread_messages=req.thread_context or [],
        subject=req.subject,
        body=req.body,
    )

    return {"draft_id": draft_id}


@app.post("/api/v1/gmail/send")
def gmail_send(req: SendEmailRequest, session: dict = Depends(get_session)):
    gmail: GmailClient = session["gmail"]
    from scheduler.db import get_user_by_id

    user = get_user_by_id(session["user_id"])
    body = req.body
    content_type = "plain"
    if user and user.scheduled_branding_enabled:
        html_body = html.escape(body).replace("\n", "<br>")
        html_body += '<br><br>sent by <a href="https://tryscheduled.com">Scheduled.</a>'
        body = html_body
        content_type = "html"

    message_id = gmail.send_email(
        thread_id=req.thread_id,
        to=req.to,
        subject=req.subject,
        body=body,
        content_type=content_type,
        cc=req.cc,
    )
    return {"message_id": message_id, "status": "sent"}


# --- Calendar routes ---


@app.post("/api/v1/calendar/events")
def calendar_events(req: GetEventsRequest, session: dict = Depends(get_session)):
    calendar: CalendarClient = session["calendar"]
    events = calendar.get_all_events(
        time_min=datetime.fromisoformat(req.start_date),
        time_max=datetime.fromisoformat(req.end_date),
        include_primary=req.include_primary,
    )
    return {"events": [_serialize_event(e) for e in events]}


@app.post("/api/v1/calendar/find")
def calendar_find(req: FindEventRequest, session: dict = Depends(get_session)):
    calendar: CalendarClient = session["calendar"]
    event = calendar.find_event(
        summary=req.summary,
        time_min=datetime.fromisoformat(req.start_date),
        time_max=datetime.fromisoformat(req.end_date),
    )
    if event:
        return {"exists": True, "event": _serialize_event(event)}
    return {"exists": False, "event": None}


@app.get("/api/v1/calendar/timezone")
def calendar_timezone(session: dict = Depends(get_session)):
    calendar: CalendarClient = session["calendar"]
    return {"timezone": calendar.get_user_timezone()}


@app.post("/api/v1/calendar/add")
def calendar_add(req: AddEventRequest, session: dict = Depends(get_session)):
    calendar: CalendarClient = session["calendar"]
    event = Event(
        id=None,
        summary=req.summary,
        start=datetime.fromisoformat(req.start),
        end=datetime.fromisoformat(req.end),
        description=req.description,
        source="gmail",
    )
    event_id = calendar.add_event(event)
    return {"event_id": event_id, "status": "created"}


# --- Settings routes (sandbox agent auth) ---


@app.get("/api/v1/settings/branding")
def settings_branding_get(session: dict = Depends(get_session)):
    from scheduler.db import get_user_by_id

    user = get_user_by_id(session["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"scheduled_branding_enabled": user.scheduled_branding_enabled}


@app.put("/api/v1/settings/branding")
def settings_branding_put(req: UpdateBrandingRequest, session: dict = Depends(get_session)):
    from scheduler.db import get_user_by_id, update_scheduled_branding

    user = get_user_by_id(session["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    update_scheduled_branding(session["user_id"], req.enabled)
    return {"scheduled_branding_enabled": req.enabled}


@app.get("/api/v1/settings/autopilot")
def settings_autopilot_get(session: dict = Depends(get_session)):
    from scheduler.db import get_user_by_id

    user = get_user_by_id(session["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"autopilot_enabled": user.autopilot_enabled}


@app.put("/api/v1/settings/autopilot")
def settings_autopilot_put(req: UpdateAutopilotRequest, session: dict = Depends(get_session)):
    from scheduler.db import get_user_by_id, update_autopilot

    user = get_user_by_id(session["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    update_autopilot(session["user_id"], req.enabled)
    return {"autopilot_enabled": req.enabled}


class UpdateSalesEmailRequest(BaseModel):
    enabled: bool


@app.get("/api/v1/settings/sales-emails")
def settings_sales_emails_get(session: dict = Depends(get_session)):
    from scheduler.db import get_user_by_id

    user = get_user_by_id(session["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"process_sales_emails": user.process_sales_emails}


@app.put("/api/v1/settings/sales-emails")
def settings_sales_emails_put(req: UpdateSalesEmailRequest, session: dict = Depends(get_session)):
    from scheduler.db import get_user_by_id, update_process_sales_emails

    user = get_user_by_id(session["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    update_process_sales_emails(session["user_id"], req.enabled)
    return {"process_sales_emails": req.enabled}


@app.get("/api/v1/settings/system")
def settings_system_get(session: dict = Depends(get_session)):
    from scheduler.db import get_user_by_id

    user = get_user_by_id(session["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"system_enabled": user.system_enabled}


@app.put("/api/v1/settings/system")
def settings_system_put(req: UpdateSystemEnabledRequest, session: dict = Depends(get_session)):
    from scheduler.db import get_user_by_id, update_system_enabled

    user = get_user_by_id(session["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    update_system_enabled(session["user_id"], req.enabled)
    return {"system_enabled": req.enabled}


# --- Guide routes ---


class ReadGuideRequest(BaseModel):
    name: str


@app.post("/api/v1/guides/write")
def guides_write(req: WriteGuideRequest, session: dict = Depends(get_session)):
    from scheduler.guides import save_guide

    user_id = session["user_id"]
    save_guide(name=req.name, content=req.content, user_id=user_id)
    return {"status": "written"}


@app.post("/api/v1/guides/read")
def guides_read(req: ReadGuideRequest, session: dict = Depends(get_session)):
    from scheduler.db import get_guide

    user_id = session["user_id"]
    guide = get_guide(user_id=user_id, name=req.name)
    if not guide:
        raise HTTPException(status_code=404, detail=f"Guide '{req.name}' not found")
    return {"name": guide.name, "content": guide.content, "updated_at": guide.updated_at.isoformat()}


# --- Onboarding ---


def _is_onboarded(user_id: str, *, scheduled_calendar_id: str | None = None) -> bool:
    from scheduler.db import get_guides_for_user
    guides = get_guides_for_user(user_id)
    guide_names = {g.name for g in guides}
    has_guides = "scheduling_preferences" in guide_names and "email_style" in guide_names
    return has_guides and scheduled_calendar_id is not None


def _renew_gmail_watch(user_id: str) -> None:
    """Background task: renew Gmail watch for a returning user."""
    from scheduler.gmail.watch import setup_gmail_watch

    try:
        setup_gmail_watch(user_id)
        logger.info("sign-in: gmail watch renewed for user=%s", user_id)
    except Exception:
        logger.exception("sign-in: failed to renew gmail watch for user=%s", user_id)


def _run_onboarding_all(user_id: str) -> None:
    """Run backfill + both guide-writer agents for a user, then set up Gmail watch."""
    import anyio
    from scheduler.gmail.watch import setup_gmail_watch
    from scheduler.guides.backends import LocalGuideBackend
    from scheduler.guides.preferences import run_preferences_agent
    from scheduler.guides.style import run_style_agent
    from scheduler.onboarding.agent import _run_backfill_async as _run_backfill
    from scheduler.onboarding.backends import LocalBackend

    creds = load_credentials(user_id)
    gmail = GmailClient(creds)
    calendar = CalendarClient(creds, config.scheduled_calendar_name)
    cal_id = calendar.get_or_create_scheduled_calendar()
    if cal_id:
        from scheduler.db import update_scheduled_calendar_id
        update_scheduled_calendar_id(user_id, cal_id)

    guide_backend = LocalGuideBackend(gmail, calendar, user_id=user_id)
    onboarding_backend = LocalBackend(gmail, calendar)

    async def _run():
        async with anyio.create_task_group() as tg:
            tg.start_soon(_run_backfill, onboarding_backend, config.onboarding_lookback_days)
            tg.start_soon(run_preferences_agent, guide_backend)
            tg.start_soon(run_style_agent, guide_backend)

    anyio.run(_run)

    try:
        setup_gmail_watch(user_id)
        logger.info("onboarding: gmail watch set up for user=%s", user_id)
    except Exception:
        logger.exception("onboarding: failed to set up gmail watch for user=%s", user_id)


def _run_onboarding(user_id: str) -> None:
    """Background task: run onboarding and update status."""
    from scheduler.db import update_onboarding_status, update_system_enabled

    with _onboarding_lock:
        if _onboarding_status.get(user_id, {}).get("status") == "running":
            logger.info("onboarding: already running for user=%s, skipping", user_id)
            return
        _onboarding_status[user_id] = {
            "status": "running",
            "agents": {
                "backfill": "running",
                "preferences": "running",
                "style": "running",
            },
        }

    update_onboarding_status(user_id, "running")

    try:
        _run_onboarding_all(user_id)
        update_system_enabled(user_id, True)
        update_onboarding_status(user_id, "done")
        logger.info("onboarding: system enabled for user=%s", user_id)
        with _onboarding_lock:
            _onboarding_status.pop(user_id, None)
    except Exception as e:
        logger.exception("onboarding: failed for user=%s", user_id)
        update_onboarding_status(user_id, "failed")
        with _onboarding_lock:
            _onboarding_status[user_id] = {"status": "failed", "error": str(e)}


def _compose_draft(
    user_id: str,
    email,
    classification,
    gmail: GmailClient,
    calendar: CalendarClient,
    autopilot: bool,
    user_email: str = "",
    thread_messages: list[dict] | None = None,
) -> dict | None:
    from scheduler.drafts.composer import DraftComposer, LocalDraftBackend

    backend = LocalDraftBackend(gmail, calendar, user_id=user_id, thread_messages=thread_messages)
    composer = DraftComposer(backend, user_id, autopilot=autopilot, user_email=user_email)
    return composer.compose_and_create_draft(email, classification)


@app.post("/api/v1/onboarding/run")
def onboarding_run(request: Request, background_tasks: BackgroundTasks):
    """Kick off the style + preferences guide agents for this user."""
    session = get_web_session(request)
    user_id = session["user_id"]
    with _onboarding_lock:
        if _onboarding_status.get(user_id, {}).get("status") == "running":
            logger.info("onboarding: already running for user=%s", user_id)
            return {"status": "already_running"}
    logger.info("onboarding: starting all agents for user=%s", user_id)
    background_tasks.add_task(_run_onboarding, user_id)
    return {"status": "started"}


# --- Gmail webhook ---


def _handle_sent_message_for_invite(user_id: str, email, gmail: GmailClient, calendar: CalendarClient) -> None:
    """Check if a user-sent message should trigger a pending calendar invite."""
    from scheduler.classifier.intent import verify_sent_message_for_invite
    from scheduler.db import get_pending_invite_by_thread, delete_pending_invite, update_pending_invite

    pending = get_pending_invite_by_thread(user_id, email.thread_id)
    if not pending:
        return

    logger.info("gmail_webhook: sent message in thread %s has pending invite, verifying", email.thread_id)

    thread_messages = []
    try:
        for t_email in gmail.get_thread(email.thread_id):
            if t_email.id == email.id:
                break
            thread_messages.append({"sender": t_email.sender, "body": t_email.body, "date": t_email.date.isoformat()})
    except Exception:
        logger.warning("gmail_webhook: failed to fetch thread for invite verification")

    result = verify_sent_message_for_invite(
        sent_message_body=email.body,
        sent_message_sender=email.sender,
        thread_messages=thread_messages,
        pending_invite=pending,
    )

    logger.info("gmail_webhook: invite verification: action=%s reason=%s", result.action, result.reason)

    if result.action == "skip":
        delete_pending_invite(pending.id)
        logger.info("gmail_webhook: deleted pending invite %s (skipped)", pending.id)
        return

    if result.action == "update":
        update_pending_invite(
            pending.id,
            attendee_emails=result.updated_attendee_emails,
            event_summary=result.updated_event_summary,
            event_start=datetime.fromisoformat(result.updated_event_start) if result.updated_event_start else None,
            event_end=datetime.fromisoformat(result.updated_event_end) if result.updated_event_end else None,
            add_google_meet=result.updated_add_google_meet,
            location=result.updated_location,
        )
        if result.updated_attendee_emails:
            pending.attendee_emails = result.updated_attendee_emails
        if result.updated_event_summary:
            pending.event_summary = result.updated_event_summary
        if result.updated_event_start:
            pending.event_start = datetime.fromisoformat(result.updated_event_start)
        if result.updated_event_end:
            pending.event_end = datetime.fromisoformat(result.updated_event_end)
        if result.updated_add_google_meet is not None:
            pending.add_google_meet = result.updated_add_google_meet
        if result.updated_location is not None:
            pending.location = result.updated_location

    # action == "send" or "update" — create the calendar invite
    try:
        calendar.create_invite_event(
            summary=pending.event_summary,
            start=pending.event_start,
            end=pending.event_end,
            attendee_emails=pending.attendee_emails,
            location=pending.location,
            add_google_meet=pending.add_google_meet,
        )
        logger.info("gmail_webhook: created invite event for thread %s", email.thread_id)
    except Exception:
        logger.exception("gmail_webhook: failed to create invite event for thread %s", email.thread_id)

    delete_pending_invite(pending.id)


def _process_new_messages(user_id: str, email_address: str, history_id: str) -> None:
    """Background task: fetch new messages since last history ID and process them."""
    from scheduler.db import get_user_by_id, update_gmail_history_id

    user = get_user_by_id(user_id)
    if not user:
        return
    if not user.system_enabled:
        logger.info("gmail_webhook: system disabled for user=%s, skipping", email_address)
        return
    if not user.gmail_history_id:
        update_gmail_history_id(user_id, history_id)
        logger.info("gmail_webhook: stored initial history_id=%s for user=%s", history_id, email_address)
        return

    creds = load_credentials(user_id)
    gmail = GmailClient(creds)

    try:
        new_message_ids = gmail.get_history(user.gmail_history_id)
    except Exception:
        logger.warning("gmail_webhook: history expired for user=%s, resetting", email_address)
        update_gmail_history_id(user_id, history_id)
        return

    update_gmail_history_id(user_id, history_id)

    if not new_message_ids:
        return

    logger.info(
        "gmail_webhook: %d new message(s) for user=%s: %s",
        len(new_message_ids),
        email_address,
        new_message_ids,
    )

    from scheduler.classifier.intent import classify_email, SchedulingIntent
    from scheduler.classifier.newsletter import is_mass_email
    from scheduler.db import try_claim_message

    calendar = CalendarClient(creds, config.scheduled_calendar_name, extra_calendar_ids=user.calendar_ids or [])

    for message_id in new_message_ids:
        if not try_claim_message(user_id, message_id):
            logger.info("gmail_webhook: message %s already claimed, skipping", message_id)
            continue

        try:
            email = gmail.get_email(message_id)

            # User-sent messages: check if there's a pending invite for this thread
            if email.sender and email_address in email.sender:
                _handle_sent_message_for_invite(user_id, email, gmail, calendar)
                try:
                    from scheduler import analytics
                    analytics.record_draft_sent(user_id, email.thread_id, email.body, email.date)
                except Exception:
                    logger.debug("analytics: failed to check sent draft for message %s", message_id, exc_info=True)
                logger.info("gmail_webhook: message %s is from the user, skipping", message_id)
                continue

            # Skip newsletters / mass emails (before classifier, saves API cost)
            if is_mass_email(email.headers, email.sender):
                logger.info("gmail_webhook: message %s is a mass email/newsletter, skipping", message_id)
                continue

            # Fetch full thread for classifier context
            thread_messages = []
            try:
                thread_emails = gmail.get_thread(email.thread_id)
                for t_email in thread_emails:
                    thread_messages.append({
                        "sender": t_email.sender,
                        "subject": t_email.subject,
                        "body": t_email.body,
                        "date": t_email.date.isoformat(),
                    })
                    if t_email.id == email.id:
                        break
            except Exception:
                logger.warning("gmail_webhook: failed to fetch thread %s for context, classifying without", email.thread_id)

            classification = classify_email(
                email.subject, email.body, email.sender,
                thread_messages=thread_messages,
                recipient=email.recipient, cc=email.cc,
            )

            from scheduler import analytics
            analytics.track(user_id, "email_classified", {
                "intent": classification.intent.value,
                "confidence": classification.confidence,
                "is_sales_email": classification.is_sales_email,
                "message_id": message_id,
            })

            if classification.intent == SchedulingIntent.DOESNT_NEED_DRAFT:
                logger.info("gmail_webhook: message %s is not scheduling-related, skipping", message_id)
                continue

            # Skip cold outreach unless user opted in
            if classification.is_sales_email and not user.process_sales_emails:
                logger.info("gmail_webhook: message %s is cold outreach, skipping", message_id)
                continue

            logger.info(
                "gmail_webhook: message %s classified as %s (confidence=%.2f), composing draft",
                message_id,
                classification.intent.value,
                classification.confidence,
            )

            compose_result = _compose_draft(
                user_id=user_id,
                email=email,
                classification=classification,
                gmail=gmail,
                calendar=calendar,
                autopilot=user.autopilot_enabled,
                user_email=email_address,
                thread_messages=thread_messages,
            )

            compose_result = compose_result or {}
            draft_id = compose_result.get("draft_id")
            invite_proposal = compose_result.get("invite_proposal")

            if draft_id is None:
                logger.info("gmail_webhook: thread for message %s already resolved, no draft created", message_id)
            else:
                logger.info("gmail_webhook: created draft %s for message %s", draft_id, message_id)

                if invite_proposal:
                    from scheduler.db import create_pending_invite
                    try:
                        create_pending_invite(
                            user_id=user_id,
                            thread_id=email.thread_id,
                            attendee_emails=invite_proposal["attendee_emails"],
                            event_summary=invite_proposal["event_summary"],
                            event_start=datetime.fromisoformat(invite_proposal["event_start"]),
                            event_end=datetime.fromisoformat(invite_proposal["event_end"]),
                            add_google_meet=invite_proposal.get("add_google_meet", False),
                            location=invite_proposal.get("location", ""),
                        )
                        logger.info("gmail_webhook: created pending invite for thread %s", email.thread_id)
                    except Exception:
                        logger.exception("gmail_webhook: failed to create pending invite for thread %s", email.thread_id)

                analytics.track(user_id, "draft_composed", {
                    "thread_id": email.thread_id,
                    "draft_id": draft_id,
                    "was_autopilot": draft_id.startswith("sent:") if isinstance(draft_id, str) else False,
                })

        except Exception as exc:
            if _is_gmail_404(exc):
                logger.warning("gmail_webhook: message %s not found (deleted?), skipping", message_id)
            else:
                logger.exception("gmail_webhook: failed to process message %s for user=%s", message_id, email_address)


@app.post("/webhooks/gmail")
async def gmail_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive Gmail push notifications via Google Cloud Pub/Sub."""
    if config.gmail_webhook_token:
        token = request.query_params.get("token", "")
        if not hmac.compare_digest(token, config.gmail_webhook_token):
            raise HTTPException(status_code=403, detail="Invalid webhook token")

    from scheduler.db import get_user_by_email

    body = await request.json()
    message = body.get("message", {})
    data_b64 = message.get("data", "")

    if not data_b64:
        raise HTTPException(status_code=400, detail="Missing message data")

    try:
        payload = json.loads(base64.urlsafe_b64decode(data_b64))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid message data")

    email_address = payload.get("emailAddress")
    history_id = str(payload.get("historyId", ""))

    if not email_address or not history_id:
        raise HTTPException(status_code=400, detail="Missing emailAddress or historyId")

    if _is_cached_unknown_gmail_webhook_email(email_address):
        logger.info("gmail_webhook: cached unknown email %s", email_address)
        return {"status": "ignored", "reason": "unknown user"}

    user = await asyncio.to_thread(get_user_by_email, email_address)
    if not user:
        _cache_unknown_gmail_webhook_email(email_address)
        logger.warning("gmail_webhook: unknown email %s", email_address)
        return {"status": "ignored", "reason": "unknown user"}

    background_tasks.add_task(_process_new_messages, str(user.id), email_address, history_id)

    return {"status": "ok"}


# --- Web API routes ---


@app.post("/web/api/v1/events/track")
def web_track_event(request: Request):
    """No-op event tracking endpoint (kept for frontend compatibility)."""
    return {"status": "ok"}


@app.get("/web/api/v1/onboarding/status")
def web_onboarding_status(
    user: dict = Depends(get_authenticated_user),
    background_tasks: BackgroundTasks = None,
):
    from scheduler.db import get_user_by_id

    db_user = get_user_by_id(user["user_id"])
    connected = db_user is not None and db_user.google_refresh_token is not None

    if connected:
        ready = _is_onboarded(user["user_id"], scheduled_calendar_id=db_user.scheduled_calendar_id)
    else:
        ready = False

    result = {"ready": ready, "connected": connected}
    if not ready and connected:
        user_id = user["user_id"]
        status_entry = _onboarding_status.get(user_id)

        if status_entry:
            if status_entry.get("status") == "failed":
                result["failed"] = True
                result["error"] = status_entry.get("error", "Unknown error")
            if "agents" in status_entry:
                result["agents"] = status_entry["agents"]
        elif db_user.onboarding_status == "running":
            logger.info("onboarding: detected interrupted run for user=%s, auto-retrying", user_id)
            background_tasks.add_task(_run_onboarding, user_id)
        elif db_user.onboarding_status == "failed":
            result["failed"] = True
            result["error"] = "Onboarding failed. Please try again."

    return result


@app.get("/web/api/v1/settings")
def web_settings_get(user: dict = Depends(get_authenticated_user)):
    from scheduler.db import get_guides_for_user, get_user_by_id

    db_user = get_user_by_id(user["user_id"])
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    guides = get_guides_for_user(user["user_id"])

    return {
        "system_enabled": db_user.system_enabled,
        "autopilot_enabled": db_user.autopilot_enabled,
        "process_sales_emails": db_user.process_sales_emails,
        "scheduled_branding_enabled": db_user.scheduled_branding_enabled,
        "reasoning_emails_enabled": db_user.reasoning_emails_enabled,
        "scheduled_calendar_id": db_user.scheduled_calendar_id,
        "calendar_ids": db_user.calendar_ids or [],
        "guides": [
            {"name": g.name, "content": g.content, "updated_at": g.updated_at.isoformat()}
            for g in guides
        ],
    }


class WebUpdateSystemEnabledRequest(BaseModel):
    enabled: bool


@app.put("/web/api/v1/settings/system")
def web_settings_system(req: WebUpdateSystemEnabledRequest, user: dict = Depends(get_authenticated_user)):
    from scheduler.db import update_system_enabled
    update_system_enabled(user["user_id"], req.enabled)
    return {"system_enabled": req.enabled}


class WebUpdateAutopilotRequest(BaseModel):
    enabled: bool


@app.put("/web/api/v1/settings/autopilot")
def web_settings_autopilot(req: WebUpdateAutopilotRequest, user: dict = Depends(get_authenticated_user)):
    from scheduler.db import update_autopilot
    update_autopilot(user["user_id"], req.enabled)
    return {"autopilot_enabled": req.enabled}


class WebUpdateSalesEmailRequest(BaseModel):
    enabled: bool


@app.put("/web/api/v1/settings/sales-emails")
def web_settings_sales_emails(req: WebUpdateSalesEmailRequest, user: dict = Depends(get_authenticated_user)):
    from scheduler.db import update_process_sales_emails
    update_process_sales_emails(user["user_id"], req.enabled)
    return {"process_sales_emails": req.enabled}


class WebUpdateBrandingRequest(BaseModel):
    enabled: bool


@app.put("/web/api/v1/settings/branding")
def web_settings_branding(req: WebUpdateBrandingRequest, user: dict = Depends(get_authenticated_user)):
    from scheduler.db import update_scheduled_branding
    update_scheduled_branding(user["user_id"], req.enabled)
    return {"scheduled_branding_enabled": req.enabled}


class WebUpdateReasoningEmailsRequest(BaseModel):
    enabled: bool


@app.put("/web/api/v1/settings/reasoning-emails")
def web_settings_reasoning_emails(req: WebUpdateReasoningEmailsRequest, user: dict = Depends(get_authenticated_user)):
    from scheduler.db import update_reasoning_emails_enabled
    update_reasoning_emails_enabled(user["user_id"], req.enabled)
    return {"reasoning_emails_enabled": req.enabled}


@app.get("/web/api/v1/calendars")
def web_list_calendars(user: dict = Depends(get_authenticated_user)):
    """List all Google calendars visible to the user, with selection state."""
    from scheduler.db import get_user_by_id

    db_user = get_user_by_id(user["user_id"])
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    creds = load_credentials(user["user_id"])
    calendar = CalendarClient(creds, config.scheduled_calendar_name)
    selected_ids = set(db_user.calendar_ids or [])

    all_cals = calendar.list_calendars()
    scheduled_id = calendar.get_or_create_scheduled_calendar()

    return [
        {**cal, "selected": cal["id"] in selected_ids}
        for cal in all_cals
        if cal["id"] != scheduled_id
    ]


class WebUpdateCalendarsRequest(BaseModel):
    calendar_ids: list[str]


@app.put("/web/api/v1/settings/calendars")
def web_settings_calendars(req: WebUpdateCalendarsRequest, user: dict = Depends(get_authenticated_user)):
    from scheduler.db import update_calendar_ids
    update_calendar_ids(user["user_id"], req.calendar_ids)
    return {"calendar_ids": req.calendar_ids}


class WebUpdateGuideRequest(BaseModel):
    content: str


@app.put("/web/api/v1/guides/{name}")
def web_guide_update(name: str, req: WebUpdateGuideRequest, user: dict = Depends(get_authenticated_user)):
    from scheduler.db import upsert_guide
    guide = upsert_guide(user["user_id"], name, req.content)
    return {"name": guide.name, "content": guide.content, "updated_at": guide.updated_at.isoformat()}


@app.post("/web/api/v1/guides/{name}/regenerate")
def web_guide_regenerate(name: str, background_tasks: BackgroundTasks, user: dict = Depends(get_authenticated_user)):
    """Regenerate a single guide by re-running the appropriate agent."""
    if name not in ("scheduling_preferences", "email_style"):
        raise HTTPException(status_code=400, detail=f"Unknown guide: {name}")
    background_tasks.add_task(_run_guide_regeneration, user["user_id"], name)
    return {"status": "regenerating"}


def _run_guide_regeneration(user_id: str, guide_name: str) -> None:
    """Background task: re-run a single guide agent for a user."""
    import anyio

    from scheduler.guides.backends import LocalGuideBackend

    creds = load_credentials(user_id)
    gmail = GmailClient(creds)
    calendar = CalendarClient(creds, config.scheduled_calendar_name)
    calendar.get_or_create_scheduled_calendar()

    guide_backend = LocalGuideBackend(gmail, calendar, user_id=user_id)

    if guide_name == "scheduling_preferences":
        from scheduler.guides.preferences import run_preferences_agent
        anyio.run(run_preferences_agent, guide_backend)
    elif guide_name == "email_style":
        from scheduler.guides.style import run_style_agent
        anyio.run(run_style_agent, guide_backend)

    logger.info("guide_regeneration: completed %s for user=%s", guide_name, user_id)


@app.post("/web/api/v1/account/disconnect")
def web_account_disconnect(request: Request, user: dict = Depends(get_authenticated_user)):
    from scheduler.db import disconnect_user, get_user_by_id

    db_user = get_user_by_id(user["user_id"])
    if db_user and db_user.google_refresh_token:
        import httpx
        try:
            httpx.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": db_user.google_refresh_token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except Exception:
            logger.warning("Failed to revoke Google token for user=%s", user["user_id"])

    disconnect_user(user["user_id"])
    return JSONResponse({"status": "disconnected"})


@app.post("/api/v1/gmail/watch/renew")
def gmail_watch_renew():
    """Renew Gmail push notification watches for all users."""
    from scheduler.gmail.watch import renew_all_watches
    result = renew_all_watches()
    return result
