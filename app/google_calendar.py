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

def create_calendar_event(credentials: Credentials, summary: str, description: str,
                          start_dt, end_dt, attendees=None, timezone="America/Sao_Paulo"):
    """
    credentials: google oauth2 Credentials (com acesso calendar.events)
    start_dt, end_dt: datetime com timezone (p.ex. aware datetimes)
    attendees: list de dicts como [{"email":"x@y.com"}, ...]
    """
    service = build("calendar", "v3", credentials=credentials)
    
    event_body = {
        "summary": summary,
        "description": description or "",
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": timezone
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": timezone
        },
        "attendees": attendees or [],
        # pedir pro Google criar um Google Meet
        "conferenceData": {
            "createRequest": {
                "requestId": f"meet-{start_dt.timestamp()}",  # id único (qualquer string única)
                "conferenceSolutionKey": {"type": "hangoutsMeet"}
            }
        },
        # opcional: reminders
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 30},
                {"method": "email", "minutes": 60*24}
            ]
        }
    }

    # IMPORTANTE: passar conferenceDataVersion=1 para que o meet seja criado
    event = service.events().insert(calendarId="primary",
                                    body=event_body,
                                    conferenceDataVersion=1,
                                    sendUpdates="all"  # "all" para enviar convites por email
                                   ).execute()
    # event terá campos: id, htmlLink, conferenceData (com entryPoints / meet link), etc.
    meet_link = None
    conf = event.get("conferenceData")
    if conf:
        for ep in conf.get("entryPoints", []):
            if ep.get("entryPointType") == "video":  # normalmente 'video'
                meet_link = ep.get("uri")
                break

    # Agora o event tem:
    # - event["id"]              → ID do evento no Calendar
    # - event["htmlLink"]        → link do evento no calendário
    # - meet_link                → link do Meet

    return {
        "id": event.get("id"),
        "htmlLink": event.get("htmlLink"),
        "meet_link": meet_link
    }
