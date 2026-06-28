import os

from fastapi.testclient import TestClient

from coldy.api.app import app
from coldy.api.security import media_token_ok
from coldy.config import settings
from coldy.db.session import init_db

client = TestClient(app)


def setup_module(_module):
    init_db()


def test_dashboard_requires_auth_when_configured():
    settings.dashboard_user, settings.dashboard_password = "admin", "pw"
    try:
        assert client.get("/dashboard").status_code == 401
        assert client.get("/dashboard", auth=("admin", "pw")).status_code == 200
        assert client.get("/api/campaigns", auth=("admin", "pw")).status_code == 200
    finally:
        settings.dashboard_user, settings.dashboard_password = "", ""


def test_dashboard_open_when_unconfigured():
    assert client.get("/dashboard").status_code == 200


def test_optin_api_token_enforced():
    settings.optin_api_token = "secret"
    try:
        bad = client.post("/api/optin", json={"phone": "+16125558001", "consent": True})
        assert bad.status_code == 403
        ok = client.post(
            "/api/optin",
            json={"phone": "+16125558001", "consent": True},
            headers={"X-Coldy-Token": "secret"},
        )
        assert ok.status_code == 200
    finally:
        settings.optin_api_token = ""


def test_twilio_webhook_rejects_unsigned_request():
    os.environ["TWILIO_AUTH_TOKEN"] = "testtoken"
    settings.twilio_validate_signatures = True
    try:
        r = client.post("/twilio/status?call_id=1", data={"CallStatus": "completed"})
        assert r.status_code == 403
    finally:
        os.environ.pop("TWILIO_AUTH_TOKEN", None)


def test_media_token_helper():
    settings.media_token = "abc"
    try:
        assert media_token_ok("abc")
        assert not media_token_ok("nope")
    finally:
        settings.media_token = ""
