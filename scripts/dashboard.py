#!/usr/bin/env python3
"""Build the job-application dashboard artifact.

Reads the local store and emits a single self-contained HTML file. The purpose
is to let someone who has been away act on a working session in a couple of
minutes: what needs them, what referrals are available, what already went out.

The "Needs you" section leads because it is the only part that is blocking.
Every blocked item carries a direct link to the exact page so acting on it is
one click plus one action, not a hunt through tabs.

Standard library only. No network calls; the page is fully offline.
"""

import argparse
import html
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def root_dir(override=None):
    if override:
        return Path(override).expanduser()
    return Path(os.environ.get("JOB_APPLICATION_DIR", "~/.job-application")).expanduser()


def read_json(path, default):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return default


def load_state(root):
    sessions = []
    sdir = root / "sessions"
    if sdir.exists():
        for f in sorted(sdir.glob("*.json")):
            data = read_json(f, {})
            if data:
                sessions.append(data)

    history = []
    hpath = root / "applications.jsonl"
    if hpath.exists():
        for line in hpath.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    history.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    latest = {}
    for e in history:
        key = e.get("applicationId") or f"{e.get('company')}|{e.get('role')}"
        latest[key] = e

    return {
        "profile": read_json(root / "profile.json", {}),
        "sessions": sessions,
        "history": list(latest.values()),
    }


def esc(v):
    return html.escape(str(v if v is not None else ""))


def link(url, label="Open"):
    if not url:
        return '<span class="muted">no link</span>'
    return f'<a class="go" href="{esc(url)}" target="_blank" rel="noopener">{esc(label)} &nearr;</a>'


def render_pending(fields):
    if not fields:
        return '<li class="done">Nothing outstanding &mdash; ready to submit</li>'
    out = []
    for f in fields:
        q = esc(f.get("question", "Unknown field"))
        reason = f.get("reason") or f.get("state") or ""
        why = f' <span class="why">{esc(reason)}</span>' if reason else ""
        out.append(f"<li>{q}{why}</li>")
    return "\n".join(out)


