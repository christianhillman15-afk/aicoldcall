"""The dialer worker: an async pacing loop that places outbound calls.

It does NOT run conversations — those run in the API's media-stream websocket
handler when Twilio connects each call. The worker's job is purely to keep the
right number of compliant calls in flight, paced to avoid spam labeling.

Loop, each tick:
  1. count in-flight calls -> free_slots = max_concurrent - in_flight
  2. plan_next_dials() -> compliance-cleared leads (+ deferrals/blocks)
  3. place each cleared call (paced by dial_interval), record a Call row
  4. apply deferrals (next_eligible_at) and hard blocks (DNC/EXHAUSTED)
  5. sleep, repeat — finish when nothing is dialable and nothing is in flight
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import func, select

from ..config import settings
from ..db.base import CallStatus, CampaignStatus, LeadStatus
from ..db.models import Call, Campaign, Lead
from ..db.session import session_scope
from ..logging import get_logger
from ..leads.repository import LeadRepository
from .scheduler import plan_next_dials

log = get_logger("coldy.dialer.worker")

_IN_FLIGHT = (CallStatus.INITIATED, CallStatus.RINGING, CallStatus.IN_PROGRESS)


class DialerWorker:
    def __init__(self, campaign_name: str, telephony=None, dry_run: bool = False):
        self.campaign_name = campaign_name
        self.dry_run = dry_run
        self._stop = asyncio.Event()
        from ..telephony.number_pool import NumberPool

        self.pool = NumberPool()  # local-presence caller-ID selection
        if telephony is not None:
            self.telephony = telephony
        elif dry_run:
            self.telephony = None
        else:
            from ..telephony import TwilioTelephony

            self.telephony = TwilioTelephony()

    def stop(self) -> None:
        self._stop.set()

    async def run(self, max_idle_ticks: int = 5, once: bool = False) -> None:
        log.info(
            "Dialer starting for campaign '%s' (dry_run=%s, once=%s)",
            self.campaign_name, self.dry_run, once,
        )
        idle_ticks = 0
        while not self._stop.is_set():
            placed, in_flight, remaining = await asyncio.to_thread(self._tick)
            if once:
                log.info(
                    "Single pass for '%s': placed=%d in_flight=%d remaining=%d",
                    self.campaign_name, placed, in_flight, remaining,
                )
                break
            if placed == 0 and in_flight == 0 and remaining == 0:
                idle_ticks += 1
                if idle_ticks >= max_idle_ticks:
                    log.info("No work left for '%s'; finishing.", self.campaign_name)
                    await asyncio.to_thread(self._complete_campaign)
                    break
            else:
                idle_ticks = 0
            await asyncio.sleep(settings.dial_interval_seconds)
        log.info("Dialer stopped for campaign '%s'", self.campaign_name)

    # --- synchronous DB-bound step (run in a thread) -----------------------
    def _tick(self) -> tuple[int, int, int]:
        """Returns (calls_placed, in_flight, remaining_dialable)."""
        with session_scope() as session:
            camp = session.execute(
                select(Campaign).where(Campaign.name == self.campaign_name)
            ).scalar_one_or_none()
            if camp is None or camp.status != CampaignStatus.RUNNING:
                return (0, 0, 0)

            in_flight = session.execute(
                select(func.count())
                .select_from(Call)
                .where(Call.campaign_id == camp.id, Call.status.in_(_IN_FLIGHT))
            ).scalar_one()

            free_slots = max(0, settings.max_concurrent_calls - in_flight)
            plan = plan_next_dials(session, camp.id, free_slots=free_slots)

            repo = LeadRepository(session)
            placed = 0
            for lead in plan.to_dial:
                # Local-presence caller ID: pick the best from-number for this lead.
                from_number = self.pool.pick(session, lead.phone) or settings.twilio_from_number
                call = Call(
                    lead_id=lead.id,
                    campaign_id=camp.id,
                    to_number=lead.phone,
                    from_number=from_number,
                    status=CallStatus.INITIATED,
                )
                session.add(call)
                session.flush()  # assign call.id
                repo.mark_calling(lead)

                if self.dry_run or self.telephony is None:
                    log.info("[dry-run] would call %s from %s (lead %s, call %s)",
                             lead.phone, from_number, lead.id, call.id)
                    # No real call -> no status callback will complete it, so
                    # mark it done now to keep the in-flight count accurate.
                    call.status = CallStatus.COMPLETED
                else:
                    try:
                        sid = self.telephony.place_call(
                            to_number=lead.phone, call_id=call.id, lead_id=lead.id,
                            from_number=from_number,
                        )
                        call.provider_call_sid = sid
                    except Exception as e:  # noqa: BLE001
                        log.error("Failed to place call to %s: %s", lead.phone, e)
                        call.status = CallStatus.FAILED
                        lead.status = LeadStatus.FAILED
                placed += 1

            # Apply deferrals (out-of-window / retry spacing).
            for lead, until, reason in plan.deferred:
                repo.defer(lead, until)
                log.debug("Deferred lead %s until %s (%s)", lead.id, until, reason)

            # Apply hard blocks.
            for lead, reason in plan.blocked:
                if "DNC" in reason or "do-not-call" in reason:
                    lead.status = LeadStatus.DNC
                elif "max attempts" in reason:
                    lead.status = LeadStatus.EXHAUSTED
                log.debug("Blocked lead %s (%s)", lead.id, reason)

            # "Remaining work" = leads compliance would dial now PLUS leads
            # deferred to a future window/retry (they auto-resolve when time
            # comes). Hard-blocked leads (no consent, DNC, exhausted) are NOT
            # remaining work, so an all-blocked campaign finishes instead of
            # looping forever, while a campaign waiting on the morning window
            # keeps the daemon alive.
            now = datetime.now(timezone.utc)
            active = [LeadStatus.NEW, LeadStatus.QUEUED, LeadStatus.CALLBACK, LeadStatus.FAILED]
            future_deferred = session.execute(
                select(func.count())
                .select_from(Lead)
                .where(
                    Lead.campaign_id == camp.id,
                    Lead.do_not_call.is_(False),
                    Lead.status.in_(active),
                    Lead.next_eligible_at.is_not(None),
                    Lead.next_eligible_at > now,
                )
            ).scalar_one()
            followup = plan_next_dials(
                session, camp.id, free_slots=max(1, settings.max_concurrent_calls)
            )
            remaining = future_deferred + len(followup.to_dial)
            return (placed, in_flight, remaining)

    def _complete_campaign(self) -> None:
        with session_scope() as session:
            camp = session.execute(
                select(Campaign).where(Campaign.name == self.campaign_name)
            ).scalar_one_or_none()
            if camp and camp.status == CampaignStatus.RUNNING:
                camp.status = CampaignStatus.COMPLETED
