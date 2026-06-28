# Setup

## 0. Prerequisites

- Python 3.11+
- Accounts/keys: **Anthropic**, **Deepgram**, **Cartesia**, **Twilio** (with a
  voice-capable phone number).
- A way to expose your local server to Twilio: `ngrok`, `cloudflared`, or a
  deployed host with a public HTTPS URL.

## 1. Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # dev extras for tests; drop [dev] for prod
```

The Pipecat extras pull in a sizable audio/ML stack (Silero VAD via onnxruntime,
provider SDKs). First install can take a few minutes.

## 2. Try it with zero accounts (dry run)

```bash
make demo
```

This initializes the DB, imports `data/sample_leads.csv`, runs the dialer in
`--dry-run` mode (logs what it *would* dial, places no calls), and prints a
report. Great for understanding the flow and the compliance gate.

```bash
coldy check --phone "+16125550142"   # see why a number is/can't be called
coldy persona                        # see the exact words the bot will use
```

## 3. Configure for real calls

```bash
cp .env.example .env
```

Fill in:

- `COLDY_PUBLIC_BASE_URL` — your public tunnel/host, e.g.
  `https://abc123.ngrok.app`. Twilio reaches your webhooks here, and Twilio
  streams audio to its `wss://` equivalent automatically.
- `ANTHROPIC_API_KEY`, `DEEPGRAM_API_KEY`, `CARTESIA_API_KEY`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `COLDY_TWILIO_FROM_NUMBER`
- Pick `COLDY_TTS_VOICE_ID` (a Cartesia voice) and `COLDY_LLM_MODEL`.

Verify:

```bash
coldy doctor
```

## 4. Expose the server

```bash
ngrok http 8000      # copy the https URL into COLDY_PUBLIC_BASE_URL in .env
coldy serve          # terminal 1
```

You do **not** need to configure anything in the Twilio console for outbound
calls — Coldy passes the webhook URL on each call programmatically.

### Hear it end-to-end (one test call)

With `coldy serve` running and `.env` filled in, place a single call to a number
you own:

```bash
coldy call --to "+1YOURCELL" --i-own-this-number
```

`--i-own-this-number` records a self-test consent so the compliance gate passes
(only valid for numbers you actually control). You'll hear the opener, talk to
it, and the outcome/transcript will be saved. `coldy doctor` checks your keys
first.

### Inbound calls (answer + qualify callbacks)

To let Coldy *answer* calls too, point your Twilio number's Voice webhook at:

```
https://<your COLDY_PUBLIC_BASE_URL>/twilio/inbound   (HTTP POST)
```

On an inbound call Coldy matches the caller to a lead (or creates one in an
"Inbound" campaign), greets them warmly (disclosing it's an AI), and runs the
same discovery/objection/booking playbook — then can transfer to a human.

## 5. Load leads + consent

CSV columns (only `phone` required): `phone, business_name, contact_name,
industry, city, state, notes`.

```bash
coldy import your_leads.csv --campaign june_painters
```

**Record consent** (required by default — see `docs/COMPLIANCE.md`). Consent must
be captured *before* you load leads into a dialing campaign — e.g. a checkbox on
a web form where the business agreed to be contacted by automated/AI calls:

```bash
coldy consent add --phone "+16125550142" --source "website form 2026-06-01" \
  --evidence-url "https://crm/contact/123/consent"
```

Without written consent on file, the compliance engine blocks the call (by
design). Set `COLDY_REQUIRE_WRITTEN_CONSENT=false` only on advice of counsel for
a documented exemption.

## 6. Dial

```bash
coldy campaign start june_painters
coldy run --campaign june_painters       # terminal 2
coldy report --campaign june_painters
```

Outcomes flow to `COLDY_CRM_WEBHOOK_URL` if set (HMAC-signed when a secret is
configured).

## 7. Production notes

- Use Postgres (`COLDY_DATABASE_URL=postgresql+psycopg://…`) and run via
  `docker compose up` (API + dialer + db).
- Replace `Base.metadata.create_all` with Alembic migrations.
- Wire a federal DNC registry checker (`set_federal_dnc_checker`) before scale.
- Rotate caller IDs / warm your numbers (see `docs/PLAYBOOK.md` → deliverability).
- Turn on recording only after configuring per-state notice
  (`COLDY_RECORD_CALLS=true`); Coldy injects a recording notice where required.
- **Schema note:** the dev DB is created with `create_all` (no migrations). After
  pulling schema changes (e.g. the new `opener_id`/`qualification` call columns),
  recreate the dev DB (`make clean && coldy init`) or add an Alembic migration
  for Postgres.
- **Multi-touch:** set `COLDY_SMS_ENABLED=true` + `COLDY_BOOKING_LINK` to text
  interested leads a booking link (SMS is consent-gated). Set
  `COLDY_VOICEMAIL_ENABLED=true` to drop a short compliant voicemail when an
  answering machine is detected.
