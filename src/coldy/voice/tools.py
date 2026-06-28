"""In-call tools the brain can invoke to take real actions mid-conversation.

These are defined in Anthropic tool-schema format and registered with the
Pipecat ``AnthropicLLMService`` via its function-calling interface. Each handler
runs against the database and updates the call/lead, then returns a short result
string the model speaks naturally.

The handlers are intentionally side-effecting but quick (light DB writes). The
opt-out tool is the most important one: it must reliably suppress the number.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..db.base import CallOutcome, LeadStatus
from ..db.session import session_scope
from ..logging import get_logger

log = get_logger("coldy.voice.tools")


# --- Tool schemas (Anthropic format) -------------------------------------

TOOL_SCHEMAS = [
    {
        "name": "book_meeting",
        "description": (
            "Book a discovery call with a human specialist. Call this when the "
            "lead agrees to a follow-up. Confirm the details back to them out loud."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_name": {"type": "string", "description": "The person's name"},
                "preferred_time": {
                    "type": "string",
                    "description": "Their preferred callback time, in their words",
                },
                "email": {"type": "string", "description": "Email, if they offer one"},
                "notes": {"type": "string", "description": "Anything useful for the specialist"},
            },
            "required": ["preferred_time"],
        },
    },
    {
        "name": "add_to_do_not_call",
        "description": (
            "MANDATORY when the person asks to stop being called / be removed / "
            "do not call. Immediately suppresses this number forever. After "
            "calling this, confirm warmly and end the call."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "What they said, briefly"}
            },
            "required": [],
        },
    },
    {
        "name": "transfer_to_human",
        "description": (
            "Warm-transfer the call to a human specialist right now. Use only "
            "when the lead explicitly wants to talk to a person immediately."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Why they want a human"}
            },
            "required": [],
        },
    },
    {
        "name": "schedule_callback",
        "description": (
            "Record that now is a bad time and capture when to call back. Use "
            "when they ask you to call later."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "when": {"type": "string", "description": "When to call back, in their words"}
            },
            "required": ["when"],
        },
    },
    {
        "name": "end_call",
        "description": (
            "End the call. ALWAYS call this when the conversation is over, with a "
            "short friendly sign-off and the final outcome."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "outcome": {
                    "type": "string",
                    "enum": [
                        "meeting_booked",
                        "interested",
                        "callback",
                        "not_interested",
                        "opted_out",
                        "transferred",
                        "wrong_number",
                    ],
                },
                "summary": {"type": "string", "description": "One-sentence summary of the call"},
            },
            "required": ["outcome"],
        },
    },
]


class CallActions:
    """Stateful handler bound to a single live call.

    Pass ``lead_id`` and ``call_id`` so handlers can update the right rows. The
    ``ended`` / ``transfer_requested`` flags let the pipeline react (hang up /
    dial the human).
    """

    def __init__(self, lead_id: int, call_id: int):
        self.lead_id = lead_id
        self.call_id = call_id
        self.ended = False
        self.transfer_requested = False
        self.final_outcome: CallOutcome = CallOutcome.UNKNOWN

    # Each method mirrors a tool name and returns a short string for the model.
    def book_meeting(self, preferred_time: str, contact_name: str = "",
                     email: str = "", notes: str = "") -> str:
        with session_scope() as s:
            from ..db.models import Call, Lead

            lead = s.get(Lead, self.lead_id)
            call = s.get(Call, self.call_id)
            if lead:
                lead.status = LeadStatus.INTERESTED
                if contact_name:
                    lead.contact_name = contact_name
            if call:
                call.outcome = CallOutcome.MEETING_BOOKED
                call.summary = (
                    f"Meeting booked. Time: {preferred_time}. "
                    f"Email: {email or 'n/a'}. Notes: {notes or 'n/a'}"
                )
        self.final_outcome = CallOutcome.MEETING_BOOKED
        log.info("Meeting booked for lead %s (%s)", self.lead_id, preferred_time)
        return f"Booked. Confirm with them: a specialist will call {preferred_time}."

    def add_to_do_not_call(self, reason: str = "") -> str:
        from ..compliance.dnc import add_to_dnc
        from ..db.models import Call, Lead

        with session_scope() as s:
            lead = s.get(Lead, self.lead_id)
            if lead:
                add_to_dnc(s, lead.phone, reason=reason or "requested on call", source="in_call")
            call = s.get(Call, self.call_id)
            if call:
                call.outcome = CallOutcome.OPTED_OUT
                call.summary = f"Opted out / DNC. {reason}".strip()
        self.final_outcome = CallOutcome.OPTED_OUT
        self.ended = True
        log.info("Lead %s opted out -> DNC", self.lead_id)
        return "Done — they're on the do-not-call list. Confirm warmly and end the call."

    def transfer_to_human(self, reason: str = "") -> str:
        self.transfer_requested = True
        self.final_outcome = CallOutcome.TRANSFERRED
        with session_scope() as s:
            from ..db.models import Call

            call = s.get(Call, self.call_id)
            if call:
                call.outcome = CallOutcome.TRANSFERRED
                call.summary = f"Transferred to human. {reason}".strip()
        log.info("Transfer requested for lead %s", self.lead_id)
        return "Tell them you're connecting them to a specialist now, then stop talking."

    def schedule_callback(self, when: str) -> str:
        from ..db.models import Call, Lead

        with session_scope() as s:
            lead = s.get(Lead, self.lead_id)
            if lead:
                lead.status = LeadStatus.CALLBACK
            call = s.get(Call, self.call_id)
            if call:
                call.outcome = CallOutcome.CALLBACK
                call.summary = f"Callback requested: {when}"
        self.final_outcome = CallOutcome.CALLBACK
        log.info("Callback scheduled for lead %s (%s)", self.lead_id, when)
        return f"Got it — confirm you'll call back {when}, then wrap up."

    def end_call(self, outcome: str = "unknown", summary: str = "") -> str:
        try:
            self.final_outcome = CallOutcome(outcome)
        except ValueError:
            self.final_outcome = CallOutcome.UNKNOWN
        with session_scope() as s:
            from ..db.models import Call

            call = s.get(Call, self.call_id)
            if call:
                call.outcome = self.final_outcome
                if summary:
                    call.summary = summary
        self.ended = True
        log.info("Call %s ended (%s)", self.call_id, outcome)
        return "Give a short friendly sign-off."

    def dispatch(self, name: str, arguments: dict) -> str:
        handler = getattr(self, name, None)
        if handler is None:
            return f"Unknown tool: {name}"
        try:
            return handler(**arguments)
        except TypeError as e:
            log.warning("Tool %s called with bad args %s: %s", name, arguments, e)
            return "Sorry, I couldn't do that — let's keep going."
