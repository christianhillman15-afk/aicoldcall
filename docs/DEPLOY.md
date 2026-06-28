# Deploying Coldy to production (DigitalOcean)

This is the full runbook to take Coldy live on a single DigitalOcean Droplet
using Docker Compose + Caddy (automatic HTTPS). End state:

```
 Internet ──HTTPS/WSS──▶ Caddy (TLS) ──▶ api (coldy serve)
 Twilio   ──webhooks───▶                  dialer (coldy run)
                                          Postgres
```

> **Before you send a single real call, read [`COMPLIANCE.md`](COMPLIANCE.md).**
> US AI-voice telemarketing needs prior express **written** consent. Coldy
> enforces it; don't disable the guardrails. Have a TCPA attorney review your
> consent wording (the text in `/optin`) and process.

---

## 0. What you need (accounts + keys)

| Thing | For | Notes |
|---|---|---|
| **DigitalOcean** account | the server | |
| A **domain** (or subdomain) | TLS + Twilio webhooks | e.g. `calls.yourdomain.com` |
| **Twilio** account + **voice numbers** | telephony | buy local numbers; set up STIR/SHAKEN (below) |
| **Anthropic** API key | the brain | |
| **Deepgram** API key | speech-to-text | |
| **Cartesia** API key + voice id | text-to-speech | |
| (optional) **Google Places / Yelp / Census** keys | prospecting | |
| (optional) **Slack** incoming webhook | opt-in / prospect alerts | |

---

## 1. Create the Droplet

DigitalOcean → Create → Droplets:

- **Image:** Ubuntu 24.04 (or the "Docker on Ubuntu" Marketplace image to skip step 3a).
- **Size:** the media server runs a full speech pipeline per concurrent call.
  - Start: **2 vCPU / 4 GB** (`s-2vcpu-4gb`, ~$24/mo) — a few concurrent calls.
  - Scale: **4 vCPU / 8 GB** for ~10+ concurrent calls.
- **Region:** close to your callees (lower audio latency).
- Add your **SSH key**. Create.

Note the Droplet's public **IPv4**.

## 2. Point your domain at it

In your DNS provider, add an **A record**:

```
calls.yourdomain.com  →  <droplet IP>
```

Wait for it to resolve (`dig +short calls.yourdomain.com`). Caddy needs this to
issue the TLS cert.

## 3. Prepare the Droplet

SSH in: `ssh root@<droplet IP>`

**3a. Install Docker** (skip if you used the Docker Marketplace image):

```bash
curl -fsSL https://get.docker.com | sh
```

**3b. Get the code:**

```bash
git clone https://github.com/christianhillman15-afk/aicoldcall.git
cd aicoldcall
git checkout claude/humanlike-ai-cold-calling-jh8xsx   # until merged to main
```

## 4. Configure `.env`

```bash
cp .env.example .env
nano .env
```

Set at minimum:

```ini
COLDY_DOMAIN=calls.yourdomain.com
COLDY_PUBLIC_BASE_URL=https://calls.yourdomain.com

ANTHROPIC_API_KEY=sk-ant-...
DEEPGRAM_API_KEY=...
CARTESIA_API_KEY=...
COLDY_TTS_VOICE_ID=<a Cartesia voice id>

TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
COLDY_FROM_NUMBERS=+1...,+1...        # your purchased local numbers

# Security — set ALL of these for production:
COLDY_TWILIO_VALIDATE_SIGNATURES=true
COLDY_DASHBOARD_USER=admin
COLDY_DASHBOARD_PASSWORD=<long random>
COLDY_MEDIA_TOKEN=<long random>
COLDY_OPTIN_API_TOKEN=<long random>   # if you POST to /api/optin from Zapier etc.

# Postgres (compose reads these):
POSTGRES_USER=coldy
POSTGRES_PASSWORD=<long random>
POSTGRES_DB=coldy
CAMPAIGN=Web Opt-ins                  # which campaign the dialer works
```

Generate randoms with `openssl rand -hex 24`.

## 5. Launch

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

First build pulls the voice stack (a few minutes). Then:
- Caddy gets a TLS cert for your domain automatically.
- `api` starts and **creates the database tables on boot**.
- `dialer` starts and waits for eligible (consented) leads.

