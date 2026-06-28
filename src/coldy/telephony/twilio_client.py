"""Twilio Programmable Voice wrapper for outbound calls.

Why Twilio: first-class Media Streams (<Connect><Stream>) for piping live audio
to our AI, mature Programmable Voice, AMD (answering-machine detection), and
status callbacks. Telnyx is a viable lower-cost alternative with an equivalent
streaming feature — the rest of the system is provider-agnostic behind this
class, so swapping is localized here.
"""

from __future__ import annotations

from ..config import settings
from ..logging import get_logger

log = get_logger("coldy.telephony.twilio")


class TwilioTelephony:
    def __init__(self) -> None:
        from twilio.rest import Client

        self._client = Client(
            # Reads TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN from env if omitted,
            # but we pass explicitly for clarity.
            username=_env("TWILIO_ACCOUNT_SID"),
            password=_env("TWILIO_AUTH_TOKEN"),
        )

    def place_call(
        self, *, to_number: str, call_id: int, lead_id: int, from_number: str | None = None
    ) -> str:
        """Place an outbound call. Returns the Twilio Call SID.

        - ``from_number`` overrides the caller ID (local-presence pool); defaults
          to the single configured number.
        - ``url`` points to our webhook which returns <Connect><Stream> TwiML.
        - AMD ("Enable") detects voicemail so we don't pitch an answering machine.
        - ``status_callback`` reports ringing/answered/completed transitions.
        """
        base = settings.public_base_url.rstrip("/")
        voice_url = f"{base}/twilio/voice?call_id={call_id}&lead_id={lead_id}"
        status_url = f"{base}/twilio/status?call_id={call_id}"
        from_num = from_number or settings.twilio_from_number

        kwargs = dict(
            to=to_number,
            from_=from_num,
            url=voice_url,
            method="POST",
            status_callback=status_url,
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST",
            # Answering-machine detection: Twilio reports AnsweredBy on the
            # status callback so the dialer can mark/handle voicemails.
            machine_detection="Enable",
            # Don't let a call ring forever.
            timeout=30,
        )
        if settings.record_calls:
            # Recording posture is enforced separately (per-state notice via the
            # compliance engine); only record when explicitly enabled.
            kwargs["record"] = True
            kwargs["recording_status_callback"] = f"{base}/twilio/recording?call_id={call_id}"
            kwargs["recording_status_callback_method"] = "POST"

        call = self._client.calls.create(**kwargs)
        log.info("Placed call %s -> %s (call_id=%s)", call.sid, to_number, call_id)
        return call.sid

    def leave_voicemail(self, call_sid: str, message: str) -> None:
        """Redirect a live (machine-answered) call to a short voicemail message."""
        from .twiml import voicemail_twiml

        try:
            self._client.calls(call_sid).update(twiml=voicemail_twiml(message))
            log.info("Left voicemail on call %s", call_sid)
        except Exception as e:  # noqa: BLE001
            log.warning("Voicemail failed for %s: %s", call_sid, e)

    def send_sms(self, to_number: str, body: str) -> str | None:
        """Send an SMS follow-up. Returns the message SID, or None on failure."""
        try:
            msg = self._client.messages.create(
                to=to_number, from_=settings.twilio_from_number, body=body
            )
            log.info("Sent SMS %s -> %s", msg.sid, to_number)
            return msg.sid
        except Exception as e:  # noqa: BLE001
            log.warning("SMS failed to %s: %s", to_number, e)
            return None

    def redirect_to_human(self, call_sid: str, to_number: str | None = None) -> None:
        """Warm-transfer a live call by updating it with <Dial> TwiML."""
        from .twiml import dial_human_twiml

        self._client.calls(call_sid).update(twiml=dial_human_twiml(to_number))
        log.info("Redirected call %s to human", call_sid)

    def hangup(self, call_sid: str) -> None:
        try:
            self._client.calls(call_sid).update(status="completed")
        except Exception as e:  # noqa: BLE001
            log.warning("Hangup failed for %s: %s", call_sid, e)


def _env(name: str) -> str:
    import os

    return os.getenv(name, "")
