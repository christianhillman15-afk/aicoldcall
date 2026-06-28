# Prospecting — finding businesses Oxsome can help

The prospecting engine **finds** service businesses, **scores** how well they fit
(do they need marketing help, and can they afford it), and **flags** the best
ones to you. It's the top of the funnel that feeds the dialer.

```bash
coldy prospect search -l "Edina, MN" -q painting --source google
coldy prospect search -l "Miami, FL" -q "hvac" --source yelp --limit 30
coldy prospect list --flagged
coldy prospect export --flagged -o hot_prospects.csv     # -> feed the dialer (after consent)
```

## How it scores

| Signal | Feeds | Why |
|---|---|---|
| No website | **need** ↑ | Biggest "we can help" signal — Oxsome builds them one. |
| Low rating (<4.0), few reviews | **need** ↑ | Weak online presence = upside. |
| Affluent ZIP (Census median income) | **afford** ↑ | "Good area" / can pay. |
| Price level, lots of reviews (busy/established) | **afford** ↑ | Real revenue, real budget. |
| Reachable (has phone) | **afford** ↑ | Actionable. |

A prospect is **flagged** only when it *both* needs help **and** looks able to
pay (`COLDY_PROSPECT_MIN_FIT/AFFORD/NEED`) — no point chasing businesses that
can't afford it. Flagged prospects are pushed to `COLDY_ALERT_WEBHOOK_URL`
(Slack-compatible) and stored.

## Sources (official APIs — not scraping)

| Source | Get a key | Notes |
|---|---|---|
| `mock` | — | Offline sample data; runs with zero keys. |
| `google` | `GOOGLE_PLACES_API_KEY` | Places API (New). Richest: website, phone, rating, price. Respect Google's caching terms. |
| `yelp` | `YELP_API_KEY` | Yelp Fusion. Great ratings/review depth; note Yelp's data-retention limits. |
| Census | `CENSUS_API_KEY` (optional) | Median household income by ZIP (affluence). |

## Why we DON'T scrape Facebook / Nextdoor

You asked about scraping Facebook and Nextdoor for people "looking for marketing
help." We deliberately **don't** do that, because:

- It **violates their Terms of Service** and US law (the CFAA + privacy laws like
  CCPA/GDPR). Meta and others actively ban and **sue** scrapers.
- People scraped that way gave **no consent** — so cold-calling them is the exact
  **TCPA** violation the rest of this system is built to avoid (AI voice
  telemarketing needs prior express written consent).

### The compliant way to capture "intent" (and it works better)

Turn it around: instead of scraping people who *might* want help, **let them
raise their hand** — which also makes them legally callable.

1. **Run ads** on Facebook/Instagram and Nextdoor (both have official Ads/Lead
   products) targeting local service businesses, e.g. "Painters: get more booked
   jobs from Google."
2. Send clicks to a **landing page / lead form** with a clear consent checkbox:
   *"I agree to be contacted, including by automated/AI calls and texts, at the
   number provided."*
3. Those opt-ins are **flagged + consented leads** — pipe them straight into a
   campaign and the dialer can legally call them.
4. For *public business* pages (not personal profiles), use the official **Meta
   Graph API** for pages you manage — within API limits.

This inbound funnel is the "bot that flags people and sends them to you" — done
the way that doesn't get you banned or sued, and that makes every lead callable.

**This is now built in.** `coldy serve` hosts the landing page at **`/optin`**
and a JSON intake at **`POST /api/optin`**:

- Point your Facebook/Instagram/Nextdoor **ads** at
  `https://<your-domain>/optin?src=fb_painters` (the `src` is stored for
  attribution).
- Each submission records **prior express written consent** with evidence (the
  exact consent text shown, timestamp, IP, user agent) and creates a **callable
  lead** in the `Web Opt-ins` campaign, eligible to dial immediately.
- **Facebook Lead Ads / Zapier / Make:** map the lead fields to a JSON POST to
  `/api/optin` (`phone`, `consent: true`, `contact_name`, `business_name`,
  `industry`, `src`). Same result.
- You get pinged on each opt-in via `COLDY_ALERT_WEBHOOK_URL`.

So the loop is fully closed: **ad → /optin (consent) → dialer calls them.**

## The hand-off to the dialer

```
prospect search ──► flagged prospects ──► export CSV
                                              │  (capture consent: ad/form opt-in,
                                              ▼   or contact them another way first)
                                         coldy import ──► campaign ──► dialer
```

Prospects are **not** consented leads. `coldy prospect export` writes a CSV in
`coldy import` format so promotion is one step — but only call them once you have
consent on file (`coldy consent add`). The engine finds *who*; consent makes them
*callable*.