Check it:

```bash
docker compose -f docker-compose.prod.yml ps
curl https://calls.yourdomain.com/health        # {"status":"ok",...}
```

Open `https://calls.yourdomain.com/dashboard` (Basic auth) and
`https://calls.yourdomain.com/optin` (the public form).

## 6. Configure Twilio

1. **Buy local numbers** in your target area codes (Console → Phone Numbers).
   Put them in `COLDY_FROM_NUMBERS`.
2. **Inbound** (so it can answer callbacks): on each number's **Voice & Fax →
   "A call comes in"**, set a **Webhook (HTTP POST)** to
   `https://calls.yourdomain.com/twilio/inbound`.
3. **STIR/SHAKEN + branded caller ID** (so calls get answered, not flagged
   "Spam Likely"): set up a **Trust Hub** business profile and number
   registration. See [`DELIVERABILITY.md`](DELIVERABILITY.md). Budget a few days
   for verification.

Outbound webhooks are passed automatically per call — nothing else to configure.

## 7. Verify end-to-end (one real test call)

```bash
docker compose -f docker-compose.prod.yml exec api \
  coldy call --to "+1YOURCELL" --i-own-this-number
```

Your phone should ring and you'll hear the bot. (Uses a self-test consent for a
number you own.)

## 8. Go live

1. **Get consented leads** — point a Facebook/Nextdoor **ad** at
   `https://calls.yourdomain.com/optin?src=fb_painters`. Each opt-in becomes a
   callable lead in the `Web Opt-ins` campaign.
   - (Optional) Find target businesses to advertise toward with
     `coldy prospect search` (see [`PROSPECTING.md`](PROSPECTING.md)).
2. The **dialer** auto-calls eligible consented leads within calling hours.
3. Watch it on the **dashboard**; outcomes/transcripts are recorded; SMS/voicemail
   follow-up fires if enabled.

---

## Operations

```bash
# logs
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f dialer

# update to new code
git pull && docker compose -f docker-compose.prod.yml up -d --build

# run any CLI command
docker compose -f docker-compose.prod.yml exec api coldy report -c "Web Opt-ins"
docker compose -f docker-compose.prod.yml exec api coldy numbers

# back up the database
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U coldy coldy > backup-$(date +%F).sql
```

**Scaling:** for more concurrent calls, size up the Droplet (CPU is the limit —
each call runs a live speech pipeline). For real scale, split the media server
onto its own bigger box and/or use **DigitalOcean Managed Postgres** (point
`COLDY_DATABASE_URL` at it and drop the `db` service).

**Rough running costs:** Droplet ~$24–48/mo + per-minute usage (Twilio voice,
Deepgram, Cartesia, Anthropic) — typically a few cents to ~$0.10–0.20 per call
minute combined. Estimate before scaling volume.

## Production checklist

- [ ] Domain resolves; `https://…/health` returns ok (TLS valid).
- [ ] `COLDY_TWILIO_VALIDATE_SIGNATURES=true` and `TWILIO_AUTH_TOKEN` set.
- [ ] Dashboard Basic auth + `COLDY_MEDIA_TOKEN` + `COLDY_OPTIN_API_TOKEN` set.
- [ ] Local numbers in `COLDY_FROM_NUMBERS`; STIR/SHAKEN registered.
- [ ] Consent wording in `/optin` reviewed by a TCPA attorney.
- [ ] Federal DNC scrubbing wired (`set_federal_dnc_checker`) before scale.
- [ ] DB backups scheduled (cron the `pg_dump` above).
- [ ] Test call heard end-to-end; one opt-in → call verified.

## Notes / known follow-ups

- **Schema migrations:** the app bootstraps tables with `create_all` on first
  boot, which is fine for launch. For evolving the schema later without data
  loss, add Alembic (the models are standard SQLAlchemy).
- **One opt-in form is public by design** (it's a landing page). Add a CAPTCHA /
  rate limiting if you see spam submissions.
- **App Platform alternative:** DO App Platform can host this (web service +
  worker + managed DB), but the Droplet + Compose path above is the simplest for
  the media-stream websocket and the long-running dialer.
