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
        <div class="tablewrap"><table><thead><tr><th>Company</th><th>Role</th><th></th></tr></thead>
        <tbody>{watch_rows}</tbody></table></div>
      </section>""" if watch else ""

    total_todo = sum(len(s.get("pendingFields", [])) for s in blocked)

    return f"""<title>Application Board</title>
<style>
  :root {{
    --bg:#f4f6f9; --surface:#ffffff; --sunk:#eef1f6;
    --ink:#12151d; --ink-2:#4a5263; --ink-3:#7b8395;
    --line:#dfe4ec; --line-2:#c9d1de;
    --accent:#2f43d4;
    --hold:#9a5511; --hold-bg:#fdf3e7;
    --go:#0d6b4a;   --go-bg:#e8f5ef;
    --warm:#6532c4; --warm-bg:#f1ebfd;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg:#0e1016; --surface:#171a22; --sunk:#12141b;
      --ink:#e9ecf3; --ink-2:#a4adbf; --ink-3:#727c91;
      --line:#242833; --line-2:#333947;
      --accent:#7b8cff;
      --hold:#e0a463; --hold-bg:#261c10;
      --go:#63c79c;   --go-bg:#10241c;
      --warm:#b294f5; --warm-bg:#1c1630;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg:#0e1016; --surface:#171a22; --sunk:#12141b;
    --ink:#e9ecf3; --ink-2:#a4adbf; --ink-3:#727c91;
    --line:#242833; --line-2:#333947;
    --accent:#7b8cff;
    --hold:#e0a463; --hold-bg:#261c10;
    --go:#63c79c;   --go-bg:#10241c;
    --warm:#b294f5; --warm-bg:#1c1630;
  }}

  *, *::before, *::after {{ box-sizing:border-box; }}
  html {{ -webkit-text-size-adjust:100%; }}
  body {{
    margin:0; background:var(--bg); color:var(--ink);
    font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;
    font-size:15px; line-height:1.5;
    -webkit-font-smoothing:antialiased;
  }}
  .wrap {{ max-width:1040px; margin:0 auto; padding:clamp(1.5rem,4vw,3rem) clamp(1rem,3vw,1.75rem) 5rem; }}

  .masthead {{ display:flex; align-items:baseline; justify-content:space-between;
    gap:1rem; flex-wrap:wrap; padding-bottom:1.1rem; border-bottom:1px solid var(--line-2); }}
  h1 {{ font-size:clamp(1.5rem,3.5vw,1.9rem); font-weight:640; letter-spacing:-.025em;
    margin:0; text-wrap:balance; }}
  .stamp {{ font-size:.78rem; color:var(--ink-3); font-variant-numeric:tabular-nums; }}

  .tally {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(132px,1fr));
    gap:1px; background:var(--line); border:1px solid var(--line);
    border-radius:8px; overflow:hidden; margin:1.5rem 0 2.75rem; }}
  .tally div {{ background:var(--surface); padding:.85rem 1rem; }}
  .tally b {{ display:block; font-size:1.7rem; font-weight:600; line-height:1.05;
    letter-spacing:-.03em; font-variant-numeric:tabular-nums; }}
  .tally span {{ font-size:.7rem; color:var(--ink-3); text-transform:uppercase;
    letter-spacing:.09em; font-weight:600; }}
  .tally .lead b {{ color:var(--hold); }}

  h2 {{ font-size:.75rem; text-transform:uppercase; letter-spacing:.11em;
    color:var(--ink-3); font-weight:700; margin:0 0 .9rem;
    display:flex; align-items:center; gap:.6rem; }}
  h2::after {{ content:""; flex:1; height:1px; background:var(--line); }}
  section {{ margin-bottom:2.75rem; }}

  .grid {{ display:grid; gap:.85rem; grid-template-columns:repeat(auto-fill,minmax(310px,1fr)); }}

  .card {{ background:var(--surface); border:1px solid var(--line);
    border-radius:8px; padding:1rem 1.05rem; display:flex; flex-direction:column; gap:.7rem; }}
  .card.hold {{ background:var(--hold-bg); border-color:color-mix(in srgb,var(--hold) 22%,var(--line)); }}
  .card.ready {{ background:var(--go-bg); border-color:color-mix(in srgb,var(--go) 22%,var(--line)); }}
  .card.ref {{ background:var(--warm-bg); border-color:color-mix(in srgb,var(--warm) 22%,var(--line)); }}

  .card header {{ display:flex; justify-content:space-between; gap:.7rem; align-items:flex-start; }}
  .card h3 {{ margin:0; font-size:1rem; font-weight:620; letter-spacing:-.01em; }}
  .role {{ margin:.15rem 0 0; color:var(--ink-2); font-size:.86rem; }}

  .chip {{ font-size:.66rem; font-weight:700; padding:.24rem .5rem; border-radius:4px;
    white-space:nowrap; text-transform:uppercase; letter-spacing:.06em;
    font-variant-numeric:tabular-nums; border:1px solid transparent; }}
  .chip.hold {{ color:var(--hold); background:var(--surface);
    border-color:color-mix(in srgb,var(--hold) 30%,transparent); }}
  .chip.ready {{ color:var(--go); background:var(--surface);
    border-color:color-mix(in srgb,var(--go) 30%,transparent); }}
  .chip.warm {{ color:var(--warm); background:var(--surface);
    border-color:color-mix(in srgb,var(--warm) 30%,transparent); }}

  ul.todo {{ margin:0; padding:0; list-style:none; display:flex; flex-direction:column; gap:.35rem; }}
  ul.todo li {{ font-size:.865rem; padding-left:1.05rem; position:relative; color:var(--ink); }}
  ul.todo li::before {{ content:""; position:absolute; left:0; top:.5em;
    width:5px; height:5px; border-radius:1px; background:var(--hold); }}
  ul.todo li.done {{ padding-left:0; color:var(--go); font-weight:560; }}
  ul.todo li.done::before {{ display:none; }}
  .why {{ color:var(--ink-2); }}
  .why::before {{ content:" — "; }}

  .card footer {{ display:flex; justify-content:space-between; align-items:center;
    gap:.6rem; flex-wrap:wrap; border-top:1px solid var(--line);
    padding-top:.7rem; margin-top:auto; }}
  .ats {{ color:var(--ink-3); font-size:.68rem; text-transform:uppercase; letter-spacing:.08em; font-weight:650; }}

  a.go {{ color:var(--accent); font-weight:620; text-decoration:none; font-size:.86rem;
    padding:.3rem .55rem; margin:-.3rem -.15rem; border-radius:5px; }}
  a.go:hover {{ background:color-mix(in srgb,var(--accent) 10%,transparent); }}
  a.go:focus-visible, button:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; }}

  .contact {{ margin:0; font-size:.88rem; line-height:1.4; }}
  .contact strong {{ font-weight:620; }}
  .contact span {{ display:block; color:var(--ink-2); font-size:.82rem; }}
  .msg {{ display:flex; flex-direction:column; gap:.5rem; align-items:flex-start; }}
  .msg pre {{ background:var(--surface); border:1px solid var(--line); border-radius:6px;
    padding:.7rem .8rem; font-family:inherit; font-size:.82rem; line-height:1.5;
    white-space:pre-wrap; margin:0; max-height:150px; overflow:auto; width:100%;
    color:var(--ink-2); }}
  button.copy {{ background:var(--surface); border:1px solid var(--line-2); color:var(--ink);
    border-radius:5px; padding:.36rem .75rem; font:inherit; font-size:.8rem; font-weight:600;
    cursor:pointer; transition:border-color .12s, color .12s; }}
  button.copy:hover {{ border-color:var(--warm); color:var(--warm); }}
  button.copy[data-done] {{ color:var(--go); border-color:var(--go); }}

  .tablewrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:8px; background:var(--surface); }}
  table {{ width:100%; border-collapse:collapse; font-size:.875rem; }}
  th {{ text-align:left; font-size:.67rem; text-transform:uppercase; letter-spacing:.09em;
    color:var(--ink-3); font-weight:700; padding:.6rem .9rem; background:var(--sunk);
    border-bottom:1px solid var(--line); white-space:nowrap; }}
  td {{ padding:.6rem .9rem; border-bottom:1px solid var(--line); }}
  tr:last-child td {{ border-bottom:none; }}
  td.when {{ color:var(--ink-3); font-variant-numeric:tabular-nums; white-space:nowrap; }}

  .note {{ background:var(--hold-bg); border:1px solid color-mix(in srgb,var(--hold) 25%,var(--line));
    border-radius:8px; padding:1rem 1.15rem; }}
  .note h2 {{ color:var(--hold); margin-bottom:.5rem; }}
  .note h2::after {{ background:color-mix(in srgb,var(--hold) 25%,transparent); }}
  .note p {{ margin:0 0 .6rem; font-size:.86rem; color:var(--ink-2); }}
  .note ul {{ margin:0; padding-left:1.1rem; font-size:.875rem; }}
  .note li {{ margin:.2rem 0; }}

  .empty {{ color:var(--ink-3); font-size:.9rem; padding:1.4rem; text-align:center;
    border:1px dashed var(--line-2); border-radius:8px; }}
  .muted {{ color:var(--ink-3); }}
  @media (prefers-reduced-motion:reduce) {{ * {{ transition:none !important; }} }}
