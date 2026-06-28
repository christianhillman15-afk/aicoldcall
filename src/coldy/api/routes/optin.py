"""Opt-in landing page + intake — how prospects become *callable* leads.

  GET  /optin        -> a branded landing page with a consent form (NO numbers
                        on it; each visitor types their own).
  POST /optin        -> form submit -> records consent + creates a callable lead
  POST /api/optin     -> JSON intake for integrations (Zapier/Make, FB Lead Ads
                        via a connector) -> same result.

Every submission stores prior express WRITTEN consent with evidence (the exact
consent language shown, timestamp, IP, user agent) so it's defensible, and drops
the lead into the opt-in campaign already eligible to dial.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from ...compliance.geo import is_mobile, normalize_e164, state_for_number, timezone_for_number
from ...config import settings
from ...db.base import ConsentType, LeadStatus
from ...db.models import Campaign, ConsentRecord, Lead
from ...db.session import session_scope
from ...logging import get_logger

log = get_logger("coldy.api.optin")
router = APIRouter()


def consent_text() -> str:
    """The exact written-consent language shown at opt-in (stored as evidence)."""
    return (
        f"I agree that {settings.company_name} may contact me at the phone number I "
        f"provided, including by automated and AI-generated phone calls and text "
        f"messages, about {settings.product_name} and related services. Consent is "
        f"not a condition of any purchase. Message and data rates may apply. I can "
        f"opt out anytime by saying or replying STOP."
    )


def _truthy(v: str | bool | None) -> bool:
    return str(v).strip().lower() in {"on", "true", "1", "yes"}


def _notify_optin(lead_name: str, phone: str, city: str | None) -> None:
    text = f"✅ New opt-in: {lead_name or 'unknown'} ({city or '—'}) — {phone} consented to AI calls."
    if not settings.alert_webhook_url:
        log.info(text)
        return
    try:
        httpx.post(settings.alert_webhook_url, json={"text": text}, timeout=10)
    except httpx.HTTPError as e:
        log.warning("Opt-in alert failed: %s", e)


def record_optin(
    *,
    phone: str,
    consent: bool,
    business_name: str = "",
    contact_name: str = "",
    email: str = "",
    industry: str = "",
    city: str = "",
    src: str = "",
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[bool, str, int | None]:
    """Validate + persist an opt-in. Returns (ok, message, lead_id)."""
    if not consent:
        return (False, "We can only reach out if you check the consent box.", None)
    e164 = normalize_e164(phone)
    if not e164:
        return (False, "Please enter a valid US phone number.", None)

    with session_scope() as s:
        camp = s.query(Campaign).filter(Campaign.name == settings.optin_campaign).one_or_none()
        if camp is None:
            camp = Campaign(name=settings.optin_campaign, goal="Qualify opt-ins and book a discovery call.")
            s.add(camp)
            s.flush()

        lead = (
            s.query(Lead)
            .filter(Lead.campaign_id == camp.id, Lead.phone == e164)
            .one_or_none()
        )
        if lead is None:
            lead = Lead(campaign_id=camp.id, phone=e164)
            s.add(lead)
        lead.business_name = business_name or lead.business_name
        lead.contact_name = contact_name or lead.contact_name
        lead.industry = industry or lead.industry
        lead.city = city or lead.city
        lead.state = lead.state or state_for_number(e164)
        lead.timezone = lead.timezone or timezone_for_number(e164)
        if lead.is_mobile is None:
            lead.is_mobile = is_mobile(e164)
        lead.do_not_call = False
        lead.status = LeadStatus.QUEUED  # consented + eligible to dial
        note = f"opt-in via {src or 'landing page'}"
        if email:
            note += f"; email={email}"
        lead.notes = note

        s.add(
            ConsentRecord(
                lead=lead,
                consent_type=ConsentType.EXPRESS_WRITTEN,
                source=f"landing_page:{src or 'direct'}",
                consent_text=consent_text(),
                ip_address=ip,
                user_agent=(user_agent or "")[:400] or None,
            )
        )
        s.flush()
        lead_id = lead.id
        lead_city = lead.city

    _notify_optin(contact_name or business_name, e164, lead_city)
    log.info("Opt-in recorded: lead %s (%s)", lead_id, e164)
    return (True, "You're all set — we'll be in touch shortly!", lead_id)


# --- JSON intake (Zapier / Make / Facebook Lead Ads via a connector) ---------

class OptinPayload(BaseModel):
    phone: str
    consent: bool = False
    business_name: str = ""
    contact_name: str = ""
    email: str = ""
    industry: str = ""
    city: str = ""
    src: str = ""


@router.post("/api/optin")
def api_optin(payload: OptinPayload, request: Request) -> JSONResponse:
    ok, message, lead_id = record_optin(
        phone=payload.phone,
        consent=payload.consent,
        business_name=payload.business_name,
        contact_name=payload.contact_name,
        email=payload.email,
        industry=payload.industry,
        city=payload.city,
        src=payload.src or "api",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return JSONResponse(
        {"ok": ok, "message": message, "lead_id": lead_id},
        status_code=200 if ok else 400,
    )


# --- HTML landing page + form submit -----------------------------------------

@router.get("/optin", response_class=HTMLResponse)
def optin_page(src: str = "") -> str:
    return _PAGE.format(
        company=settings.company_name,
        product=settings.product_name,
        pitch=settings.product_pitch,
        value=settings.value_prop_short,
        consent=consent_text(),
        src=src,
    )


@router.post("/optin", response_class=HTMLResponse)
async def optin_submit(
    request: Request,
    phone: str = Form(...),
    business_name: str = Form(""),
    contact_name: str = Form(""),
    email: str = Form(""),
    industry: str = Form(""),
    city: str = Form(""),
    consent: str = Form(""),
    src: str = Form(""),
) -> str:
    ok, message, _ = record_optin(
        phone=phone,
        consent=_truthy(consent),
        business_name=business_name,
        contact_name=contact_name,
        email=email,
        industry=industry,
        city=city,
        src=src,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    if ok:
        return _THANKS.format(company=settings.company_name, message=message)
    # Re-render the form with the error.
    page = _PAGE.format(
        company=settings.company_name, product=settings.product_name,
        pitch=settings.product_pitch, value=settings.value_prop_short,
        consent=consent_text(), src=src,
    )
    return page.replace("<!--ERROR-->", f'<p class="err">{message}</p>')


_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{company} — Get More Booked Jobs</title>
<style>
 :root{{color-scheme:light}}
 *{{box-sizing:border-box}}
 body{{margin:0;font:16px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;color:#1b2733;
   background:linear-gradient(160deg,#0e1116,#1c2733);min-height:100vh;display:flex;
   align-items:center;justify-content:center;padding:24px}}
 .card{{background:#fff;border-radius:18px;max-width:560px;width:100%;padding:36px;
   box-shadow:0 20px 60px rgba(0,0,0,.35)}}
 h1{{font-size:26px;margin:0 0 6px}} .sub{{color:#5b6b7b;margin:0 0 22px}}
 label{{display:block;font-size:13px;font-weight:600;color:#33414f;margin:14px 0 4px}}
 input,select{{width:100%;padding:11px 12px;border:1px solid #cfd8e0;border-radius:10px;font-size:15px}}
 .row{{display:flex;gap:12px}} .row>div{{flex:1}}
 .consent{{display:flex;gap:10px;align-items:flex-start;margin:18px 0 8px;
   background:#f3f6f9;border:1px solid #e0e7ee;border-radius:10px;padding:12px}}
 .consent input{{width:auto;margin-top:4px}} .consent small{{color:#5b6b7b;font-size:12px}}
 button{{width:100%;margin-top:16px;padding:14px;border:0;border-radius:10px;
   background:#1763ff;color:#fff;font-size:16px;font-weight:650;cursor:pointer}}
 button:hover{{background:#0f4fd6}}
 .err{{background:#fdecec;color:#b42318;border:1px solid #f3c4c0;padding:10px 12px;
   border-radius:10px;font-size:14px;margin:0 0 14px}}
 .fine{{color:#8a98a6;font-size:11px;margin-top:14px}}
</style></head><body>
<div class="card">
  <h1>Get more booked jobs.</h1>
  <p class="sub">{company} helps local service businesses with {value}. Tell us
     where to reach you and a specialist will walk you through {product}.</p>
  <!--ERROR-->
  <form method="post" action="/optin">
    <input type="hidden" name="src" value="{src}"/>
    <div class="row">
      <div><label>Your name</label><input name="contact_name" autocomplete="name"/></div>
      <div><label>Business name</label><input name="business_name"/></div>
    </div>
    <div class="row">
      <div><label>Phone *</label><input name="phone" type="tel" required autocomplete="tel" placeholder="(612) 555-0100"/></div>
      <div><label>Email</label><input name="email" type="email" autocomplete="email"/></div>
    </div>
    <label>What do you do?</label>
    <select name="industry">
      <option value="">Select…</option>
      <option>painting</option><option>hvac</option><option>plumbing</option>
      <option>landscaping</option><option>cleaning</option><option>roofing</option>
      <option>electrical</option><option>other</option>
    </select>
    <label class="consent">
      <input type="checkbox" name="consent" value="on" required/>
      <small>{consent}</small>
    </label>
    <button type="submit">Get my free consultation →</button>
  </form>
  <p class="fine">By submitting, you agree to the consent above. We respect your
     privacy and you can opt out anytime.</p>
</div></body></html>"""


_THANKS = """<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Thanks — {company}</title>
<style>body{{margin:0;font:18px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;
 background:linear-gradient(160deg,#0e1116,#1c2733);color:#e6edf3;min-height:100vh;
 display:flex;align-items:center;justify-content:center;text-align:center;padding:24px}}
 .c{{max-width:480px}} h1{{font-size:30px}} .check{{font-size:54px}}</style></head>
<body><div class="c"><div class="check">✅</div><h1>{message}</h1>
<p>Thanks for reaching out to {company}. Keep an eye on your phone — we'll call from a local number.</p>
</div></body></html>"""
