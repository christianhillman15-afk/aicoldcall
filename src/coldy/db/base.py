"""SQLAlchemy declarative base + shared enums."""

from __future__ import annotations

import enum

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class LeadStatus(str, enum.Enum):
    NEW = "new"                      # imported, not yet queued
    QUEUED = "queued"                # eligible and waiting to be dialed
    CALLING = "calling"             # a call is in progress right now
    CALLBACK = "callback"           # caller asked to be called back later
    INTERESTED = "interested"       # qualified / meeting booked
    NOT_INTERESTED = "not_interested"
    DNC = "dnc"                      # do-not-call: never dial again
    FAILED = "failed"               # transient failure, may retry
    EXHAUSTED = "exhausted"         # hit max attempts
    INVALID = "invalid"             # bad / unreachable number


class CallStatus(str, enum.Enum):
    INITIATED = "initiated"
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    FAILED = "failed"
    VOICEMAIL = "voicemail"          # answering-machine detected
    CANCELED = "canceled"


class CallOutcome(str, enum.Enum):
    UNKNOWN = "unknown"
    MEETING_BOOKED = "meeting_booked"
    INTERESTED = "interested"
    CALLBACK = "callback"
    NOT_INTERESTED = "not_interested"
    OPTED_OUT = "opted_out"          # asked to be put on DNC
    TRANSFERRED = "transferred"      # warm-transferred to a human
    VOICEMAIL = "voicemail"
    NO_ANSWER = "no_answer"
    WRONG_NUMBER = "wrong_number"


class ConsentType(str, enum.Enum):
    # Prior express WRITTEN consent — required for AI/artificial-voice
    # telemarketing under the FCC's 2024 TCPA ruling.
    EXPRESS_WRITTEN = "express_written"
    # Prior express (non-written) consent — insufficient for telemarketing.
    EXPRESS = "express"
    # An established business relationship (narrow; not a telemarketing pass).
    EBR = "established_business_relationship"


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
