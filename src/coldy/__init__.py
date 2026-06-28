"""Coldy — a human-sounding, compliance-first AI cold-calling platform.

Package layout:
    config       application settings (env-driven)
    db           SQLAlchemy models + session
    leads        lead import + persistence
    compliance   TCPA / DNC / calling-hours / consent / recording guardrails
    voice        the real-time Pipecat voice agent (STT -> Claude -> TTS)
    telephony    Twilio outbound calling + TwiML
    dialer       campaign pacing, concurrency, retry scheduling
    crm          outcome sinks (webhook adapter, base interface)
    api          FastAPI app: Twilio webhooks + media-stream websocket
    cli          `coldy` command-line entrypoint
"""

__version__ = "0.1.0"
