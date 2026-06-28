"""Twilio Programmable Voice webhooks.

  POST /twilio/voice   -> returns <Connect><Stream> TwiML bridging audio to /media
  POST /twilio/status  -> call lifecycle + AMD (answering-machine) updates
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Response
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from ...config import settings
from ...db.base import CallOutcome, CallStatus, LeadStatus
from ...db.models import Call, Lead
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
    call_status = _STATUS_MAP.get(twilio_status, CallStatus.IN_PROGRESS)
    is_machine = answered_by.startswith("machine")

    payload = await run_in_threadpool(
        _apply_status, call_id, call_status, is_machine, duration
    )

    # Push terminal outcomes to the CRM (best effort, off the request path).
    if payload is not None:
        from ...crm import CallOutcomePayload, get_default_sink

        sink = get_default_sink()
        if sink.enabled:
            await run_in_threadpool(sink.send, CallOutcomePayload(**payload))

    return Response(status_code=204)


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
