# Architecture

Coldy has two runtime processes and one shared database:

1. **API / media server** (`coldy serve`) — FastAPI. Serves Twilio webhooks and
   the media-stream websocket where each conversation runs.
2. **Dialer worker** (`coldy run`) — an async pacing loop that decides who to
   call and places calls. It does **not** run conversations.

They communicate only through the database, so you can run several dialer
workers (one per campaign) and scale the API independently.

## The call lifecycle

```
1. coldy run  ── worker tick ──────────────────────────────────────────────
   - count in-flight calls -> free_slots
   - plan_next_dials(): pull candidate leads, run ComplianceEngine on each
   - for each cleared lead: create Call row, mark CALLING, Twilio.place_call()
   - defer time-blocked leads; suppress DNC/exhausted leads
        │
        ▼  Twilio places the call
2. Callee answers ─> Twilio fetches  POST /twilio/voice
   - returns <Connect><Stream url="wss://.../media"> with call_id/lead_id params
        │
        ▼  Twilio opens the media-stream websocket
3. POST(ws) /media
   - read Twilio 'start' frame -> streamSid, callSid, custom params
   - load lead -> build CallContext (business, industry, recording posture)
   - run_bot():  Pipecat pipeline runs the conversation
        transport.input -> Deepgram STT -> user aggregator
          -> Claude (AnthropicLLMService, streaming + tools)
          -> Cartesia TTS -> transport.output -> assistant aggregator
   - opening line (AI disclosure) is spoken verbatim, then Claude drives
   - in-call tools: book_meeting / schedule_callback / transfer_to_human /
     add_to_do_not_call / end_call  -> update Call + Lead in DB
        │
        ▼  call ends (EndFrame / hangup / transfer)
4. Twilio sends  POST /twilio/status  (status + AnsweredBy/AMD)
   - update Call (status, duration), reconcile Lead state machine
   - push the outcome to your CRM webhook
```

## Why these components

| Concern | Choice | Why |
|---|---|---|
| Orchestration | **Pipecat** | Purpose-built real-time voice framework; first-class Twilio Media Streams, VAD, interruptions, streaming everything. |
| STT | **Deepgram** (`nova-3`) | Streaming, low-latency, strong on telephony 8kHz audio. |
| TTS | **Cartesia Sonic** | Among the lowest time-to-first-byte; natural prosody — the single biggest "human" lever. |
| Brain | **Claude** | Excellent instruction-following for the spoken persona + reliable tool use for in-call actions. Model is configurable for the latency/IQ tradeoff. |
| Telephony | **Twilio** | Mature Programmable Voice, Media Streams, AMD, status callbacks. Swap-able (Telnyx) behind `telephony/`. |
| DB | **SQLAlchemy** (SQLite dev / Postgres prod) | Simple, portable. |

## The latency budget (why it sounds human)

Target round-trip (human stops talking → agent starts talking) is **< 800 ms**.
The pipeline hits it by never waiting for a whole step to finish:

- Deepgram emits interim + final transcripts as the person speaks.
- Claude streams tokens; Pipecat chunks them into sentences.
- Cartesia begins synthesizing the first sentence while Claude is still writing.
- Silero VAD detects end-of-speech in ~0.6 s and triggers the turn.

Tuning knobs live in `voice/humanizer.py`.

## Model choice (latency vs intelligence)

The brain is `COLDY_LLM_MODEL`. For a live phone call, the dominant driver of
"human" is latency, so the default is `claude-haiku-4-5` (fastest). For tougher
objection handling, switch to `claude-sonnet-4-6`, or `claude-opus-4-8` with
`COLDY_LLM_FAST_MODE=true` (Opus 4.8 Fast Mode runs the same model ~2.5× faster
at premium price). **Two-tier escalation is live**: a `ModelEscalator` processor
(`voice/bot.py`, driven by `voice/brain.py`) watches each user turn and, on a
hard turn (objection/pricing/trust — `COLDY_LLM_ESCALATION_MODEL`), pushes an
`LLMUpdateSettingsFrame` so that turn is answered by the smarter model, then
drops back to the fast model. Fast by default, smart when it matters.

**Inbound calls** are live too: point a Twilio number's Voice webhook at
`/twilio/inbound`. Coldy matches the caller to a lead (or creates one in an
"Inbound" campaign), greets them (disclosing AI), and runs the same
discovery/objection/booking playbook in inbound mode.

Prompt caching of the (large, stable) system prompt is **enabled**: it cuts
both latency and cost across the many calls in a campaign.

## Extending it

- **New CRM:** implement `crm.base.CRMSink` and wire it in `crm/__init__`.
- **New telephony provider:** implement the `TwilioTelephony` surface
  (`place_call`, `redirect_to_human`, `hangup`) and the media transport.
- **Federal DNC scrubbing:** call `compliance.dnc.set_federal_dnc_checker(fn)`
  with your licensed registry provider at startup.
- **Local presence:** rotate `COLDY_TWILIO_FROM_NUMBER` from a pool matched to
  the lead's area code (see `docs/PLAYBOOK.md` on deliverability).
