# Coldy

A **human-sounding, compliance-first AI cold-calling platform** for US service
businesses. Coldy places outbound calls, holds a natural spoken conversation
powered by Claude, qualifies the business, and books a discovery call — while
enforcing US calling law (TCPA, DNC, calling windows, AI disclosure) at every step.

Built for the use case: calling local service businesses (painters, HVAC,
plumbers, landscapers, cleaners) to introduce a marketing platform like
**[Oxsome](https://oxsome.com)** and book them a discovery call.

> ⚠️ **Read [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) before calling anyone.**
> In Feb 2024 the FCC ruled that **AI-generated voices are "artificial/prerecorded"
> under the TCPA**, so AI telemarketing calls generally require **prior express
> *written* consent**. Coldy enforces this by default. "Cold calling hundreds of
> strangers a day" with an AI voice is, for most B2C and many B2B cases, *not*
> legal without that consent. Coldy is built to keep you on the right side of the
> line — don't disable the guardrails without legal advice.

---

## How it sounds human

Human-ness on the phone is mostly **latency + turn-taking + spoken register**,
not raw model IQ. Coldy is engineered around that:

- **Sub-second responses** via fully streaming pipeline: streaming STT →
  token-streaming LLM → sentence-chunked streaming TTS (audio starts on the
  first sentence, not the whole reply).
- **Real interruptions / barge-in** via Silero VAD — talk over it and it stops,
  like a person.
- **Spoken-style persona** — short turns, contractions, one question at a time,
  no lists, numbers spoken out, light natural backchannels.
- **Best-in-class voice stack:** Deepgram (STT) + Cartesia Sonic (ultra-low-
  latency TTS) + Claude (brain), orchestrated by [Pipecat](https://pipecat.ai).

See [`docs/PLAYBOOK.md`](docs/PLAYBOOK.md) for the full "perfect cold call +
human-sounding AI" deep-dive.

## Finding prospects

A built-in **prospecting engine** finds the businesses Oxsome can help — via
official APIs (Google Places, Yelp), scoring each on *needs marketing help* (no
website, weak reviews) + *can afford it* (affluent ZIP, busy/established) — and
flags the best to you. It deliberately does **not** scrape Facebook/Nextdoor
(ToS + privacy + no consent); the compliant "intent" play is an ads → opt-in
funnel that also makes leads legally callable. Full detail + the hand-off to the
dialer: [`docs/PROSPECTING.md`](docs/PROSPECTING.md).

## Filling your call list legally (the opt-in funnel)

`coldy serve` hosts a **consent-capture landing page** at **`/optin`** — a blank
form (no numbers on it; each visitor enters their own). On submit it records
**prior express written consent** with evidence (exact wording shown, timestamp,
IP, user agent) and drops a **callable lead** into the opt-in campaign, already
eligible to dial. There's also a JSON intake at **`POST /api/optin`** for
integrations (Zapier/Make, Facebook Lead Ads via a connector).

This is the legal way to "find people who want help": run ads → `/optin` →
consented leads → the dialer can call them. Prospecting finds *who*; the opt-in
makes them *callable*.

## Architecture at a glance

```
 leads.csv ──> import ──> [ Leads DB ] <── consent / DNC
                              │
                     ┌────────▼─────────┐   compliance gate (TCPA/DNC/hours/consent)
                     │  Dialer worker   │──────────────┐
                     │ (pacing/retry)   │              ▼  blocked? defer/suppress
                     └────────┬─────────┘        [ ComplianceEngine ]
                              │ place_call (Twilio REST)
                              ▼
   Twilio ──webhook──> /twilio/voice  ──TwiML <Connect><Stream>──┐
   Twilio ──audio────────────────────> /media (websocket) ───────┤
                                                                  ▼
                                        Pipecat:  STT → Claude → TTS  (+ in-call tools)
                                                                  │
   Twilio ──status/AMD──> /twilio/status ──> outcomes ──> CRM webhook
```

Full detail in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Quick start (no real calls)

```bash
make dev            # pip install -e ".[dev]"
cp .env.example .env  # fill in keys later; the dry-run demo needs none
make demo           # init db, import sample leads, dry-run the dialer, show report
make test           # run the test suite
```

`make demo` runs the whole pipeline in **dry-run** mode (plans and logs calls,
places none) so you can see lead import, the compliance gate, pacing, and
reporting end-to-end without a Twilio account.

## Going live (real calls)

1. Get keys: **Anthropic**, **Deepgram**, **Cartesia**, **Twilio** (+ a phone number).
2. Fill `.env` (see `.env.example`) and expose this server publicly
   (e.g. `ngrok http 8000`) — set `COLDY_PUBLIC_BASE_URL` to the tunnel URL.
3. **Capture consent** for your leads and record it (`coldy consent add ...`).
4. Run it:

   ```bash
   coldy init
   coldy import your_leads.csv --campaign june_painters
   coldy serve          # terminal 1: webhook + media server
   coldy run -c june_painters   # terminal 2: the dialer
   coldy report -c june_painters
   ```

See [`docs/SETUP.md`](docs/SETUP.md) for local setup, and
**[`docs/DEPLOY.md`](docs/DEPLOY.md)** for the full **DigitalOcean** production
runbook (Droplet + Docker Compose + Caddy auto-HTTPS, Twilio config, go-live
checklist).

Production security is built in (set these in `.env`): Twilio webhook signature
validation, HTTP Basic auth on the dashboard, a token on the media-stream URL,
and an optional token on the opt-in API.

## CLI

| Command | What it does |
|---|---|
| `coldy init` | Create DB tables |
| `coldy prospect search -l "City, ST" -q painting [--source google\|yelp\|mock]` | Find + score + flag prospects |
| `coldy prospect list --flagged` / `coldy prospect export -o leads.csv` | Review / export flagged prospects |
| `coldy import FILE --campaign NAME` | Import leads (normalizes numbers, resolves tz/state) |
| `coldy consent add --phone … --source …` | Record prior express written consent |
| `coldy dnc add --phone …` | Suppress a number (internal DNC) |
| `coldy campaign create/start/pause NAME` | Manage a campaign |
| `coldy run --campaign NAME [--dry-run] [--once]` | Run the dialer (daemon, or one pass with `--once` for cron) |
| `coldy call --to +1… [--i-own-this-number]` | Place ONE real test call to hear the bot end-to-end |
| `coldy plan --campaign NAME` | Preview who'd be dialed right now (compliance-gated), no calls |
| `coldy check --phone …` | Preview the compliance decision for a number |
| `coldy persona` | Print the exact system prompt + a sample opening the bot uses |
| `coldy openers [--industry X]` | Preview the data-backed opener library, rendered |
| `coldy report --campaign NAME` | Campaign stats / outcomes / funnel / opener A/B |
| `coldy numbers [--to +1…]` | Show the caller-ID pool + local-presence selection |
| `coldy serve` | Run the webhook + media server (+ live dashboard at `/dashboard`) |
| `coldy doctor` | Verify configuration & credentials |

## Configuration

Everything is env-driven (`COLDY_*` prefix). The most important knobs:

- `COLDY_LLM_MODEL` — the conversational brain (fast model for the turn loop).
  `claude-haiku-4-5` (default), `claude-sonnet-4-6`, or `claude-opus-4-8`.
  `COLDY_LLM_ESCALATION_MODEL` is used for hard turns (objections/pricing — see
  `voice/brain.py`). The system prompt is **prompt-cached** across the campaign
  for lower latency + cost.
- `COLDY_OPENER_STYLE` — `rotate` (A/B) or a specific opener id (`coldy openers`).
- `COLDY_REQUIRE_WRITTEN_CONSENT` — **keep `true`** unless counsel says otherwise.
- `COLDY_CALL_WINDOW_START_HOUR` / `_END_HOUR` — local calling window (default 9–20).
- `COLDY_MAX_CONCURRENT_CALLS`, `COLDY_DIAL_INTERVAL_SECONDS` — pacing.
- `COLDY_VOICEMAIL_ENABLED`, `COLDY_SMS_ENABLED`, `COLDY_BOOKING_LINK` —
  multi-touch follow-up (voicemail drop on machine detection; consent-gated SMS).
- `COLDY_RECORD_CALLS` — enable recording (per-state notice auto-injected).
- `COLDY_FROM_NUMBERS`, `COLDY_PER_NUMBER_DAILY_CAP` — local-presence caller-ID
  pool + reputation caps (see `docs/DELIVERABILITY.md`).

`coldy report` (and the **live dashboard** at `/dashboard` while `coldy serve`
runs) show the **funnel** (dials → connected → conversations → meetings) and a
**per-opener A/B table** so you can see which opener books most. Getting calls
answered at all is covered in [`docs/DELIVERABILITY.md`](docs/DELIVERABILITY.md)
(local presence, STIR/SHAKEN, number reputation).

Full list in `.env.example`.

## Project layout

```
src/coldy/
  config.py          settings (env-driven)
  db/                SQLAlchemy models + session
  leads/             CSV import + repository
  compliance/        TCPA / DNC / hours / consent / recording / engine  ← the guardrails
  voice/             persona, humanizer, in-call tools, Pipecat bot      ← the human-ness
  telephony/         Twilio client + TwiML
  dialer/            campaign, scheduler, pacing worker
  crm/               outcome sinks (webhook adapter)
  api/               FastAPI: Twilio webhooks + media-stream websocket
  cli.py             the `coldy` command
docs/                ARCHITECTURE, COMPLIANCE, SETUP, PLAYBOOK
tests/               compliance / calling-hours / geo / persona
```

## Disclaimer

This is engineering scaffolding, **not legal advice**. Telemarketing law is
strict and the penalties are real (TCPA statutory damages are $500–$1,500 *per
call*). Have qualified counsel review your consent capture, scripts, and process
before dialing.
