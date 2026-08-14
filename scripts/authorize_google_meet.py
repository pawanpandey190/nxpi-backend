#!/usr/bin/env python3
"""
One-time Google OAuth2 authorization script.
Run this once to get a refresh token for creating Google Meet rooms.

Usage:
    python scripts/authorize_google_meet.py

After running, it will print the refresh token to add to your .env file.
"""

import json
import os
import sys
import webbrowser
from urllib.parse import urlencode, urlparse, parse_qs

import requests

# ─── Load credentials from .env ───────────────────────────────────────────────
# Try to load from environment or prompt
CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or input("Paste your OAuth2 Client ID: ").strip()
CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or input("Paste your OAuth2 Client Secret: ").strip()

REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"  # Desktop app redirect
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/meetings.space.created",
]

# ─── Step 1: Build auth URL ────────────────────────────────────────────────────
auth_params = {
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "response_type": "code",
    "scope": " ".join(SCOPES),
    "access_type": "offline",
    "prompt": "consent",
}

auth_url = f"https://accounts.google.com/o/oauth2/auth?{urlencode(auth_params)}"

print("\n" + "=" * 60)
print("STEP 1: Open this URL in your browser and sign in with")
print("        krishnakalia70@gmail.com")
print("=" * 60)
print(f"\n{auth_url}\n")

try:
    webbrowser.open(auth_url)
    print("(Browser should have opened automatically)")
except Exception:
    print("(Please open the URL manually)")

# ─── Step 2: Get the auth code ────────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 2: After authorizing, Google will show you a code.")
print("        Copy and paste it below.")
print("=" * 60)
auth_code = input("\nPaste the authorization code here: ").strip()

# ─── Step 3: Exchange code for tokens ─────────────────────────────────────────
token_response = requests.post(
    "https://oauth2.googleapis.com/token",
    data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    },
)

if token_response.status_code != 200:
    print(f"\n❌ Failed to get tokens: {token_response.json()}")
    sys.exit(1)

tokens = token_response.json()
refresh_token = tokens.get("refresh_token")

if not refresh_token:
    print("\n❌ No refresh token returned. Try running again (make sure prompt=consent is set).")
    sys.exit(1)

# ─── Step 4: Print the result ─────────────────────────────────────────────────
print("\n" + "=" * 60)
print("✅ SUCCESS! Add these to your backend/.env file:")
print("=" * 60)
print(f"\nGOOGLE_OAUTH_CLIENT_ID={CLIENT_ID}")
print(f"GOOGLE_OAUTH_CLIENT_SECRET={CLIENT_SECRET}")
print(f"GOOGLE_OAUTH_REFRESH_TOKEN={refresh_token}")
print("\n" + "=" * 60)

# ─── Step 5: Test creating a Google Meet room ─────────────────────────────────
print("\nTesting Google Meet creation with your credentials...")

creds_data = {
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "refresh_token": refresh_token,
    "grant_type": "refresh_token",
}
access_resp = requests.post("https://oauth2.googleapis.com/token", data=creds_data)
access_token = access_resp.json().get("access_token")

test_event = {
    "summary": "NXPI Test Meeting",
    "start": {"dateTime": "2026-09-01T14:00:00", "timeZone": "Asia/Kolkata"},
    "end":   {"dateTime": "2026-09-01T14:30:00", "timeZone": "Asia/Kolkata"},
    "conferenceData": {
        "createRequest": {
            "requestId": "nxpi-test-auth-001",
            "conferenceSolutionKey": {"type": "hangoutsMeet"},
        }
    },
}

event_resp = requests.post(
    "https://www.googleapis.com/calendar/v3/calendars/primary/events?conferenceDataVersion=1",
    headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
    json=test_event,
)

if event_resp.status_code == 200:
    meet_link = event_resp.json().get("hangoutsMeetLink")
    print(f"\n✅ GOOGLE MEET LINK GENERATED: {meet_link}")
    print("\nYour setup is working! Every onboarding will now generate a real Google Meet link.")
else:
    print(f"\n⚠️  Event creation test: {event_resp.status_code} — {event_resp.json()}")
