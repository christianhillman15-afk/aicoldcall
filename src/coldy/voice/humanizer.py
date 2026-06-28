"""Human-ness tuning knobs for the voice pipeline.

These constants control turn-taking feel — the single biggest driver of whether
a call sounds human. They're isolated here so you can tune by ear without
touching pipeline wiring.

Latency budget (round-trip, human stops talking -> agent starts talking):
    < 800ms  feels natural
    ~1s      acceptable
    > 1.5s   noticeably robotic
The pipeline minimizes this via: streaming STT, token-streaming LLM, and
sentence-chunked streaming TTS, so audio starts on the first sentence rather
than waiting for the full response.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TurnTakingConfig:
    # Silero VAD: how long the human must be silent before we consider their
    # turn finished. Lower = snappier but more likely to cut them off; higher =
    # more patient but adds latency. 0.5–0.8s is a good phone range.
    vad_stop_secs: float = 0.6
    # Minimum speech duration to count as a real utterance (filters coughs/clicks).
    vad_start_secs: float = 0.2
    # Allow the human to barge in over the agent (essential for natural feel).
    allow_interruptions: bool = True
    # Audio sample rate for telephony (Twilio Media Streams is 8kHz mu-law).
    sample_rate: int = 8000


TURN_TAKING = TurnTakingConfig()


# Short backchannels the model is encouraged to use (see persona). Listed here
# for reference / future use (e.g. injecting an immediate "mhm" while the LLM
# thinks, to mask latency).
BACKCHANNELS = ("mm-hmm", "yeah", "right", "gotcha", "for sure", "totally")
