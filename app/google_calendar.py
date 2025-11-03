# app/google_calendar.py
import os
import json
from urllib.parse import urlencode
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from datetime import datetime
from flask import current_app

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

def get_oauth_flow(redirect_uri=None, state=None):
    """Cria um objeto Flow para iniciar autorização."""
    client_config = {
        "web": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri or os.environ.get("GOOGLE_OAUTH_REDIRECT_URI"))
    if state:
        flow.redirect_uri = flow.redirect_uri
        flow.params = {"state": state}
    return flow

def build_credentials_from_tokens(token_data):
    """
    token_data: dict com keys access_token, refresh_token, token_uri, client_id, client_secret, scopes, expiry
    ou o dict retornado por google oauth
    """
    creds = Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        scopes=SCOPES
    )
    return creds

def create_calendar_event(credentials, calendar_id="primary", summary=None, description=None, start_dt=None, end_dt=None, attendees=None, timezone="America/Sao_Paulo"):
    """
    credentials: google.oauth2.credentials.Credentials
    start_dt, end_dt: datetime objects with tzinfo
    attendees: list of dicts [{"email": "..."}]
    """
    service = build("calendar", "v3", credentials=credentials)
    event_body = {
        "summary": summary or "Aula agendada",
        "description": description or "",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone},
    }
    if attendees:
        event_body["attendees"] = attendees

    event = service.events().insert(calendarId=calendar_id, body=event_body, sendUpdates="all").execute()
    return event  # event contains 'id' and 'htmlLink'