def build(state, generated):
    sessions = state["sessions"]
    history = state["history"]
    profile = state["profile"]

    blocked = [s for s in sessions if s.get("status") in ("active", "review")]
    blocked.sort(key=lambda s: len(s.get("pendingFields", [])))

    referrals = [s for s in sessions if s.get("referral")]
    watch = [s for s in sessions if s.get("status") == "watch"]
    submitted = [e for e in history if e.get("event") == "completed"]
    reviewed_only = {
        (e.get("company"), e.get("role"))
        for e in history
        if e.get("event") == "reviewed"
    } - {(e.get("company"), e.get("role")) for e in submitted}

    name = profile.get("firstName") or "there"

    cards = []
    for s in blocked:
        pending = s.get("pendingFields", [])
        badge = "ready" if not pending else f"{len(pending)} to do"
        cls = "ready" if not pending else "hold"
        chip = "ready" if not pending else "hold"
        cards.append(f"""
        <article class="card {cls}">
          <header>
            <div>
              <h3>{esc(s.get('company', 'Unknown'))}</h3>
              <p class="role">{esc(s.get('role', ''))}</p>
            </div>
            <span class="chip {chip}">{esc(badge)}</span>
          </header>
          <ul class="todo">{render_pending(pending)}</ul>
          <footer>
            <span class="ats">{esc(s.get('ats', ''))}</span>
            {link(s.get('url'), 'Open application')}
          </footer>
        </article>""")

    ref_cards = []
    for s in referrals:
        r = s.get("referral", {})
        msg = r.get("message", "")
        ref_cards.append(f"""
        <article class="card ref">
          <header>
            <div>
              <h3>{esc(s.get('company', ''))}</h3>
              <p class="role">{esc(s.get('role', ''))}</p>
            </div>
            <span class="chip warm">{esc(r.get('degree', 'connection'))}</span>
          </header>
          <p class="contact"><strong>{esc(r.get('name', ''))}</strong>
             <span>{esc(r.get('title', ''))}</span></p>
          {f'<div class="msg"><pre>{esc(msg)}</pre><button class="copy" data-msg="{esc(msg)}">Copy message</button></div>' if msg else ''}
          <footer>{link(r.get('profileUrl'), 'Message them')}{link(s.get('url'), 'Open role')}</footer>
        </article>""")

    sub_rows = "\n".join(
        f"<tr><td>{esc(e.get('company'))}</td><td>{esc(e.get('role'))}</td>"
        f"<td class='when'>{esc((e.get('at') or '')[:10])}</td></tr>"
        for e in sorted(submitted, key=lambda x: x.get("at", ""), reverse=True)
    ) or "<tr><td colspan='3' class='muted'>Nothing submitted yet</td></tr>"

    unconfirmed = "".join(
        f"<li>{esc(c)} &mdash; {esc(r)}</li>" for c, r in sorted(reviewed_only) if c
    )
    unconfirmed_block = f"""
      <section class="note">
        <h2>Not confirmed submitted</h2>
        <p>These reached final review but no submission was observed. Worth checking before reapplying.</p>
        <ul>{unconfirmed}</ul>
      </section>""" if unconfirmed else ""

    watch_rows = "\n".join(
        f"<tr><td>{esc(s.get('company'))}</td><td>{esc(s.get('role'))}</td>"
        f"<td>{link(s.get('url'))}</td></tr>" for s in watch
    )
    watch_block = f"""
      <section>
        <h2>Watch list</h2>
        <div class="panel"><div class="tablewrap"><table><thead><tr><th>Company</th><th>Role</th><th></th></tr></thead>
        <tbody>{watch_rows}</tbody></table></div></div>
      </section>""" if watch else ""

    total_todo = sum(len(s.get("pendingFields", [])) for s in blocked)

    return f"""<title>Application Board</title>
<style>
  :root {{
    color-scheme: light dark;
    --bg:#f5f5f7; --card:#ffffff; --card-2:#fbfbfd;
    --ink:#1d1d1f; --ink-2:#6e6e73; --ink-3:#86868b;
    --hair:rgba(0,0,0,.08); --hair-2:rgba(0,0,0,.04);
    --blue:#0071e3; --orange:#c2410c; --green:#047857; --purple:#6d28d9;
    --tint-o:rgba(234,88,12,.07); --tint-g:rgba(5,150,105,.07); --tint-p:rgba(109,40,217,.06);
    --shadow:0 1px 2px rgba(0,0,0,.04), 0 4px 16px rgba(0,0,0,.05);
    --shadow-2:0 1px 2px rgba(0,0,0,.05), 0 8px 28px rgba(0,0,0,.07);
  }}
  @media (prefers-color-scheme:dark) {{
    :root:not([data-theme="light"]) {{
      --bg:#000000; --card:#1c1c1e; --card-2:#161618;
      --ink:#f5f5f7; --ink-2:#a1a1a6; --ink-3:#8a8a8e;
      --hair:rgba(255,255,255,.12); --hair-2:rgba(255,255,255,.06);
      --blue:#0a84ff; --orange:#ff9f0a; --green:#30d158; --purple:#bf5af2;
      --tint-o:rgba(255,159,10,.10); --tint-g:rgba(48,209,88,.09); --tint-p:rgba(191,90,242,.09);
      --shadow:0 1px 2px rgba(0,0,0,.4); --shadow-2:0 2px 12px rgba(0,0,0,.5);
    }}
  }}
  :root[data-theme="dark"] {{
    --bg:#000000; --card:#1c1c1e; --card-2:#161618;
    --ink:#f5f5f7; --ink-2:#a1a1a6; --ink-3:#8a8a8e;
    --hair:rgba(255,255,255,.12); --hair-2:rgba(255,255,255,.06);
    --blue:#0a84ff; --orange:#ff9f0a; --green:#30d158; --purple:#bf5af2;
    --tint-o:rgba(255,159,10,.10); --tint-g:rgba(48,209,88,.09); --tint-p:rgba(191,90,242,.09);
    --shadow:0 1px 2px rgba(0,0,0,.4); --shadow-2:0 2px 12px rgba(0,0,0,.5);
  }}

  *,*::before,*::after {{ box-sizing:border-box; }}
  html {{ -webkit-text-size-adjust:100%; }}
  body {{
    margin:0; background:var(--bg); color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","SF Pro Display",
      "Helvetica Neue",Inter,system-ui,sans-serif;
    font-size:17px; line-height:1.47059; letter-spacing:-.022em;
    -webkit-font-smoothing:antialiased; -moz-osx-font-smoothing:grayscale;
  }}
  .wrap {{ max-width:980px; margin:0 auto; padding:clamp(2.5rem,7vw,5rem) 1.5rem 7rem; }}

  .hero {{ margin-bottom:3.5rem; }}
  h1 {{ font-size:clamp(2.4rem,6vw,3.4rem); font-weight:700; letter-spacing:-.035em;
    line-height:1.05; margin:0 0 .6rem; text-wrap:balance; }}
  .lede {{ font-size:1.24rem; color:var(--ink-2); margin:0; letter-spacing:-.019em;
    line-height:1.38; max-width:34ch; text-wrap:balance; }}
  .lede b {{ color:var(--ink); font-weight:600; }}
  .stamp {{ font-size:.82rem; color:var(--ink-3); margin:1.4rem 0 0; letter-spacing:-.01em;
    font-variant-numeric:tabular-nums; }}

  .tally {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(126px,1fr));
    gap:.75rem; margin:2.5rem 0 3.75rem; }}
  .stat {{ background:var(--card); border-radius:18px; padding:1.15rem 1.25rem;
    box-shadow:var(--shadow); }}
  .stat b {{ display:block; font-size:2.05rem; font-weight:600; line-height:1;
    letter-spacing:-.04em; font-variant-numeric:tabular-nums; margin-bottom:.3rem; }}
  .stat span {{ font-size:.8rem; color:var(--ink-2); letter-spacing:-.01em; }}
  .stat.lead b {{ color:var(--orange); }}

  h2 {{ font-size:1.55rem; font-weight:650; letter-spacing:-.028em; margin:0 0 .35rem; }}
  .sectionnote {{ color:var(--ink-2); font-size:.98rem; margin:0 0 1.5rem; letter-spacing:-.015em; }}
  section {{ margin-bottom:4rem; }}

  .grid {{ display:grid; gap:1rem; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); }}

  .card {{ background:var(--card); border-radius:20px; padding:1.4rem 1.5rem 1.25rem;
    box-shadow:var(--shadow); display:flex; flex-direction:column; gap:1rem;
    transition:box-shadow .25s cubic-bezier(.4,0,.2,1), transform .25s cubic-bezier(.4,0,.2,1); }}
  .card:hover {{ box-shadow:var(--shadow-2); transform:translateY(-1px); }}
  .card.hold {{ background:linear-gradient(var(--tint-o),var(--tint-o)),var(--card); }}
  .card.ready {{ background:linear-gradient(var(--tint-g),var(--tint-g)),var(--card); }}
  .card.ref {{ background:linear-gradient(var(--tint-p),var(--tint-p)),var(--card); }}

  .card header {{ display:flex; justify-content:space-between; gap:.9rem; align-items:flex-start; }}
  .card h3 {{ margin:0; font-size:1.13rem; font-weight:620; letter-spacing:-.022em; line-height:1.25; }}
  .role {{ margin:.22rem 0 0; color:var(--ink-2); font-size:.93rem; letter-spacing:-.014em;
    line-height:1.35; }}

  .chip {{ font-size:.735rem; font-weight:590; padding:.28rem .62rem; border-radius:100px;
    white-space:nowrap; letter-spacing:-.008em; font-variant-numeric:tabular-nums; }}
  .chip.hold {{ color:var(--orange); background:var(--tint-o); }}
  .chip.ready {{ color:var(--green); background:var(--tint-g); }}
  .chip.warm {{ color:var(--purple); background:var(--tint-p); }}

  ul.todo {{ margin:0; padding:0; list-style:none; display:flex; flex-direction:column; gap:.5rem; }}
  ul.todo li {{ font-size:.93rem; line-height:1.38; letter-spacing:-.014em;
    padding-left:1.3rem; position:relative; }}
  ul.todo li::before {{ content:""; position:absolute; left:.28rem; top:.52em;
    width:6px; height:6px; border-radius:50%; background:var(--orange); opacity:.85; }}
  ul.todo li.done {{ padding-left:1.3rem; color:var(--green); font-weight:550; }}
  ul.todo li.done::before {{ content:"\\2713"; background:none; width:auto; height:auto;
    left:0; top:0; font-size:.95rem; font-weight:700; opacity:1; }}
  .why {{ color:var(--ink-2); }}
  .why::before {{ content:" \\2014 "; }}

  .card footer {{ display:flex; justify-content:space-between; align-items:center;
    gap:.75rem; flex-wrap:wrap; border-top:1px solid var(--hair-2);
    padding-top:.95rem; margin-top:auto; }}
  .ats {{ color:var(--ink-3); font-size:.79rem; letter-spacing:-.008em; }}

  a.go {{ color:var(--blue); font-weight:520; text-decoration:none; font-size:.93rem;
    letter-spacing:-.016em; border-radius:8px; padding:.2rem .1rem; }}
  a.go:hover {{ text-decoration:underline; text-underline-offset:2px; }}
  a.go:focus-visible, button:focus-visible {{ outline:3px solid var(--blue);
    outline-offset:3px; border-radius:8px; }}

  .contact {{ margin:0; font-size:.95rem; letter-spacing:-.015em; line-height:1.4; }}
  .contact strong {{ font-weight:600; }}
  .contact span {{ display:block; color:var(--ink-2); font-size:.88rem; margin-top:.1rem; }}
  .msg {{ display:flex; flex-direction:column; gap:.8rem; align-items:flex-start; }}
  .msg pre {{ background:var(--card-2); border-radius:12px; padding:.9rem 1rem;
    font-family:inherit; font-size:.875rem; line-height:1.5; letter-spacing:-.012em;
    white-space:pre-wrap; margin:0; max-height:142px; overflow:auto; width:100%;
    color:var(--ink-2); box-shadow:inset 0 0 0 1px var(--hair-2); }}
  button.copy {{ background:var(--blue); border:none; color:#fff; border-radius:100px;
    padding:.5rem 1.1rem; font:inherit; font-size:.875rem; font-weight:520;
    letter-spacing:-.014em; cursor:pointer;
    transition:opacity .2s, transform .12s; }}
  button.copy:hover {{ opacity:.86; }}
  button.copy:active {{ transform:scale(.97); }}
  button.copy[data-done] {{ background:var(--green); }}

  .panel {{ background:var(--card); border-radius:20px; box-shadow:var(--shadow);
    overflow:hidden; }}
  .tablewrap {{ overflow-x:auto; }}
  table {{ width:100%; border-collapse:collapse; font-size:.95rem; letter-spacing:-.015em; }}
  th {{ text-align:left; font-size:.79rem; color:var(--ink-3); font-weight:510;
    padding:.95rem 1.5rem; border-bottom:1px solid var(--hair); white-space:nowrap;
    letter-spacing:-.008em; }}
  td {{ padding:.92rem 1.5rem; border-bottom:1px solid var(--hair-2); }}
  tr:last-child td {{ border-bottom:none; }}
  td.when {{ color:var(--ink-3); font-variant-numeric:tabular-nums; white-space:nowrap; }}

  .note {{ background:linear-gradient(var(--tint-o),var(--tint-o)),var(--card);
    border-radius:20px; padding:1.5rem 1.6rem; box-shadow:var(--shadow); }}
  .note h2 {{ font-size:1.2rem; margin-bottom:.35rem; }}
  .note p {{ margin:0 0 .9rem; font-size:.95rem; color:var(--ink-2); letter-spacing:-.015em; }}
  .note ul {{ margin:0; padding:0; list-style:none; display:flex; flex-direction:column; gap:.4rem; }}
  .note li {{ font-size:.95rem; letter-spacing:-.015em; }}

  .empty {{ color:var(--ink-2); font-size:1.05rem; padding:3rem 1.5rem; text-align:center;
    background:var(--card); border-radius:20px; box-shadow:var(--shadow); letter-spacing:-.018em; }}
  .muted {{ color:var(--ink-3); }}
  @media (prefers-reduced-motion:reduce) {{ *,*::before,*::after {{
    transition:none !important; animation:none !important; }} }}
  @media (max-width:600px) {{
    body {{ font-size:16px; }}
    .grid {{ grid-template-columns:1fr; }}
    th, td {{ padding-left:1.15rem; padding-right:1.15rem; }}
  }}
</style>

<div class="wrap">
  <header class="hero">
    <h1>Application board</h1>
    <p class="lede"><b>{len(blocked)} application{'' if len(blocked)==1 else 's'}</b> {'is' if len(blocked)==1 else 'are'} waiting on you.
       {f'{len(referrals)} referral{"" if len(referrals)==1 else "s"} ready to send.' if referrals else ''}</p>
    <p class="stamp">{esc(name)} &middot; updated {esc(generated)}</p>
  </header>

  <div class="tally">
    <div class="stat lead"><b>{len(blocked)}</b><span>Need you</span></div>
    <div class="stat"><b>{total_todo}</b><span>Open items</span></div>
    <div class="stat"><b>{len(referrals)}</b><span>Referrals</span></div>
    <div class="stat"><b>{len(submitted)}</b><span>Submitted</span></div>
  </div>

  <section>
    <h2>Needs you</h2>
    <p class="sectionnote">Each one opens straight to the page where it is blocked.</p>
    {f'<div class="grid">{"".join(cards)}</div>' if cards
     else '<p class="empty">Nothing is blocked right now.</p>'}
  </section>

  {f'''<section><h2>Referrals worth sending</h2>
    <p class="sectionnote">A referral moves the odds more than another application does.</p>
    <div class="grid">{"".join(ref_cards)}</div></section>''' if ref_cards else ''}

  {unconfirmed_block}

  <section>
    <h2>Submitted</h2>
    <p class="sectionnote">Already out. Check here before applying again.</p>
    <div class="panel"><div class="tablewrap"><table>
      <thead><tr><th>Company</th><th>Role</th><th>When</th></tr></thead>
      <tbody>{sub_rows}</tbody>
    </table></div></div>
  </section>

  {watch_block}
</div>

<script>
  document.querySelectorAll('button.copy').forEach(function (b) {{
    b.addEventListener('click', function () {{
      navigator.clipboard.writeText(b.dataset.msg).then(function () {{
        var t = b.textContent;
        b.textContent = 'Copied'; b.dataset.done = '1';
        setTimeout(function () {{ b.textContent = t; delete b.dataset.done; }}, 1600);
      }});
    }});
  }});
</script>
"""


def main():
    ap = argparse.ArgumentParser(description="Build the job-application dashboard.")
    ap.add_argument("--out", required=True, help="output HTML path")
    ap.add_argument("--root", help="store directory")
    args = ap.parse_args()

    root = root_dir(args.root)
    if not root.exists():
        print("job-application dashboard: no store found; run store.py init first", file=sys.stderr)
        return 2

    state = load_state(root)
    generated = datetime.now(timezone.utc).astimezone().strftime("%d %b %Y, %H:%M")
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(state, generated))

    print(json.dumps({
        "written": str(out),
        "blocked": len([s for s in state["sessions"] if s.get("status") in ("active", "review")]),
        "referrals": len([s for s in state["sessions"] if s.get("referral")]),
        "submitted": len([e for e in state["history"] if e.get("event") == "completed"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
