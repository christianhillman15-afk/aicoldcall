"""``coldy`` command-line interface.

    coldy init                         create database tables
    coldy import LEADS.csv --campaign  import leads into a campaign
    coldy consent add --phone ...      record prior express written consent
    coldy dnc add --phone ...          suppress a number (internal DNC)
    coldy campaign create/start/pause  manage a campaign
    coldy run --campaign NAME          run the dialer (use --dry-run to preview)
    coldy report --campaign NAME       show campaign stats
    coldy check --phone ...            preview the compliance decision for a number
    coldy persona                      print the system prompt the bot will use
    coldy serve                        run the FastAPI webhook/media server
    coldy doctor                       check configuration
"""

from __future__ import annotations

import asyncio

import typer
from rich import print as rprint
from rich.table import Table

from .config import settings
from .logging import get_logger

log = get_logger("coldy.cli")
app = typer.Typer(add_completion=False, help="Coldy — human-sounding, compliant AI cold calling.")
campaign_app = typer.Typer(help="Manage campaigns.")
consent_app = typer.Typer(help="Manage consent records.")
dnc_app = typer.Typer(help="Manage the internal do-not-call list.")
app.add_typer(campaign_app, name="campaign")
app.add_typer(consent_app, name="consent")
app.add_typer(dnc_app, name="dnc")


@app.command()
def init() -> None:
    """Create database tables."""
    from .db.session import init_db

    init_db()
    rprint(f"[green]Database ready[/green] at {settings.database_url}")


@app.command(name="import")
def import_leads(
    csv_path: str = typer.Argument(..., help="Path to the leads CSV"),
    campaign: str = typer.Option(..., "--campaign", "-c", help="Campaign name"),
) -> None:
    """Import leads from a CSV into a campaign."""
    from .db.session import init_db
    from .leads import import_leads_csv

    init_db()
    result = import_leads_csv(csv_path, campaign)
    rprint(f"[green]Done:[/green] {result}")


@consent_app.command("add")
def consent_add(
    phone: str = typer.Option(..., "--phone", "-p"),
    source: str = typer.Option(..., "--source", "-s", help="Where/how consent was captured"),
    written: bool = typer.Option(True, "--written/--express", help="Express WRITTEN consent (required for AI telemarketing)"),
    evidence_url: str = typer.Option("", "--evidence-url"),
) -> None:
    """Record consent for every lead matching a phone number."""
    from sqlalchemy import select

    from .compliance.geo import normalize_e164
    from .db.base import ConsentType
    from .db.models import ConsentRecord, Lead
    from .db.session import init_db, session_scope

    init_db()
    e164 = normalize_e164(phone)
    if not e164:
        rprint(f"[red]Invalid phone:[/red] {phone}")
        raise typer.Exit(1)

    ctype = ConsentType.EXPRESS_WRITTEN if written else ConsentType.EXPRESS
    n = 0
    with session_scope() as s:
        for lead in s.execute(select(Lead).where(Lead.phone == e164)).scalars():
            s.add(
                ConsentRecord(
                    lead_id=lead.id,
                    consent_type=ctype,
                    source=source,
                    evidence_url=evidence_url or None,
                )
            )
            n += 1
    rprint(f"[green]Recorded {ctype.value} consent for {n} lead(s)[/green] ({e164})")
    if n == 0:
        rprint("[yellow]No leads matched that number yet — import them first.[/yellow]")


@dnc_app.command("add")
def dnc_add(
    phone: str = typer.Option(..., "--phone", "-p"),
    reason: str = typer.Option("", "--reason", "-r"),
) -> None:
    """Add a number to the internal do-not-call list."""
    from .compliance.dnc import add_to_dnc
    from .compliance.geo import normalize_e164
    from .db.session import init_db, session_scope

    init_db()
    e164 = normalize_e164(phone) or phone
    with session_scope() as s:
        add_to_dnc(s, e164, reason=reason, source="cli")
    rprint(f"[green]Added to DNC:[/green] {e164}")


@campaign_app.command("create")
def campaign_create(
    name: str = typer.Argument(...),
    goal: str = typer.Option("", "--goal", "-g"),
) -> None:
    from .db.session import init_db, session_scope
    from .dialer import CampaignService

    init_db()
    with session_scope() as s:
        svc = CampaignService(s)
        if svc.get(name):
            rprint(f"[yellow]Campaign already exists:[/yellow] {name}")
            return
        svc.create(name, goal or None)
    rprint(f"[green]Created campaign:[/green] {name}")


@campaign_app.command("start")
def campaign_start(name: str = typer.Argument(...)) -> None:
    _set_campaign_status(name, "RUNNING")


