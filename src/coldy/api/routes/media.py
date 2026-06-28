"""The Twilio Media Streams websocket endpoint.

Twilio connects here (via the <Connect><Stream> TwiML) and streams call audio.
We read the initial 'start' frame to learn the streamSid/callSid and our custom
parameters (call_id, lead_id), build the call context, and hand the socket to
the Pipecat bot which runs the conversation.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...config import settings
from ...db.models import Lead
from ...db.session import get_session
from ...logging import get_logger
from ...voice.bot import CallMeta, run_bot
from ...voice.persona import CallContext

log = get_logger("coldy.api.media")
router = APIRouter()


async def _read_start(ws: WebSocket) -> dict | None:
    """Consume Twilio's initial frames and return the 'start' payload."""
    while True:
        try:
            raw = await ws.receive_text()
        except WebSocketDisconnect:
            return None
        msg = json.loads(raw)
        event = msg.get("event")
        if event == "start":
            return msg
        # 'connected' and any pre-start frames are ignored.


def _load_context(lead_id: int) -> tuple[CallContext, str | None]:
    """Build the persona context from the lead row. Returns (ctx, call_sid_hint)."""
    session = get_session()
    try:
        lead = session.get(Lead, lead_id) if lead_id else None
        if lead is None:
            return CallContext(), None

        requires_notice = False
        if settings.record_calls:
            from ...compliance.recording import requires_all_party_consent

            requires_notice = requires_all_party_consent(lead.state)

        goal = lead.campaign.goal if lead.campaign else CallContext().campaign_goal
        ctx = CallContext(
            business_name=lead.business_name,
            contact_name=lead.contact_name,
            industry=lead.industry,
            city=lead.city,
            state=lead.state,
            campaign_goal=goal,
            requires_recording_notice=requires_notice,
        )
        return ctx, None
    finally:
        session.close()


@router.websocket("/media")
async def media(websocket: WebSocket) -> None:
    await websocket.accept()
    from ..security import media_token_ok

    if not media_token_ok(websocket.query_params.get("token")):
        log.warning("Media stream rejected: bad/missing token")
        await websocket.close(code=1008)
        return
    start = await _read_start(websocket)
    if start is None:
        log.warning("Media socket closed before 'start'")
        return

    start_data = start.get("start", {})
    stream_sid = start_data.get("streamSid") or start.get("streamSid", "")
    call_sid = start_data.get("callSid", "")
    params = start_data.get("customParameters", {}) or {}
    call_id = int(params.get("call_id", 0) or 0)
    lead_id = int(params.get("lead_id", 0) or 0)
    inbound = params.get("inbound") == "1"

    log.info(
        "Media stream start: call_sid=%s call_id=%s lead_id=%s inbound=%s",
        call_sid, call_id, lead_id, inbound,
    )

    ctx, _ = _load_context(lead_id)
    ctx.inbound = inbound
    meta = CallMeta(
        lead_id=lead_id,
        call_id=call_id,
        stream_sid=stream_sid,
        call_sid=call_sid,
        context=ctx,
    )

    async def _on_transfer() -> None:
        # Warm-transfer the live call to a human by redirecting it via Twilio.
        from ...telephony import TwilioTelephony

        if call_sid:
            tel = TwilioTelephony()
            tel.redirect_to_human(call_sid)

    try:
        await run_bot(websocket, meta, on_transfer=_on_transfer)
    except WebSocketDisconnect:
        log.info("Media stream disconnected for call_id=%s", call_id)
    except Exception as e:  # noqa: BLE001
        log.exception("Bot crashed for call_id=%s: %s", call_id, e)
