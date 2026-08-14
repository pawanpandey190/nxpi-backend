"""
Google Calendar + Meet Service.

Always returns GOOGLE_MEET_DEFAULT_ROOM as the meeting link (stored in .env).
Also creates a Google Calendar event so the admin can track the schedule.
"""

import logging
from datetime import datetime, timedelta, timezone

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_MEET_ROOM = "https://meet.google.com/ezn-wtth-zxw"


def _get_meet_link() -> str:
    """Return the fixed Google Meet room URL from config."""
    return settings.GOOGLE_MEET_DEFAULT_ROOM or DEFAULT_MEET_ROOM


def _get_service_account_calendar_service():
    """Build Calendar API service using the service account (for creating calendar events)."""
    client_email = settings.GOOGLE_CALENDAR_CLIENT_EMAIL
    private_key = settings.GOOGLE_CALENDAR_PRIVATE_KEY
    if not client_email or not private_key:
        return None
    formatted_key = private_key.replace("\\n", "\n")
    credentials_info = {
        "type": "service_account",
        "client_email": client_email,
        "private_key": formatted_key,
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    scopes = ["https://www.googleapis.com/auth/calendar"]
    creds = service_account.Credentials.from_service_account_info(credentials_info, scopes=scopes)
    return build("calendar", "v3", credentials=creds)


async def create_google_meet_event(
    company_name: str,
    client_email: str,
    discussion_date: str,
    discussion_time: str,
    discussion_timezone: str = "Asia/Kolkata",
) -> tuple[str, str | None]:
    """
    Returns the fixed Google Meet room URL and creates a Google Calendar event
    for scheduling visibility. Both client and admin always get the same meet_link.
    """
    meet_link = _get_meet_link()

    # ── Build start/end times ───────────────────────────────────────────────
    time_str = discussion_time or "10:00"
    if len(time_str.split(":")) == 2:
        time_str += ":00"
    start_iso = f"{discussion_date}T{time_str}"
    try:
        start_dt = datetime.strptime(start_iso, "%Y-%m-%dT%H:%M:%S")
        end_iso = (start_dt + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        end_iso = start_iso

    event_body = {
        "summary": f"NXπ Onboarding Discussion: {company_name}",
        "description": (
            f"Enterprise Onboarding & Technical Consultation for {company_name}.\n"
            f"Client Email: {client_email}\n"
            f"Scheduled Time: {discussion_date} at {discussion_time} ({discussion_timezone})\n\n"
            f"Join Google Meet: {meet_link}"
        ),
        "location": meet_link,
        "start": {"dateTime": start_iso, "timeZone": discussion_timezone},
        "end": {"dateTime": end_iso, "timeZone": discussion_timezone},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 24 * 60},
                {"method": "popup", "minutes": 30},
            ],
        },
    }

    # ── Create calendar event (best-effort, does not block meet_link return) ─
    try:
        svc = _get_service_account_calendar_service()
        if svc:
            calendar_id = settings.GOOGLE_CALENDAR_ID or "primary"
            res = svc.events().insert(calendarId=calendar_id, body=event_body).execute()
            event_id = res.get("id")
            logger.info(
                f"Calendar event created for {company_name} on {discussion_date}: "
                f"event_id={event_id}, meet_link={meet_link}"
            )
            return meet_link, event_id
    except Exception as exc:
        logger.warning(f"Calendar event creation failed (meet_link still returned): {exc}")

    return meet_link, None