@campaign_app.command("pause")
def campaign_pause(name: str = typer.Argument(...)) -> None:
    _set_campaign_status(name, "PAUSED")


def _set_campaign_status(name: str, status_name: str) -> None:
    from .db.base import CampaignStatus
    from .db.session import init_db, session_scope
    from .dialer import CampaignService

    init_db()
    with session_scope() as s:
        camp = CampaignService(s).set_status(name, CampaignStatus[status_name])
        if camp is None:
            rprint(f"[red]No such campaign:[/red] {name}")
            raise typer.Exit(1)
    rprint(f"[green]{name} -> {status_name}[/green]")


@app.command()
def run(
    campaign: str = typer.Option(..., "--campaign", "-c"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan + log, but don't place real calls"),
    once: bool = typer.Option(False, "--once", help="Do a single dialing pass and exit (good for cron)"),
) -> None:
    """Run the dialer worker for a campaign (Ctrl-C to stop)."""
    from .db.base import CampaignStatus
    from .db.session import init_db, session_scope
    from .dialer import CampaignService, DialerWorker

    init_db()
    # Auto-start the campaign so a fresh import can dial immediately.
    with session_scope() as s:
        svc = CampaignService(s)
        if svc.get(campaign) is None:
            rprint(f"[red]No such campaign:[/red] {campaign}")
            raise typer.Exit(1)
        svc.set_status(campaign, CampaignStatus.RUNNING)

    worker = DialerWorker(campaign, dry_run=dry_run)
    try:
        asyncio.run(worker.run(once=once))
    except KeyboardInterrupt:
        rprint("\n[yellow]Stopping dialer...[/yellow]")
        worker.stop()


@app.command()
def plan(campaign: str = typer.Option(..., "--campaign", "-c")) -> None:
    """Preview who would be dialed right now (compliance-gated), placing no calls."""
    from .db.session import init_db, session_scope
    from .dialer import CampaignService
    from .dialer.scheduler import plan_next_dials

    init_db()
    with session_scope() as s:
        camp = CampaignService(s).get(campaign)
        if camp is None:
            rprint(f"[red]No such campaign:[/red] {campaign}")
            raise typer.Exit(1)
        p = plan_next_dials(s, camp.id, free_slots=settings.max_concurrent_calls)
        rprint(f"[bold]{campaign}[/bold] dial plan now "
               f"({settings.max_concurrent_calls} slots, window "
               f"{settings.call_window_start_hour}:00-{settings.call_window_end_hour}:00 local)")

        t = Table("Would dial now", "timezone")
        for lead in p.to_dial:
            t.add_row(f"{lead.phone}  {lead.business_name or ''}", lead.timezone or "?")
        rprint(t if p.to_dial else "[dim]nothing dialable right now[/dim]")

        if p.deferred:
            t2 = Table("Deferred", "eligible at (UTC)", "why")
            for lead, until, why in p.deferred:
                t2.add_row(lead.phone, until.isoformat() if until else "?", why[:50])
            rprint(t2)
        if p.blocked:
            t3 = Table("Blocked", "why")
            for lead, why in p.blocked:
                t3.add_row(lead.phone, why[:70])
            rprint(t3)


@app.command()
def report(campaign: str = typer.Option(..., "--campaign", "-c")) -> None:
    """Show campaign statistics."""
    from .db.session import init_db, session_scope
    from .dialer import CampaignService

    init_db()
    with session_scope() as s:
        data = CampaignService(s).report(campaign)
    if not data:
        rprint(f"[red]No such campaign:[/red] {campaign}")
        raise typer.Exit(1)

    rprint(f"[bold]{data['campaign']}[/bold] ({data['status']}) — "
           f"{data['total_leads']} leads, [green]{data['meetings_booked']} meetings booked[/green]")
    t = Table("Lead status", "Count")
    for k, v in sorted(data["leads_by_status"].items()):
        t.add_row(k, str(v))
    rprint(t)
    t2 = Table("Call outcome", "Count")
    for k, v in sorted(data["call_outcomes"].items()):
        t2.add_row(k, str(v))
    rprint(t2)

    f = data.get("funnel", {})
    if f:
        rprint(
            f"\n[bold]Funnel[/bold]: {f['dials']} dials → {f['connected']} connected "
            f"([cyan]{f['connect_rate_pct']}%[/cyan]) → {f['conversations']} conversations "
            f"([cyan]{f['conversation_rate_pct']}%[/cyan]) → {f['meetings']} meetings "
            f"([green]{f['meeting_rate_pct']}%[/green])"
        )
    by_opener = data.get("by_opener", {})
    if by_opener:
        t3 = Table("Opener (best first)", "Calls", "Meetings", "Meeting %")
        for oid, d in sorted(
            by_opener.items(), key=lambda kv: kv[1]["meeting_rate_pct"], reverse=True
        ):
            t3.add_row(oid, str(d["calls"]), str(d["meetings"]), f"{d['meeting_rate_pct']}%")
        rprint(t3)


@app.command()
def check(phone: str = typer.Option(..., "--phone", "-p")) -> None:
    """Preview the compliance decision for a number's first matching lead."""
    from sqlalchemy import select

    from .compliance import ComplianceEngine
    from .compliance.geo import normalize_e164, state_for_number, timezone_for_number
    from .db.models import Lead
    from .db.session import init_db, session_scope

    init_db()
    e164 = normalize_e164(phone) or phone
    rprint(f"Number: {e164}  tz={timezone_for_number(e164)}  state={state_for_number(e164)}")
    with session_scope() as s:
        lead = s.execute(select(Lead).where(Lead.phone == e164)).scalars().first()
        if lead is None:
            rprint("[yellow]No lead with that number; import it to evaluate fully.[/yellow]")
            return
        decision = ComplianceEngine(s).evaluate(lead)
        color = "green" if decision.allowed else "red"
        rprint(f"[{color}]allowed={decision.allowed}[/{color}]")
        for r in decision.reasons:
            rprint(f"  - {r}")
        if decision.retry_after_utc:
            rprint(f"  retry after: {decision.retry_after_utc.isoformat()}")


@app.command()
def persona() -> None:
    """Print the system prompt + a sample opening line the bot will use."""
    from .voice.persona import CallContext, build_opening_line, build_system_prompt

    ctx = CallContext(business_name="Acme Plumbing", industry="plumbing", city="Minneapolis", state="MN")
    rprint("[bold]SAMPLE OPENING LINE[/bold]")
    rprint(build_opening_line(ctx))
    rprint("\n[bold]SYSTEM PROMPT[/bold]")
    rprint(build_system_prompt(ctx))


@app.command()
def openers(industry: str = typer.Option("painting", "--industry", "-i")) -> None:
    """Preview the full opener library rendered for a sample lead."""
    from .voice.openers import OPENERS, render
    from .voice.persona import CallContext

    ctx = CallContext(industry=industry, city="Minneapolis", state="MN")
    rprint(f"[bold]Opener library[/bold] (style='{settings.opener_style}', "
           f"industry='{industry}') — {len(OPENERS)} openers\n")
    for o in OPENERS:
        rprint(f"[bold cyan]{o.id}[/bold cyan] [dim]({o.style})[/dim]")
        rprint(f"  \"{render(o, ctx)}\"")
        rprint(f"  [dim]{o.note}[/dim]\n")


@app.command()
def call(
    to: str = typer.Option(..., "--to", help="Number to call in E.164 (use a number you OWN to test)"),
    campaign: str = typer.Option("_test", "--campaign", "-c"),
    i_own_this_number: bool = typer.Option(
        False,
        "--i-own-this-number",
        help="Record a self-test consent so compliance passes (ONLY for numbers you own/control)",
    ),
) -> None:
    """Place ONE real outbound call to hear the bot end-to-end.

    Requires `coldy serve` running, COLDY_PUBLIC_BASE_URL reachable by Twilio, and
    Anthropic/Deepgram/Cartesia/Twilio keys. This places a REAL call (costs money).
    """
    import os

    from sqlalchemy import select

    from .compliance import ComplianceEngine
    from .compliance.geo import is_mobile, normalize_e164, state_for_number, timezone_for_number
    from .db.base import CallStatus, ConsentType, LeadStatus
    from .db.models import Call, ConsentRecord, Lead
    from .db.session import init_db, session_scope
    from .dialer import CampaignService

    init_db()
    e164 = normalize_e164(to)
    if not e164:
        rprint(f"[red]Invalid number:[/red] {to}")
        raise typer.Exit(1)

    # Pre-flight: fail fast if anything needed for a live call is missing.
    missing = [
        k for k in (
            "ANTHROPIC_API_KEY", "DEEPGRAM_API_KEY", "CARTESIA_API_KEY",
            "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN",
        ) if not os.getenv(k)
    ]
    if missing:
        rprint(f"[red]Missing keys:[/red] {', '.join(missing)} (set them in .env)")
        raise typer.Exit(1)
    if not settings.twilio_from_number:
        rprint("[red]COLDY_TWILIO_FROM_NUMBER is not set.[/red]")
        raise typer.Exit(1)
    if not settings.public_base_url.startswith("http"):
        rprint("[red]COLDY_PUBLIC_BASE_URL is not set[/red] — Twilio must reach your server.")
        raise typer.Exit(1)

    with session_scope() as s:
        svc = CampaignService(s)
        camp = svc.get(campaign) or svc.create(campaign, "End-to-end test call.")
        lead = s.execute(
            select(Lead).where(Lead.phone == e164, Lead.campaign_id == camp.id)
        ).scalars().first()
        if lead is None:
            lead = Lead(
                campaign_id=camp.id, phone=e164, status=LeadStatus.NEW,
                state=state_for_number(e164), timezone=timezone_for_number(e164),
                is_mobile=is_mobile(e164),
            )
            s.add(lead)
            s.flush()
        if i_own_this_number:
            rprint("[yellow]Recording a self-test consent — only valid for numbers you own.[/yellow]")
            s.add(ConsentRecord(
                lead_id=lead.id, consent_type=ConsentType.EXPRESS_WRITTEN,
                source="self-test (--i-own-this-number)",
            ))
            s.flush()
            s.refresh(lead)

        decision = ComplianceEngine(s).evaluate(lead)
        if not decision.allowed:
            rprint(f"[red]Blocked by compliance:[/red] {'; '.join(decision.reasons)}")
            rprint("[yellow]Self-test? re-run with --i-own-this-number (numbers you own only).[/yellow]")
            raise typer.Exit(1)

        call_row = Call(
            lead_id=lead.id, campaign_id=camp.id, to_number=e164,
            from_number=settings.twilio_from_number, status=CallStatus.INITIATED,
        )
        s.add(call_row)
        s.flush()
        lead.status = LeadStatus.CALLING
        lead.attempts += 1
        call_id, lead_id = call_row.id, lead.id

    from .telephony import TwilioTelephony

    sid = TwilioTelephony().place_call(to_number=e164, call_id=call_id, lead_id=lead_id)
    rprint(f"[green]Calling {e164}[/green] — Twilio SID {sid}.")
    rprint("Make sure `coldy serve` is running and reachable at COLDY_PUBLIC_BASE_URL.")


@app.command()
def numbers(
    to: str = typer.Option("", "--to", help="Show which from-number would be picked for this destination"),
) -> None:
    """Show the caller-ID pool, today's usage, and local-presence selection."""
    from .compliance.geo import area_code, normalize_e164, state_for_number
    from .db.session import init_db, session_scope
    from .telephony import NumberPool

    init_db()
    pool = NumberPool()
    if not pool.numbers:
        rprint("[yellow]No from-numbers configured.[/yellow] Set COLDY_FROM_NUMBERS "
               "(comma-separated) or COLDY_TWILIO_FROM_NUMBER.")
        raise typer.Exit(1)

    with session_scope() as s:
        usage = pool.usage_today(s)
        t = Table("From number", "Area", "State", "Used today", "Cap")
        for n in pool.numbers:
            t.add_row(n, area_code(n) or "?", state_for_number(n) or "?",
                      str(usage.get(n, 0)), str(settings.per_number_daily_cap))
        rprint(t)
        if to:
            e164 = normalize_e164(to) or to
            pick = pool.pick(s, e164)
            rprint(f"\nFor [bold]{e164}[/bold] (area {area_code(e164)}, "
                   f"{state_for_number(e164)}): would call from [green]{pick}[/green]")


@app.command()
def serve() -> None:
    """Run the FastAPI webhook/media server."""
    import uvicorn

    uvicorn.run(
        "coldy.api.app:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


@app.command()
def doctor() -> None:
    """Check configuration and required credentials."""
    import os

    checks = [
        ("ANTHROPIC_API_KEY", bool(os.getenv("ANTHROPIC_API_KEY"))),
        ("DEEPGRAM_API_KEY", bool(os.getenv("DEEPGRAM_API_KEY"))),
        ("CARTESIA_API_KEY", bool(os.getenv("CARTESIA_API_KEY"))),
        ("TWILIO_ACCOUNT_SID", bool(os.getenv("TWILIO_ACCOUNT_SID"))),
        ("TWILIO_AUTH_TOKEN", bool(os.getenv("TWILIO_AUTH_TOKEN"))),
        ("COLDY_TWILIO_FROM_NUMBER", bool(settings.twilio_from_number)),
        ("COLDY_PUBLIC_BASE_URL set", settings.public_base_url.startswith("http")),
    ]
    t = Table("Check", "OK")
    for name, ok in checks:
        t.add_row(name, "[green]yes[/green]" if ok else "[red]no[/red]")
    rprint(t)
    rprint(f"LLM model: [bold]{settings.llm_model}[/bold]  "
           f"written-consent required: [bold]{settings.require_written_consent}[/bold]  "
           f"window: {settings.call_window_start_hour}:00-{settings.call_window_end_hour}:00")


if __name__ == "__main__":
    app()