</style>

<div class="wrap">
  <header class="masthead">
    <h1>Application board</h1>
    <p class="stamp">{esc(name)} &middot; {esc(generated)}</p>
  </header>

  <div class="tally">
    <div class="lead"><b>{len(blocked)}</b><span>need you</span></div>
    <div><b>{total_todo}</b><span>open items</span></div>
    <div><b>{len(referrals)}</b><span>referrals</span></div>
    <div><b>{len(submitted)}</b><span>submitted</span></div>
  </div>

  <section>
    <h2>Needs you</h2>
    {f'<div class="grid">{"".join(cards)}</div>' if cards
     else '<p class="empty">Nothing blocked right now.</p>'}
  </section>

  {f'<section><h2>Referrals worth sending</h2><div class="grid">{"".join(ref_cards)}</div></section>' if ref_cards else ''}

  {unconfirmed_block}

  <section>
    <h2>Submitted</h2>
    <div class="tablewrap"><table>
      <thead><tr><th>Company</th><th>Role</th><th>When</th></tr></thead>
      <tbody>{sub_rows}</tbody>
    </table></div>
  </section>

  {watch_block}
</div>

<script>
  document.querySelectorAll('button.copy').forEach(function (b) {{
    b.addEventListener('click', function () {{
      navigator.clipboard.writeText(b.dataset.msg).then(function () {{
        var t = b.textContent;
        b.textContent = 'Copied'; b.dataset.done = '1';
        setTimeout(function () {{ b.textContent = t; delete b.dataset.done; }}, 1500);
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
