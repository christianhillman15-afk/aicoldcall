"""TwiML generation.

Outbound flow:
  1. We place a call via the REST API pointing its ``url`` at our webhook.
  2. Twilio fetches that webhook, which returns ``connect_stream_twiml`` — a
     <Connect><Stream> that bridges the call audio to our websocket where the
     Pipecat bot runs.

Warm transfer:
  When the bot decides to transfer, we update the live call with
  ``dial_human_twiml`` so Twilio <Dial>s the human specialist.
"""

from __future__ import annotations

from twilio.twiml.voice_response import Connect, VoiceResponse

from ..config import settings


def connect_stream_twiml(websocket_url: str, *, call_id: int, lead_id: int) -> str:
    """<Connect><Stream> TwiML that hands call audio to our media-stream socket.

    Custom parameters are delivered in the Twilio "start" message so the bot
    knows which call/lead it is handling.
    """
    response = VoiceResponse()
    connect = Connect()
    stream = connect.stream(url=websocket_url)
    stream.parameter(name="call_id", value=str(call_id))
    stream.parameter(name="lead_id", value=str(lead_id))
    response.append(connect)
    return str(response)


def voicemail_twiml(message: str) -> str:
    """Speak a short compliant voicemail, then hang up. Used when AMD detects a
    machine and voicemail is enabled."""
    response = VoiceResponse()
    response.say(message)
    response.hangup()
    return str(response)


def dial_human_twiml(to_number: str | None = None) -> str:
    """TwiML to warm-transfer the live call to a human specialist."""
    to = to_number or settings.transfer_number
    response = VoiceResponse()
    if to:
        response.say("Connecting you with a specialist now. One moment.")
        response.dial(to)
    else:
        response.say(
            "Sorry, no specialist is available right now. We'll follow up shortly. Goodbye."
        )
        response.hangup()
    return str(response)
