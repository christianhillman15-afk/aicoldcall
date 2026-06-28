# The Playbook: Perfect Cold Calling + Perfect Human-Sounding AI Calls

A "perfect" AI cold call is two crafts stacked on top of each other:

- **The conversation** — sales craft. What gets said, in what order, how
  objections are handled, how the meeting gets booked.
- **The technology** — voice-AI engineering. Why it *sounds* like a person:
  latency, turn-taking, prosody, spoken register.

Nail only one and you fail: a brilliant script delivered by a laggy robot gets
hung up on in five seconds; a flawless-sounding voice with a bad script gets
"not interested." This doc covers both, then shows how Coldy implements each
point.

> Legal first: read [`COMPLIANCE.md`](COMPLIANCE.md). In the US, AI-voice
> telemarketing generally needs **prior express written consent**. "Perfect"
> includes "lawful." Everything below assumes you're calling people who agreed
> to be contacted.

---

## Part A — The perfect cold call (sales craft)

### 1. The first 7 seconds decide everything

Most calls die in the opener. Two failure modes: sounding like a telemarketer
(triggers instant brush-off) and sounding scripted (triggers distrust). Beat
both with a **permission-based, pattern-interrupting opener** that is honest,
brief, and hands control to the prospect.

A strong opener has four micro-moves, in ~8 seconds:

1. **Identify** — who you are + (for AI, legally required) that you're an AI
   assistant on behalf of the company.
2. **Disarm with permission** — "did I catch you at an okay moment?" This single
   question dramatically raises engagement: it respects their time and earns a
   small "yes" that opens the conversation.
3. **Reason for the call** — one sentence, about *them*, not you.
4. **Stop talking.** Let them respond. The opener is a question, not a pitch.

> ✅ "Hi, this is Avery, an AI assistant calling on behalf of Launch Media. I'll
> keep this quick — did I catch you at an okay moment?"
> *(pause, listen)* "Awesome — the reason I'm calling is we help local painting
> companies get more booked jobs from their website and Google. Mind if I ask —
> how are you getting most of your jobs right now?"

> ❌ "Hi! How are you today?! I'm calling from Launch Media and we're a
> full-service AI marketing platform offering websites, SEO, Google Ads, social
> media management, and..." *(click)*

### 2. Call structure: the funnel

```
Opener (permission)  ->  Reason for call (about them)  ->  Hook (one problem you solve)
   ->  Qualifying question (is this even relevant?)  ->  Discovery (2-3 questions, listen)
   ->  Value tailored to what they said  ->  CTA: book the 15-min discovery call
```

Rules:

- **The goal is the *meeting*, not the sale.** On a cold call you're selling the
  next step, not the product. Lowering the ask ("a quick fifteen-minute call with
  a specialist") raises yes-rates massively.
- **One idea at a time.** Never list features. Pick the one problem most likely
  to land for this prospect and lead with the *problem*, not the feature.
- **Talk/listen ratio ~43/57.** The best reps listen more than they talk. Ask,
  then shut up. Silence after a question is your friend.
- **Earn the right to pitch.** You pitch *after* they've told you something you
  can tailor to.

### 3. Discovery for SMB service businesses

You're qualifying lightly, not interrogating. Three questions max before the CTA:

- "How are you getting most of your jobs right now — referrals, Google, ads?"
- "When someone searches '[their trade] near me,' are you showing up?"
- "If we could get you two or three more booked jobs a month, would that be
  worth a quick look?"

A simple SMB qualification frame:

- **Need** — is their lead flow weak / website old / not ranking?
- **Authority** — are you talking to the owner / decision-maker?
- **Timing** — busy season coming? Slow now and want more work?
- **Fit** — are they the kind of local service business your offer suits?

### 4. Objection handling (acknowledge → reframe → redirect)

Never argue. Acknowledge the human, reframe lightly, redirect to the small ask.

| They say | Don't | Do |
|---|---|---|
| "Not interested." | Push the pitch | "Totally fair. Quick question — are you happy with how many jobs you're booking right now, or could you use more?" If still no: thank + offer opt-out. |
| "I'm busy / bad time." | Plow ahead | "Of course — I'll be quick or grab a better time. Is later today or tomorrow morning better?" |
| "Just send me an email." | Only send the email | "Happy to. So I send the right thing — are you more focused on the website or getting found on Google? And could we grab fifteen minutes so it's not just another email in the pile?" |
| "How much is it?" | Quote a number cold | "Great question — it depends on what you actually need, so a specialist walks you through options on the call. Most owners are surprised it's less than one extra job a month. Want me to set that up?" |
| "How'd you get my number?" | Get defensive | "Fair to ask — we reach out to local service businesses that look like a fit. If you'd rather not hear from us, I'll take you off right now." |
| "Are you a robot?" | Dodge | "I am — I'm an AI assistant for Launch Media. Happy to connect you with a person if you'd prefer." |
| Gatekeeper | Trick them | Be warm + direct: "Hi! Is the owner around? I help [trade] businesses get more booked jobs — wanted to see if it's worth a quick chat." |
| "Take me off your list." | Anything but comply | Immediately add to DNC, confirm warmly, end the call. Non-negotiable. |

### 5. Voicemail strategy

Most calls hit voicemail. Either (a) don't pitch a machine — detect it and move
on (Coldy's AMD does this), or (b) leave a short, curiosity-driven message and
let the callback/retry cadence work. A good voicemail is < 15 seconds, says who
+ why + a specific reason to call back, and never pitches.

### 6. Timing, cadence, persistence

- **Best connect windows:** mid-morning (≈10–11am) and late afternoon
  (≈4–5pm) local; early in the week is often better than Friday. Always within
  the legal 8am–9pm local window.
- **Cadence:** it routinely takes 3–6 touches to reach a prospect. Space retries
  (Coldy default: 24h apart, max 3 attempts) and vary the time of day.
- **Persistence ≠ pestering.** Cap attempts, honor opt-outs instantly, and stop
  on a clear no.

### 7. The metrics that matter

| Metric | What it tells you | Lever |
|---|---|---|
| **Connect rate** (answers / dials) | Number/list quality, deliverability | Better data, local presence, number reputation |
| **Conversation rate** (real talks / connects) | Opener strength | Fix the first 10 seconds |
| **Meeting rate** (booked / conversations) | Pitch + objection handling | Tighten the CTA, the hook, discovery |
| **Show rate** (showed / booked) | Lead quality + reminders | Confirmations, SMS reminders |
| Talk/listen ratio, interruptions | Conversation health | Tune VAD, persona brevity |

Optimize in that order — a 2× better opener beats a 2× bigger list.

---

## Part B — The perfect human-sounding AI call (engineering)

The dirty secret: callers forgive a slightly synthetic *timbre* far more than
they forgive **bad timing**. Get the conversation *rhythm* right and people stop
caring that it's AI. Rhythm is mostly latency + turn-taking.

### 1. Latency is king

Target the gap between "human stops talking" and "agent starts talking":

| Round-trip | Feel |
|---|---|
| **< 800 ms** | Natural — like a real person |
| ~1 s | Acceptable |
| > 1.5 s | Noticeably robotic; people start talking over it |

Hit it by **streaming every stage** and never waiting for a stage to finish:

```
human speech ─stream─> STT(interim+final) ─stream tokens─> LLM
            ─sentence chunks─> TTS(first sentence) ─audio─> caller
```

The agent starts speaking the first sentence while the LLM is still generating
the rest. Budget roughly: VAD end-of-turn ~300–600 ms, STT finalize ~100–300 ms,
LLM time-to-first-token ~200–500 ms, TTS time-to-first-byte ~100–300 ms — overlap
them and you land under a second.

### 2. Turn-taking & barge-in (the #1 human tell)

- **Endpointing / VAD.** How long of a pause means "they're done"? Too short and
  you cut people off; too long and you feel laggy. ~0.5–0.8 s of silence is the
  sweet spot on the phone (Coldy: `vad_stop_secs = 0.6`). Smart endpointing also
  uses the *content* — "my number is..." clearly isn't finished.
- **Barge-in.** A human stops the instant you start talking over them. The agent
  must too: when VAD detects the caller speaking, **immediately stop TTS playback
  and cancel the in-flight LLM/TTS**, then listen. Without barge-in it sounds
  like a robot reading a script. (Pipecat handles this via
  `allow_interruptions=True` + VAD.)
- **Don't double-talk.** After you ask a question, *stop*. Let silence pull the
  answer out.

### 3. Voice (TTS) — the timbre

Pick a TTS with **low time-to-first-byte** *and* natural prosody. Leaders in 2026
for real-time phone:

- **Cartesia Sonic** — very low latency, natural; Coldy's default.
- **ElevenLabs Flash/Turbo** — excellent quality; Flash is the low-latency tier.
- **Rime** — built for conversational/expressive phone voices.
- **Deepgram Aura** — fast, tightly integrated if you also use Deepgram STT.

Tips: choose a **warm, mid-energy US voice** (not a hype-y "announcer"); keep TTS
**streaming, sentence-chunked**; and feed it text shaped for speech (next point).

### 4. Make the LLM talk like a person, not write like one

This is 80% of perceived human-ness and it's all in the prompt. The persona must
force a **spoken register** (see `voice/persona.py`):

- Short turns (1–2 sentences). No monologues.
- Contractions, casual phrasing, ONE question at a time.
- **No lists, markdown, emojis, or headings** — it's speech.
- Speak numbers/money/URLs the human way ("twelve hundred bucks", "oxsome dot
  com"), never digits or symbols (TTS mangles "$1,200" and "https://").
- Light, occasional backchannels ("yeah", "gotcha", "for sure").
- React to what was actually said; don't recite.
- If interrupted, stop and address the new thing. If silence, gently check in
  ("you still there?") instead of restarting.

### 5. Masking the unavoidable latency

Even at < 1 s there's a beat before the answer. Humans fill it naturally; so can
the agent:

- **Instant acknowledgers.** A quick "mm-hmm" / "yeah, totally" can be emitted
  *immediately* on end-of-turn while the LLM thinks, masking the gap.
- **Thinking sounds.** "Good question, let me think..." buys time on hard turns —
  used sparingly so it doesn't become a tic.
- Keep responses **short** — long replies feel like a recording and invite
  interruption.

### 6. Speech-to-text on telephony

Phone audio is **8 kHz mu-law mono** — narrowband and lossy. Use an STT model
tuned for it (Deepgram `nova-3`), stream partials for fast endpointing, and
expect names/numbers to be the hard part — have the agent **confirm critical
details back** ("so that's five-one-two...?"). Coldy speaks numbers back when
booking.

### 7. Tools = the agent actually *doing* things

A human rep books the meeting, takes them off the list, transfers to a manager.
The AI does the same via tool calls (`voice/tools.py`): `book_meeting`,
`schedule_callback`, `transfer_to_human`, `add_to_do_not_call`, `end_call`. Tool
results are fed back so the agent confirms naturally ("done — a specialist will
call you Thursday at two").

### 8. Model, streaming, caching

- **Model:** latency favors a fast model for the turn loop (`claude-haiku-4-5`
  default). Use a smarter model (`claude-sonnet-4-6`/`claude-opus-4-8` + Fast
  Mode) when objection nuance matters. Optionally two-tier: fast model normally,
  smart model for hard turns.
- **Stream tokens**, chunk into sentences for TTS.
- **Prompt-cache the system prompt/persona** — it's large and identical across
  every call in a campaign, so caching cuts both latency and cost.
- **Keep `max_tokens` small** (~300) — spoken turns are short; this caps worst-
  case latency.

### 9. Robotic tells to avoid (a checklist)

- ❌ Long pauses before responding → fix latency / add acknowledgers.
- ❌ Talking over the caller / not stopping → fix barge-in + VAD.
- ❌ Monologuing / listing features → shorten persona turns.
- ❌ Reading "$1,200", "https://oxsome.com", "#1" literally → speak-it-out rules.
- ❌ Ignoring interruptions and resuming the script → handle interruptions.
- ❌ Same canned opener regardless of response → react to what they said.
- ❌ Repeating the prospect's name every sentence → unnatural; use sparingly.
- ❌ Over-perky "announcer" energy → warm, calm, mid-energy.

---

## Part C — A perfect call, annotated

```
AI:   Hi, this is Avery, an AI assistant calling on behalf of Launch Media.
      I'll keep this quick — did I catch you at an okay moment?
        ▲ identity + (legal) AI disclosure + permission. Then STOP.

H:    Uh, who is this?

AI:   Avery, with Launch Media — we help local painting companies book more
      jobs. Is this North Star Painting?
        ▲ brief re-identify, reason about THEM, easy yes/no question.

H:    Yeah, this is Dan.

AI:   Hey Dan. The reason I'm calling — a lot of painters we talk to are losing
      jobs because they don't show up on Google when people search. How are you
      getting most of your work right now?
        ▲ one problem (not a feature dump) + ONE discovery question. Then listen.

H:    Mostly referrals, honestly. Word of mouth.

AI:   Gotcha — referrals are great, but they're unpredictable, right? When word
      of mouth's slow, the work dries up. If I could show you how to get a
      steady two or three extra jobs a month from Google, worth a quick look?
        ▲ acknowledge + reframe + low-friction CTA (look, not buy).

H:    How much does that cost though?

AI:   Fair question — it depends what you actually need, so a specialist walks
      you through options on a quick call. Most owners are surprised it's less
      than one extra job a month pays for. Want me to set up fifteen minutes?
        ▲ classic price-objection redirect to the meeting.

H:    Yeah, okay.

AI:   Awesome. What's better for you — tomorrow morning or afternoon?
        [book_meeting tool fires; AI confirms the details back out loud]
        ▲ assume-the-close, capture, confirm.
```

---

## Part D — Test, score, iterate

You don't write the perfect call — you *tune* it.

1. **Record + transcribe** (where consent allows). Read transcripts; listen to
   the openers.
2. **Score every call** on: did the opener earn a conversation? where did it
   lose them? did it sound natural? did it book?
3. **A/B one variable at a time** — opener wording, the hook, VAD timing, voice,
   model. Change one thing, measure connect→conversation→meeting.
4. **Watch the funnel order:** fix connect rate (data/deliverability), then
   conversation rate (opener), then meeting rate (pitch/objections).
5. **Listen for robotic tells** (Part B §9) and tune `voice/humanizer.py` +
   `voice/persona.py`.

### Deliverability (so calls get answered at all)

- **Caller ID / local presence:** dial from a number matching the lead's area
  code (rotate a pool). Unfamiliar/long-distance numbers get ignored.
- **STIR/SHAKEN attestation:** register your numbers with the carrier for full
  (A-level) attestation so you aren't flagged "Spam Likely."
- **Number reputation / pacing:** don't blast from one number; spread volume,
  pace dials (Coldy: `dial_interval_seconds`), and monitor spam-labeling. Rotate
  and rest numbers.
- **List hygiene:** dead/wrong numbers tank connect rate and hurt reputation —
  validate and dedupe (Coldy normalizes + dedupes on import).

---

## How Coldy implements this

| Playbook point | In the code |
|---|---|
| Permission opener + AI disclosure | `voice/persona.py` → `build_opening_line`; `compliance/disclosure.py` |
| Spoken-style register, one-question-at-a-time, speak-it-out | `voice/persona.py` → `SPOKEN_STYLE_RULES` |
| Objection handling + book-the-meeting goal | `voice/persona.py` system prompt |
| Sub-second latency / streaming pipeline | `voice/bot.py` (Pipecat streaming STT→LLM→TTS) |
| Barge-in + endpointing tuning | `voice/humanizer.py` (`TurnTakingConfig`), `voice/bot.py` (VAD params) |
| In-call actions (book/transfer/opt-out) | `voice/tools.py` |
| Voicemail (AMD) handling | `telephony/twilio_client.py` (`machine_detection`), `api/.../twilio_webhooks.py` |
| Timing windows, cadence, retries | `compliance/calling_hours.py`, `compliance/engine.py`, `dialer/worker.py` |
| Pacing / concurrency / deliverability | `dialer/worker.py`, `COLDY_DIAL_INTERVAL_SECONDS`, `COLDY_MAX_CONCURRENT_CALLS` |
| Metrics / outcomes | `dialer/campaign.py` (`report`), `crm/` |
| Model / latency tuning | `config.py` (`llm_model`, `llm_fast_mode`, `llm_max_tokens`) |
```
