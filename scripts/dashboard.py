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


def safe_url(url):
    """URLs come from scraped pages; only http(s) may become a clickable link."""
    u = str(url or "").strip()
    return u if u.startswith(("https://", "http://")) else ""


def link(url, label="Open"):
    url = safe_url(url)
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
    # An application whose latest event is a post-submission outcome is still
    # submitted; it must not vanish from the board when an outcome is logged.
    OUTCOMES = ("response", "interview", "offer", "rejected")
    submitted = [e for e in history if e.get("event") in ("completed",) + OUTCOMES]
    # "reviewed" never confirmed, plus "submitting" with no completion after it —
    # the latter means a session died mid-submit and the platform must be checked.
    reviewed_only = {
        (e.get("company"), e.get("role"), e.get("event") == "submitting")
        for e in history
        if e.get("event") in ("reviewed", "submitting")
    }
    reviewed_only = {
        (c, r, interrupted) for c, r, interrupted in reviewed_only
        if (c, r) not in {(e.get("company"), e.get("role")) for e in submitted}
    }

    name = profile.get("firstName") or "there"

    cards = []
    for s in blocked:
        pending = s.get("pendingFields", [])
        aid = s.get("applicationId") or f"{s.get('company','')}-{s.get('role','')}"
        badge = "ready" if not pending else f"{len(pending)} to do"
        cls = "ready" if not pending else "hold"
        chip = "ready" if not pending else "hold"
        cards.append(f"""
        <article class="card {cls}" data-id="{esc(aid)}">
          <header>
            <div>
              <h3>{esc(s.get('company', 'Unknown'))}</h3>
              <p class="role">{esc(s.get('role', ''))}</p>
            </div>
            <span class="chip {chip}">{esc(badge)}</span>
          </header>
          <ul class="todo">{render_pending(pending)}</ul>
          <p class="stub">&#10003; Marked submitted <button class="undo" data-id="{esc(aid)}">Undo</button></p>
          <div class="act">
            <a class="btn" href="{esc(safe_url(s.get('url')))}" target="_blank" rel="noopener">Open &amp; finish</a>
            <button class="btn ghost mark" data-id="{esc(aid)}">Mark submitted</button>
            <span class="ats">{esc(s.get('ats', ''))}</span>
          </div>
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
          {f'<div class="msg"><pre>{esc(msg)}</pre></div>' if msg else ''}
          <div class="act">
            {f'<button class="btn copy" data-msg="{esc(msg)}">Copy message</button>' if msg else ''}
            <a class="btn ghost" href="{esc(safe_url(r.get('profileUrl')))}" target="_blank" rel="noopener">Message</a>
          </div>
        </article>""")

    outcome_chip = {"completed": ("", "submitted"), "response": ("warm", "response"),
                    "interview": ("warm", "interview"), "offer": ("ready", "offer"),
                    "rejected": ("", "rejected")}
    def sub_row(e):
        cls, label = outcome_chip.get(e.get("event"), ("", e.get("event")))
        return (f"<tr><td>{esc(e.get('company'))}</td><td>{esc(e.get('role'))}</td>"
                f"<td><span class='chip {cls}'>{esc(label)}</span></td>"
                f"<td class='when'>{esc((e.get('at') or '')[:10])}</td></tr>")

    sub_rows = "\n".join(
        sub_row(e) for e in sorted(submitted, key=lambda x: x.get("at", ""), reverse=True)
    ) or "<tr><td colspan='4' class='muted'>Nothing submitted yet</td></tr>"

    unconfirmed = "".join(
        f"<li>{esc(c)} &mdash; {esc(r)}"
        f"{' <strong>(submission attempted, interrupted before confirmation)</strong>' if interrupted else ''}</li>"
        for c, r, interrupted in sorted(reviewed_only, key=lambda t: (str(t[0]), str(t[1]))) if c
    )
    unconfirmed_block = f"""
      <div class="note">
        <h4>Not confirmed submitted</h4>
        <p>These reached final review or an interrupted submission, but no confirmation was observed. Check on the platform before reapplying.</p>
        <ul>{unconfirmed}</ul>
      </div>""" if unconfirmed else ""

    watch_rows = "\n".join(
        f"<tr><td><strong>{esc(s.get('company'))}</strong><br><span class='muted'>{esc(s.get('role'))}</span></td>"
        f"<td class='note-cell'>{esc(s.get('step',''))}</td>"
        f"<td>{link(s.get('url'), 'View')}</td></tr>" for s in watch
    )


    total_todo = sum(len(s.get("pendingFields", [])) for s in blocked)

    tabs = [
        ("act", "Needs you", len(blocked)),
        ("ref", "Referrals", len(referrals)),
        ("done", "Submitted", len(submitted)),
    ]
    if watch:
        tabs.append(("watch", "Watching", len(watch)))

    tabnav = "".join(
        f'<button class="tab{" on" if i == 0 else ""}" data-tab="{k}" role="tab" '
        f'aria-selected="{"true" if i == 0 else "false"}" aria-controls="p-{k}">'
        f'{esc(label)}<span class="n">{n}</span></button>'
        for i, (k, label, n) in enumerate(tabs)
    )

    return f"""<title>Application Board</title>
<style>
  :root {{
    color-scheme:light dark;
    --bg:#f5f5f7; --card:#fff; --sunk:#f0f0f2; --seg:#e8e8ed;
    --ink:#1d1d1f; --ink-2:#6e6e73; --ink-3:#8e8e93;
    --hair:rgba(0,0,0,.07);
    --blue:#0071e3; --orange:#b45309; --green:#047857; --purple:#6d28d9;
    --t-o:rgba(234,88,12,.08); --t-g:rgba(5,150,105,.08); --t-p:rgba(109,40,217,.07);
    --sh:0 1px 3px rgba(0,0,0,.05), 0 6px 20px rgba(0,0,0,.05);
  }}
  @media (prefers-color-scheme:dark) {{
    :root:not([data-theme="light"]) {{
      --bg:#000; --card:#1c1c1e; --sunk:#2c2c2e; --seg:#2c2c2e;
      --ink:#f5f5f7; --ink-2:#aeaeb2; --ink-3:#8e8e93;
      --hair:rgba(255,255,255,.1);
      --blue:#0a84ff; --orange:#ff9f0a; --green:#30d158; --purple:#bf5af2;
      --t-o:rgba(255,159,10,.13); --t-g:rgba(48,209,88,.12); --t-p:rgba(191,90,242,.12);
      --sh:0 1px 3px rgba(0,0,0,.5);
    }}
  }}
  :root[data-theme="dark"] {{
    --bg:#000; --card:#1c1c1e; --sunk:#2c2c2e; --seg:#2c2c2e;
    --ink:#f5f5f7; --ink-2:#aeaeb2; --ink-3:#8e8e93;
    --hair:rgba(255,255,255,.1);
    --blue:#0a84ff; --orange:#ff9f0a; --green:#30d158; --purple:#bf5af2;
    --t-o:rgba(255,159,10,.13); --t-g:rgba(48,209,88,.12); --t-p:rgba(191,90,242,.12);
    --sh:0 1px 3px rgba(0,0,0,.5);
  }}
  *,*::before,*::after {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",system-ui,sans-serif;
    font-size:17px; line-height:1.47; letter-spacing:-.022em;
    -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:860px; margin:0 auto; padding:clamp(2rem,6vw,4rem) 1.25rem 6rem; }}

  .top {{ text-align:center; margin-bottom:2rem; }}
  h1 {{ font-size:clamp(2rem,5.5vw,2.75rem); font-weight:700; letter-spacing:-.035em;
    line-height:1.07; margin:0 0 .5rem; }}
  .lede {{ font-size:1.1rem; color:var(--ink-2); margin:0; letter-spacing:-.018em; }}
  .stamp {{ font-size:.8rem; color:var(--ink-3); margin:.7rem 0 0;
    font-variant-numeric:tabular-nums; }}

  .segwrap {{ display:flex; justify-content:center; margin-bottom:2.25rem;
    position:sticky; top:.75rem; z-index:5; }}
  .seg {{ display:inline-flex; background:var(--seg); border-radius:100px; padding:3px;
    gap:2px; max-width:100%; overflow-x:auto; scrollbar-width:none; }}
  .seg::-webkit-scrollbar {{ display:none; }}
  .tab {{ border:none; background:none; color:var(--ink-2); font:inherit; font-size:.93rem;
    font-weight:510; letter-spacing:-.015em; padding:.5rem 1.05rem; border-radius:100px;
    cursor:pointer; white-space:nowrap; display:inline-flex; align-items:center; gap:.4rem;
    transition:background .22s cubic-bezier(.4,0,.2,1), color .22s; }}
  .tab .n {{ font-size:.78rem; color:var(--ink-3); font-variant-numeric:tabular-nums;
    background:var(--card); padding:.05rem .38rem; border-radius:100px; min-width:1.35em;
    text-align:center; }}
  .tab.on {{ background:var(--card); color:var(--ink); box-shadow:0 1px 3px rgba(0,0,0,.12); }}
  .tab.on .n {{ background:var(--sunk); color:var(--ink-2); }}
  .tab:focus-visible {{ outline:3px solid var(--blue); outline-offset:2px; }}

  .panel {{ display:none; animation:in .3s cubic-bezier(.4,0,.2,1); }}
  .panel.on {{ display:block; }}
  @keyframes in {{ from {{ opacity:0; transform:translateY(6px); }} to {{ opacity:1; transform:none; }} }}
  .hint {{ text-align:center; color:var(--ink-2); font-size:.95rem; margin:0 0 1.75rem;
    letter-spacing:-.015em; }}

  .grid {{ display:grid; gap:.9rem; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); }}
  .card {{ background:var(--card); border-radius:20px; padding:1.35rem 1.45rem 1.15rem;
    box-shadow:var(--sh); display:flex; flex-direction:column; gap:.95rem; }}
  .card.hold {{ background:linear-gradient(var(--t-o),var(--t-o)),var(--card); }}
  .card.ready {{ background:linear-gradient(var(--t-g),var(--t-g)),var(--card); }}
  .card.ref {{ background:linear-gradient(var(--t-p),var(--t-p)),var(--card); }}
  .card header {{ display:flex; justify-content:space-between; gap:.85rem; align-items:flex-start; }}
  .card h3 {{ margin:0; font-size:1.1rem; font-weight:620; letter-spacing:-.022em; line-height:1.25; }}
  .role {{ margin:.2rem 0 0; color:var(--ink-2); font-size:.91rem; letter-spacing:-.014em; }}
  .chip {{ font-size:.73rem; font-weight:590; padding:.26rem .6rem; border-radius:100px;
    white-space:nowrap; font-variant-numeric:tabular-nums; }}
  .chip.hold {{ color:var(--orange); background:var(--t-o); }}
  .chip.ready {{ color:var(--green); background:var(--t-g); }}
  .chip.warm {{ color:var(--purple); background:var(--t-p); }}

  ul.todo {{ margin:0; padding:0; list-style:none; display:flex; flex-direction:column; gap:.45rem; }}
  ul.todo li {{ font-size:.92rem; line-height:1.38; padding-left:1.25rem; position:relative;
    letter-spacing:-.014em; }}
  ul.todo li::before {{ content:""; position:absolute; left:.3rem; top:.52em; width:6px;
    height:6px; border-radius:50%; background:var(--orange); }}
  ul.todo li.done {{ color:var(--green); font-weight:550; }}
  ul.todo li.done::before {{ content:"\\2713"; background:none; width:auto; height:auto;
    left:0; top:0; font-weight:700; }}
  .why {{ color:var(--ink-2); }}
  .why::before {{ content:" \\2014 "; }}

  .act {{ display:flex; gap:.55rem; flex-wrap:wrap; align-items:center; margin-top:auto;
    padding-top:.95rem; border-top:1px solid var(--hair); }}
  .btn {{ display:inline-block; background:var(--blue); color:#fff; text-decoration:none;
    border:none; font:inherit; font-size:.9rem; font-weight:520; letter-spacing:-.014em;
    padding:.52rem 1.15rem; border-radius:100px; cursor:pointer;
    transition:opacity .2s, transform .12s; }}
  .btn:hover {{ opacity:.86; }}
  .btn:active {{ transform:scale(.97); }}
  .btn.ghost {{ background:var(--sunk); color:var(--ink); }}
  .btn[data-done] {{ background:var(--green); }}
  .btn:focus-visible {{ outline:3px solid var(--blue); outline-offset:3px; }}
  .ats {{ color:var(--ink-3); font-size:.78rem; margin-left:auto; }}
  .card.marked {{ opacity:.55; }}
  .card.marked .chip {{ background:var(--t-g); color:var(--green); }}
  .card.marked ul.todo {{ display:none; }}
  .stub {{ display:none; align-items:center; gap:.5rem; font-size:.9rem; color:var(--green);
    font-weight:550; }}
  .card.marked .stub {{ display:flex; }}
  .card.marked .mark {{ display:none; }}
  .undo {{ background:none; border:none; color:var(--ink-3); font:inherit; font-size:.82rem;
    text-decoration:underline; cursor:pointer; padding:0; }}
  .undo:hover {{ color:var(--ink); }}

  .contact {{ margin:0; font-size:.93rem; line-height:1.4; letter-spacing:-.015em; }}
  .contact strong {{ font-weight:600; }}
  .contact span {{ display:block; color:var(--ink-2); font-size:.86rem; margin-top:.1rem; }}
  .msg pre {{ background:var(--bg); border-radius:12px; padding:.85rem .95rem;
    font-family:inherit; font-size:.86rem; line-height:1.5; white-space:pre-wrap; margin:0;
    max-height:140px; overflow:auto; color:var(--ink-2); letter-spacing:-.012em; }}

  .sheet {{ background:var(--card); border-radius:20px; box-shadow:var(--sh); overflow:hidden; }}
  .tablewrap {{ overflow-x:auto; }}
  table {{ width:100%; border-collapse:collapse; font-size:.93rem; letter-spacing:-.015em; }}
  th {{ text-align:left; font-size:.78rem; color:var(--ink-3); font-weight:510;
    padding:.9rem 1.4rem; border-bottom:1px solid var(--hair); white-space:nowrap; }}
  td {{ padding:.88rem 1.4rem; border-bottom:1px solid var(--hair); }}
  tr:last-child td {{ border-bottom:none; }}
  td.when {{ color:var(--ink-3); font-variant-numeric:tabular-nums; white-space:nowrap; }}
  a.go {{ color:var(--blue); text-decoration:none; font-weight:510; }}
  td.note-cell {{ color:var(--ink-2); font-size:.88rem; max-width:32ch; }}
  a.go:hover {{ text-decoration:underline; }}

  .note {{ background:linear-gradient(var(--t-o),var(--t-o)),var(--card); border-radius:20px;
    padding:1.3rem 1.45rem; box-shadow:var(--sh); margin-top:1.5rem; }}
  .note h4 {{ margin:0 0 .3rem; font-size:1rem; font-weight:620; letter-spacing:-.02em; }}
  .note p {{ margin:0 0 .7rem; font-size:.9rem; color:var(--ink-2); }}
  .note ul {{ margin:0; padding:0; list-style:none; display:flex; flex-direction:column; gap:.3rem;
    font-size:.9rem; }}
  .empty {{ text-align:center; color:var(--ink-2); font-size:1.05rem; padding:3.5rem 1.5rem;
    background:var(--card); border-radius:20px; box-shadow:var(--sh); letter-spacing:-.018em; }}
  .muted {{ color:var(--ink-3); }}
  @media (prefers-reduced-motion:reduce) {{ *,*::before,*::after {{
    transition:none !important; animation:none !important; }} }}
  @media (max-width:600px) {{ .grid {{ grid-template-columns:1fr; }}
    th,td {{ padding-left:1.1rem; padding-right:1.1rem; }} }}
</style>

<div class="wrap">
  <div class="top">
    <h1>Application board</h1>
    <p class="lede">{f"{len(blocked)} waiting on you" if blocked else "Nothing blocked"}{f" &middot; {len(referrals)} referral{'' if len(referrals)==1 else 's'} ready" if referrals else ""}</p>
    <p class="stamp">{esc(name)} &middot; {esc(generated)}</p>
  </div>

  <div class="segwrap"><div class="seg" role="tablist">{tabnav}</div></div>

  <div class="panel on" id="p-act" role="tabpanel">
    <p class="hint">Each opens straight to where it is blocked.</p>
    {f'<div class="grid">{"".join(cards)}</div>' if cards else '<p class="empty">Nothing blocked right now.</p>'}
    {unconfirmed_block}
  </div>

  <div class="panel" id="p-ref" role="tabpanel">
    <p class="hint">A referral moves the odds more than another application.</p>
    {f'<div class="grid">{"".join(ref_cards)}</div>' if ref_cards else '<p class="empty">No referral paths found yet.</p>'}
  </div>

  <div class="panel" id="p-done" role="tabpanel">
    <p class="hint">Already out. Check here before applying again.</p>
    <div class="sheet"><div class="tablewrap"><table>
      <thead><tr><th>Company</th><th>Role</th><th>Status</th><th>When</th></tr></thead>
      <tbody>{sub_rows}</tbody></table></div></div>
  </div>

  {f'''<div class="panel" id="p-watch" role="tabpanel">
    <p class="hint">Found, not started.</p>
    <div class="sheet"><div class="tablewrap"><table>
      <thead><tr><th>Role</th><th>Why it is here</th><th></th></tr></thead>
      <tbody>{watch_rows}</tbody></table></div></div>
  </div>''' if watch else ""}
</div>

<script>
  var tabs = document.querySelectorAll('.tab');
  tabs.forEach(function (t) {{
    t.addEventListener('click', function () {{
      tabs.forEach(function (o) {{ o.classList.remove('on'); o.setAttribute('aria-selected','false'); }});
      document.querySelectorAll('.panel').forEach(function (p) {{ p.classList.remove('on'); }});
      t.classList.add('on'); t.setAttribute('aria-selected','true');
      var p = document.getElementById('p-' + t.dataset.tab);
      if (p) p.classList.add('on');
    }});
  }});
  var KEY = 'jobapp.marked';
  function readMarks() {{
    try {{ return JSON.parse(localStorage.getItem(KEY) || '[]'); }} catch (e) {{ return []; }}
  }}
  function writeMarks(m) {{
    try {{ localStorage.setItem(KEY, JSON.stringify(m)); }} catch (e) {{}}
  }}
  function applyMarks() {{
    var marks = readMarks();
    document.querySelectorAll('.card[data-id]').forEach(function (c) {{
      c.classList.toggle('marked', marks.indexOf(c.dataset.id) !== -1);
    }});
    var n = document.querySelectorAll('.card.marked').length;
    var badge = document.querySelector('.tab[data-tab="act"] .n');
    if (badge) badge.textContent = Math.max(0, {len(blocked)} - n);
  }}
  document.querySelectorAll('.mark').forEach(function (b) {{
    b.addEventListener('click', function () {{
      var m = readMarks();
      if (m.indexOf(b.dataset.id) === -1) m.push(b.dataset.id);
      writeMarks(m); applyMarks();
    }});
  }});
  document.querySelectorAll('.undo').forEach(function (b) {{
    b.addEventListener('click', function () {{
      writeMarks(readMarks().filter(function (x) {{ return x !== b.dataset.id; }}));
      applyMarks();
    }});
  }});
  applyMarks();

  document.querySelectorAll('.copy').forEach(function (b) {{
    b.addEventListener('click', function () {{
      navigator.clipboard.writeText(b.dataset.msg).then(function () {{
        var s = b.textContent; b.textContent = 'Copied'; b.dataset.done = '1';
        setTimeout(function () {{ b.textContent = s; delete b.dataset.done; }}, 1600);
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
        "submitted": len([e for e in state["history"]
                          if e.get("event") in ("completed", "response", "interview", "offer", "rejected")]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
