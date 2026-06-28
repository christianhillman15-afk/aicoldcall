# Deliverability — getting calls answered

The best bot in the world books nothing if nobody picks up. Answer rates are
driven by three things: **the number you call from**, **its reputation**, and
**pacing**. Coldy handles the software side; the rest is a one-time carrier setup.

## 1. Local presence (software — done)

People answer local numbers far more than unfamiliar/long-distance ones. Coldy
rotates a **pool** of caller-ID numbers and picks the one whose **area code
matches the lead** (then state, then least-used).

```bash
# .env — a pool covering the regions you call:
COLDY_FROM_NUMBERS=+16125550100,+14155550100,+13055550100
COLDY_PER_NUMBER_DAILY_CAP=200

coldy numbers                       # show the pool + today's usage
coldy numbers --to "+13055551234"   # see which number a given lead gets
```

Buy numbers in the metros you target (Twilio Console → Phone Numbers). More
local coverage = higher answer rates.

## 2. Number reputation (software + ops)

A number that suddenly blasts hundreds of calls gets flagged "Spam Likely."

- **Per-number daily cap** (`COLDY_PER_NUMBER_DAILY_CAP`) spreads volume; Coldy
  won't exceed it and load-balances across the pool (least-used first).
- **Pacing** (`COLDY_DIAL_INTERVAL_SECONDS`, `COLDY_MAX_CONCURRENT_CALLS`) keeps
  the cadence human.
- **Warm up** new numbers (ramp volume over days), and **rotate/rest** numbers.
- **Monitor** spam labeling (e.g. Twilio Voice Integrity / a spam-checker) and
  retire numbers that get flagged.

## 3. STIR/SHAKEN + branded caller ID (ops — do this with your carrier)

This is the part you set up once in the Twilio Console; it can't be fully
scripted:

- **STIR/SHAKEN attestation** — register your numbers so calls are signed with
  full **A-level attestation** (carriers trust them more). On Twilio this is via
  **Trust Hub** (business profile → Shaken/Stir).
- **CNAM / Branded Caller ID** — register a display name (and, where supported,
  a logo/reason-for-call via the CTIA Branded Calling ecosystem) so your business
  name shows instead of a bare number.
- **Use a verified business profile** — required for branded calling and for the
  best attestation.

See Twilio's Trust Hub / Shaken-Stir and Branded Calls docs for the current
steps; budget a few days for verification.

## 4. List hygiene (software — done)

Dead/wrong numbers tank answer rate and hurt reputation. Coldy normalizes to
E.164, drops invalid numbers, dedupes per campaign, and resolves mobile vs
landline on import — so you're not burning dials on junk.

## Measure it

Watch the **funnel** in `coldy report` or the live dashboard (`/dashboard`):
**connect rate** (answers ÷ dials) is the deliverability number. If it's low,
the fix is here — better local coverage, attestation, and pacing — *before* you
touch the script.
