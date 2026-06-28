"""Application settings, loaded from environment / .env.

Everything tunable lives here so the rest of the codebase never reads
``os.environ`` directly. Import the singleton ``settings``.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COLDY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Server ---
    public_base_url: str = "http://localhost:8000"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # --- Database ---
    database_url: str = "sqlite:///./coldy.db"

    # --- Anthropic brain ---
    # Note: ANTHROPIC_API_KEY (no COLDY_ prefix) is read by the Anthropic SDK.
    llm_model: str = "claude-haiku-4-5"
    llm_escalation_model: str = "claude-opus-4-8"
    llm_fast_mode: bool = False
    llm_max_tokens: int = 300  # spoken turns are short; keeps latency low

    # --- Deepgram STT ---
    stt_model: str = "nova-3"

    # --- Cartesia TTS ---
    tts_voice_id: str = "71a7ad14-091c-4e8e-a314-022ece01c121"

    # --- Twilio ---
    twilio_from_number: str = ""
    transfer_number: str = ""

    # --- Brand / persona ---
    company_name: str = "Launch Media"
    agent_name: str = "Avery"
    product_name: str = "Oxsome"
    product_pitch: str = (
        "an AI marketing platform that builds your website, runs your SEO and "
        "Google Ads, and handles your social media from one dashboard"
    )
    # Short, spoken outcome used in openers ("...help you {value_prop_short}").
    value_prop_short: str = "get more booked jobs from your website and Google"

    # --- Opener selection (the first 5-10 seconds) ---
    # An opener id from voice/openers.py, or "rotate"/"auto" to A-B at random.
    opener_style: str = "rotate"
    # The oddly-specific number used in permission openers ("twenty ... seconds").
    opener_ask_seconds: int = 27

    # --- Voicemail (compliant artificial-voice message when AMD finds a machine) ---
    voicemail_enabled: bool = False

    # --- SMS follow-up (TCPA: texting also requires consent — gated on it) ---
    sms_enabled: bool = False
    booking_link: str = ""  # sent to interested leads, e.g. a Calendly URL

    # --- Compliance ---
    require_written_consent: bool = True
    call_window_start_hour: int = 9
    call_window_end_hour: int = 20
    max_attempts: int = 3
    retry_interval_hours: int = 24
    record_calls: bool = False

    # --- Dialer pacing ---
    max_concurrent_calls: int = 5
    dial_interval_seconds: int = 8

    # --- CRM webhook ---
    crm_webhook_url: str = ""
    crm_webhook_secret: str = ""

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def websocket_base_url(self) -> str:
        """The wss:// origin Twilio should stream media to."""
        return self.public_base_url.replace("https://", "wss://").replace(
            "http://", "ws://"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
