"""Live dashboard: a self-contained web UI over the funnel + per-opener stats.

  GET /dashboard          -> the HTML page (auto-refreshes)
  GET /api/campaigns      -> [{name, status}]
  GET /api/report/{name}  -> the full report (funnel, by_opener, outcomes, ...)
  GET /api/calls/{name}   -> recent calls

NOTE: these endpoints are unauthenticated. Put the app behind auth / a private
network before exposing the dashboard publicly.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from ...db.session import session_scope
from ...dialer import CampaignService

router = APIRouter()


@router.get("/api/campaigns")
def api_campaigns() -> list[dict]:
    with session_scope() as s:
        return CampaignService(s).list_campaigns()


@router.get("/api/report/{name}")
def api_report(name: str) -> dict:
    with session_scope() as s:
        return CampaignService(s).report(name) or {}


@router.get("/api/calls/{name}")
def api_calls(name: str, limit: int = 25) -> list[dict]:
    with session_scope() as s:
        svc = CampaignService(s)
        camp = svc.get(name)
        return svc.recent_calls(camp.id, limit) if camp else []


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    return _HTML


_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Coldy — Live Dashboard</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; font: 14px/1.5 -apple-system, Segoe UI, Roboto, sans-serif;
         background:#0e1116; color:#e6edf3; }
  header { padding:16px 24px; border-bottom:1px solid #222b36; display:flex;
           align-items:center; gap:16px; position:sticky; top:0; background:#0e1116; }
  h1 { font-size:18px; margin:0; font-weight:650; }
  h1 span { color:#6ea8fe; }
  select { background:#161b22; color:#e6edf3; border:1px solid #30363d;
           border-radius:8px; padding:7px 10px; font-size:14px; }
  .muted { color:#8b949e; }
  main { padding:24px; max-width:1100px; margin:0 auto; }
  .cards { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:20px; }
  .card { background:#161b22; border:1px solid #21262d; border-radius:12px; padding:16px; }
  .card .n { font-size:28px; font-weight:700; }
  .card .l { color:#8b949e; font-size:12px; text-transform:uppercase; letter-spacing:.04em; }
  .card .pct { color:#3fb950; font-size:13px; }
  .funnel { display:flex; gap:8px; align-items:stretch; margin-bottom:24px; }
  .stage { flex:1; background:#161b22; border:1px solid #21262d; border-radius:10px;
           padding:14px; text-align:center; }
  .stage .v { font-size:22px; font-weight:700; } .stage .s { color:#8b949e; font-size:12px; }
  .stage .r { color:#6ea8fe; font-size:12px; }
  h2 { font-size:14px; text-transform:uppercase; letter-spacing:.04em; color:#8b949e; margin:24px 0 10px; }
  table { width:100%; border-collapse:collapse; background:#161b22; border-radius:12px; overflow:hidden; }
  th,td { text-align:left; padding:9px 12px; border-bottom:1px solid #21262d; font-variant-numeric:tabular-nums; }
  th { color:#8b949e; font-weight:600; font-size:12px; text-transform:uppercase; }
  tr:last-child td { border-bottom:none; }
  .pill { padding:2px 8px; border-radius:999px; font-size:12px; background:#21262d; }
  .pill.win { background:#10331d; color:#3fb950; } .pill.bad { background:#3a1d1d; color:#f85149; }
  .bar { height:6px; background:#21262d; border-radius:4px; overflow:hidden; margin-top:6px; }
  .bar>i { display:block; height:100%; background:#6ea8fe; }
</style>
</head>
<body>
<header>
  <h1>Cold<span>y</span> · live dashboard</h1>
  <select id="campaign"></select>
  <span class="muted" id="updated"></span>
</header>
<main>
  <div class="cards" id="cards"></div>
  <h2>Funnel</h2>
  <div class="funnel" id="funnel"></div>
  <h2>Openers — A/B (best first)</h2>
  <table id="openers"><thead><tr><th>Opener</th><th>Calls</th><th>Meetings</th><th>Meeting %</th></tr></thead><tbody></tbody></table>
  <h2>Recent calls</h2>
  <table id="calls"><thead><tr><th>When</th><th>Number</th><th>Business</th><th>Dir</th><th>Outcome</th><th>Opener</th><th>Score</th></tr></thead><tbody></tbody></table>
</main>
<script>
const $ = s => document.querySelector(s);
let current = null;

async function loadCampaigns() {
  const cs = await fetch('/api/campaigns').then(r=>r.json());
  const sel = $('#campaign');
  sel.innerHTML = cs.map(c=>`<option value="${c.name}">${c.name} (${c.status})</option>`).join('');
  if (cs.length) { current = current || cs[0].name; sel.value = current; }
  sel.onchange = () => { current = sel.value; refresh(); };
}

function card(n,l,extra='') { return `<div class="card"><div class="l">${l}</div><div class="n">${n}</div>${extra}</div>`; }

async function refresh() {
  if (!current) return;
  const [rep, calls] = await Promise.all([
    fetch('/api/report/'+encodeURIComponent(current)).then(r=>r.json()),
    fetch('/api/calls/'+encodeURIComponent(current)).then(r=>r.json()),
  ]);
  const f = rep.funnel || {};
  $('#cards').innerHTML =
    card(rep.total_leads ?? 0, 'Leads') +
    card(f.dials ?? 0, 'Dials') +
    card(f.conversations ?? 0, 'Conversations') +
    card(rep.meetings_booked ?? 0, 'Meetings', `<div class="pct">${f.meeting_rate_pct ?? 0}% of convos</div>`);

  const stages = [['Dials',f.dials,null],['Connected',f.connected,f.connect_rate_pct],
                  ['Conversations',f.conversations,f.conversation_rate_pct],['Meetings',f.meetings,f.meeting_rate_pct]];
  $('#funnel').innerHTML = stages.map(([s,v,r])=>
    `<div class="stage"><div class="v">${v ?? 0}</div><div class="s">${s}</div>${r!=null?`<div class="r">${r}%</div>`:''}</div>`).join('');

  const ob = rep.by_opener || {};
  const rows = Object.entries(ob).sort((a,b)=>b[1].meeting_rate_pct-a[1].meeting_rate_pct);
  const maxRate = Math.max(1, ...rows.map(r=>r[1].meeting_rate_pct));
  $('#openers tbody').innerHTML = rows.map(([id,d])=>
    `<tr><td>${id}</td><td>${d.calls}</td><td>${d.meetings}</td>
     <td>${d.meeting_rate_pct}%<div class="bar"><i style="width:${100*d.meeting_rate_pct/maxRate}%"></i></div></td></tr>`).join('')
     || '<tr><td colspan="4" class="muted">No calls yet.</td></tr>';

  const win = o => ['meeting_booked','interested','transferred'].includes(o);
  const bad = o => ['not_interested','opted_out','no_answer'].includes(o);
  $('#calls tbody').innerHTML = calls.map(c=>{
    const cls = win(c.outcome)?'win':(bad(c.outcome)?'bad':'');
    const t = c.started_at ? new Date(c.started_at).toLocaleString() : '';
    return `<tr><td class="muted">${t}</td><td>${c.phone}</td><td>${c.business||''}</td>
      <td>${c.direction}</td><td><span class="pill ${cls}">${c.outcome}</span></td>
      <td>${c.opener||''}</td><td>${c.score??''}</td></tr>`;
  }).join('') || '<tr><td colspan="7" class="muted">No calls yet.</td></tr>';

  $('#updated').textContent = 'updated ' + new Date().toLocaleTimeString();
}

(async () => { await loadCampaigns(); await refresh(); setInterval(refresh, 5000); })();
</script>
</body>
</html>"""
