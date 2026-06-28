"""Twilio Programmable Voice webhooks.

  POST /twilio/voice    -> returns <Connect><Stream> TwiML bridging audio to /media
  POST /twilio/inbound  -> inbound calls: register + bridge to the bot
  POST /twilio/status   -> call lifecycle + AMD (answering-machine) updates
  POST /twilio/recording-> capture the recording URL
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Response
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from ...config import settings
from ...db.base import CallStatus, CallOutcome, LeadStatus
from ...db.models import Call, Campaign, Lead
from ...db.session import session_scope
from ...logging import get_logger
from ...telephony.twiml import connect_stream_twiml

log = get_logger("coldy.api.twilio")
router = APIRouter(prefix="/twilio")


@router.post("/voice")
async def voice(request: Request, call_id: int, lead_id: int) -> Response:
    """Twilio fetches this when the callee answers; we return streaming TwiML."""
    ws_url = f"{settings.websocket_base_url.rstrip('/')}/media"
    twiml = connect_stream_twiml(ws_url, call_id=call_id, lead_id=lead_id)
    log.info("Returning <Connect><Stream> TwiML for call_id=%s", call_id)
    return Response(content=twiml, media_type="application/xml")


@router.post("/inbound")
async def inbound(request: Request) -> Response:
    """Inbound calls (callbacks). Configure this as your Twilio number's Voice
    webhook. We register the call, match/create the lead, and bridge to the bot
    in inbound mode (it greets warmly instead of cold-opening)."""
    form = await request.form()
    from_number = form.get("From") or ""
    to_number = form.get("To") or ""
    call_sid = form.get("CallSid") or ""
    call_id, lead_id = await run_in_threadpool(
        _register_inbound, from_number, to_number, call_sid
    )
    ws_url = f"{settings.websocket_base_url.rstrip('/')}/media"
    twiml = connect_stream_twiml(ws_url, call_id=call_id, lead_id=lead_id, inbound=True)
    log.info("Inbound call from %s -> call_id=%s lead_id=%s", from_number, call_id, lead_id)
    return Response(content=twiml, media_type="application/xml")


_STATUS_MAP = {
    "queued": CallStatus.INITIATED,
    "initiated": CallStatus.INITIATED,
    "ringing": CallStatus.RINGING,
    "in-progress": CallStatus.IN_PROGRESS,
    "completed": CallStatus.COMPLETED,
    "busy": CallStatus.BUSY,
    "no-answer": CallStatus.NO_ANSWER,
    "failed": CallStatus.FAILED,
    "canceled": CallStatus.CANCELED,
}


@router.post("/status")
async def status(request: Request, call_id: int) -> Response:
    form = await request.form()
    twilio_status = (form.get("CallStatus") or "").lower()
    answered_by = (form.get("AnsweredBy") or "").lower()  # AMD result, if any
    duration = form.get("CallDuration")
    call_sid = form.get("CallSid") or ""
    call_status = _STATUS_MAP.get(twilio_status, CallStatus.IN_PROGRESS)
    is_machine = answered_by.startswith("machine")

    # Machine detected -> leave a short compliant voicemail (if enabled) by
    # redirecting the still-live call before it pitches an answering machine.
    if is_machine and settings.voicemail_enabled and call_sid:
        vm_text = await run_in_threadpool(_voicemail_text, call_id)
        if vm_text:
            await run_in_threadpool(_telephony().leave_voicemail, call_sid, vm_text)

    payload = await run_in_threadpool(
        _apply_status, call_id, call_status, is_machine, duration
    )

    if payload is not None:
        # Push the outcome to the CRM (best effort, off the request path).
        from ...crm import CallOutcomePayload, get_default_sink

        sink = get_default_sink()
        if sink.enabled:
            await run_in_threadpool(sink.send, CallOutcomePayload(**payload))

        # Multi-touch SMS follow-up (consent-gated inside _send_followup).
        if settings.sms_enabled:
            await run_in_threadpool(_send_followup, call_id)

    return Response(status_code=204)


@router.post("/recording")
async def recording(request: Request, call_id: int) -> Response:
    """Capture the recording URL once Twilio finishes recording the call."""
    form = await request.form()
    url = form.get("RecordingUrl")
    if url:
        await run_in_threadpool(_save_recording_url, call_id, url)
    return Response(status_code=204)


# --- helpers (run in threadpool) ---------------------------------------------

_telephony_singleton = None


def _telephony():
    global _telephony_singleton
    if _telephony_singleton is None:
        from ...telephony import TwilioTelephony

        _telephony_singleton = TwilioTelephony()
    return _telephony_singleton


def _voicemail_text(call_id: int) -> str | None:
    from ...voice.persona import CallContext, build_voicemail

    with session_scope() as session:
        call = session.get(Call, call_id)
        if call is None:
            return None
        lead = session.get(Lead, call.lead_id)
        ctx = CallContext(industry=lead.industry if lead else None)
        return build_voicemail(ctx)


def _send_followup(call_id: int) -> None:
    from ...followup import send_followup

    with session_scope() as session:
        call = session.get(Call, call_id)
        if call is not None:
            send_followup(_telephony(), session, call)


def _save_recording_url(call_id: int, url: str) -> None:
    with session_scope() as session:
        call = session.get(Call, call_id)
        if call is not None:
            call.recording_url = url
            call.recorded = True


def _register_inbound(from_number: str, to_number: str, call_sid: str) -> tuple[int, int]:
    """Match the caller to an existing lead (or create one in the Inbound
    campaign) and open an inbound Call row. Returns (call_id, lead_id)."""
    from ...compliance.geo import (
        is_mobile,
        normalize_e164,
        state_for_number,
        timezone_for_number,
    )

    e164 = normalize_e164(from_number) or from_number
    with session_scope() as session:
        lead = session.execute(select(Lead).where(Lead.phone == e164)).scalars().first()
        if lead is None:
            camp = session.execute(
                select(Campaign).where(Campaign.name == "Inbound")
            ).scalar_one_or_none()
            if camp is None:
                camp = Campaign(
                    name="Inbound",
                    goal="Help the caller, answer questions, and book a discovery call or transfer to a human.",
                )
                session.add(camp)
                session.flush()
            lead = Lead(
                campaign_id=camp.id,
                phone=e164,
                status=LeadStatus.NEW,
                state=state_for_number(e164),
                timezone=timezone_for_number(e164),
                is_mobile=is_mobile(e164),
            )
            session.add(lead)
            session.flush()
        call = Call(
            lead_id=lead.id,
            campaign_id=lead.campaign_id,
            direction="inbound",
            provider_call_sid=call_sid,
            from_number=e164,
            to_number=to_number,
            status=CallStatus.IN_PROGRESS,
        )
        session.add(call)
        session.flush()
        return call.id, lead.id


def _apply_status(
    call_id: int, call_status: CallStatus, is_machine: bool, duration: str | None
) -> dict | None:
    """Update Call + Lead from a status callback. Returns a CRM payload on
    terminal states, else None."""
    with session_scope() as session:
        call = session.get(Call, call_id)
        if call is None:
            return None
        lead = session.get(Lead, call.lead_id)

        if is_machine and call.outcome == CallOutcome.UNKNOWN:
            call.outcome = CallOutcome.VOICEMAIL
            call.status = CallStatus.VOICEMAIL
        else:
            call.status = call_status

        terminal = call_status in (
            CallStatus.COMPLETED, CallStatus.BUSY, CallStatus.NO_ANSWER,
            CallStatus.FAILED, CallStatus.CANCELED,
        )
        if not terminal and not is_machine:
            return None

        if duration:
            try:
                call.duration_seconds = int(duration)
            except ValueError:
                pass
        call.ended_at = datetime.now(timezone.utc)

        if lead is not None:
            _reconcile_lead(lead, call)

        return {
            "call_id": call.id,
            "lead_id": call.lead_id,
            "campaign": lead.campaign.name if lead and lead.campaign else None,
            "phone": call.to_number,
            "business_name": lead.business_name if lead else None,
            "contact_name": lead.contact_name if lead else None,
            "outcome": call.outcome.value,
            "summary": call.summary,
            "duration_seconds": call.duration_seconds,
        }


def _reconcile_lead(lead: Lead, call: Call) -> None:
    """Move the lead to its next state based on the call outcome."""
    outcome = call.outcome
    if outcome == CallOutcome.MEETING_BOOKED or outcome == CallOutcome.INTERESTED:
        lead.status = LeadStatus.INTERESTED
    elif outcome == CallOutcome.OPTED_OUT:
        lead.status = LeadStatus.DNC
        lead.do_not_call = True
    elif outcome == CallOutcome.CALLBACK:
        lead.status = LeadStatus.CALLBACK
    elif outcome == CallOutcome.NOT_INTERESTED:
        lead.status = LeadStatus.NOT_INTERESTED
    elif outcome in (CallOutcome.VOICEMAIL, CallOutcome.NO_ANSWER, CallOutcome.UNKNOWN):
        # Reschedule a retry, unless attempts are exhausted.
        if lead.attempts >= settings.max_attempts:
            lead.status = LeadStatus.EXHAUSTED
        else:
            lead.status = LeadStatus.QUEUED
            lead.next_eligible_at = datetime.now(timezone.utc) + timedelta(
                hours=settings.retry_interval_hours
            )
