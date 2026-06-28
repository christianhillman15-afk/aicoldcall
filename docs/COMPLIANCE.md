# Compliance (US)

> **Not legal advice.** This summarizes why Coldy's guardrails exist and how they
> map to US law. TCPA penalties are **$500–$1,500 per call** and class actions are
> common. Have qualified counsel review your consent capture, scripts, and process.

## The headline: AI voices are "artificial/prerecorded" under the TCPA

On **February 8, 2024** the FCC issued a Declaratory Ruling that calls using
**AI technologies that generate human-sounding voices are "artificial or
prerecorded voice" calls under the TCPA** — effective immediately.

Consequences for an AI cold-caller:

1. **Consent.** Artificial/prerecorded-voice calls require the called party's
   **prior express consent**. For **telemarketing** (which selling marketing
   services is), that means **prior express *written* consent** — and to a
   **wireless** number, written consent is required regardless. A bare cold call
   to a stranger's cell with an AI voice and no consent is the textbook
   violation.
2. **Identification.** The message must identify the entity responsible for the
   call at the start.
3. **Opt-out.** Telemarketing artificial-voice calls must offer an opt-out
   mechanism, honored promptly.

Coldy enforces all three by default.

## What "cold calling hundreds of leads a day" really means

You generally **cannot** legally point an AI voice at hundreds of strangers who
never agreed to be called. The lawful shapes of this are:

- **Permission-based outreach.** Call people/businesses who gave prior express
  written consent to receive automated/AI calls (e.g. a checkbox on your site, a
  contract clause, a lead-gen form that discloses AI calling). This is the model
  Coldy is built around — consent is a first-class, auditable record.
- **Manually-dialed, live-agent calls** are a different legal regime; an
  always-on AI voice is not that.
- **B2B nuance.** Some TCPA provisions and the National DNC Registry are framed
  around residential subscribers, and business-to-business calls have *some*
  different treatment — but the **artificial/prerecorded-voice consent rule and
  state law still reach many B2B calls**, especially to wireless numbers (and
  most small-business owners' "business" line is a cell). Do **not** assume "it's
  B2B so it's fine." Get the consent.

## What Coldy enforces (in code)

The `ComplianceEngine.evaluate(lead)` gate (in `compliance/engine.py`) blocks a
call unless **all** pass. The dialer calls it before every dial.

| Rule | Where | Default |
|---|---|---|
| Internal/company DNC + per-lead DNC flag | `compliance/dnc.py` | Always on; opt-outs added instantly via the in-call tool |
| Federal National DNC Registry | `compliance/dnc.py` (`set_federal_dnc_checker`) | **You must wire a licensed provider**; unknown by default |
| Prior express **written** consent | `compliance/engine.py` + `ConsentRecord` | Required (`COLDY_REQUIRE_WRITTEN_CONSENT=true`) |
| Calling window 8am–9pm local | `compliance/calling_hours.py` | 9:00–20:00 in the lead's local tz; **fails closed** if tz unknown |
| Attempt cap + retry spacing | `compliance/engine.py` | 3 attempts, 24h apart |
| Recording consent (two-party states) | `compliance/recording.py` | Recording off by default; notice injected where required |
| AI identity + opt-out disclosure | `compliance/disclosure.py` + persona | Spoken verbatim at call open; opt-out honored mid-call |

## State-level AI disclosure

Several states regulate automated/"bot" communications and call recording:

- **Bot-disclosure laws** (e.g. California's B.O.T. Act) require disclosing that
  the user is talking to an automated system in certain commercial contexts.
  Coldy opens **every** call by stating it's an AI assistant — the safe default.
- **All-party (two-party) recording-consent states** (CA, FL, IL, PA, WA, MA,
  and others — see `compliance/recording.py`) require all parties consent to
  recording. Coldy only records when you enable it, and injects a spoken
  recording notice for those states (and when the state is unknown).

## Operating checklist

- [ ] Capture and store prior express **written** consent before importing leads
      to dial; keep the evidence (`coldy consent add --evidence-url …`).
- [ ] Scrub against the **federal National DNC Registry** via a licensed provider
      (`set_federal_dnc_checker`) and maintain your **internal DNC** list.
- [ ] Keep the **8am–9pm local** window (Coldy enforces; don't widen blindly).
- [ ] Keep the **AI-identity disclosure** and **opt-out** in the opening/persona.
- [ ] Honor opt-outs immediately and forever (the `add_to_do_not_call` tool does).
- [ ] Configure **recording** posture per state, or leave it off.
- [ ] Maintain caller-ID accuracy and STIR/SHAKEN attestation with your carrier.
- [ ] Have counsel review everything for your specific offer and audience.

## Sources

- FCC, *Declaratory Ruling — AI-generated voices are "artificial or prerecorded"
  under the TCPA* (Feb 8, 2024): https://www.fcc.gov/document/fcc-confirms-tcpa-applies-ai-technologies-generate-human-voices
- FCC press release, *AI-Generated Voices in Robocalls* (Feb 8, 2024): https://www.fcc.gov/document/fcc-makes-ai-generated-voices-robocalls-illegal
- FCC FCC-24-17 (full ruling): https://docs.fcc.gov/public/attachments/FCC-24-17A1.pdf
- Federal Register notice: https://www.federalregister.gov/documents/2024/09/10/2024-19028/implications-of-artificial-intelligence-technologies-on-protecting-consumers-from-unwanted-robocalls
