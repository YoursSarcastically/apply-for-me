#!/usr/bin/env python3
"""Local storage for the job-application skill.

Keeps profile, reusable answers, application history and resumable sessions in
~/.job-application/. Standard library only.

Design notes:
  - Every answer and inferred profile field carries a confidence state so a
    guess cannot silently become a fact on the next application.
  - Sensitive values (compensation, visa, demographics) are only persisted with
    an explicit --remember-sensitive flag, because permission to use a value now
    is a different decision from permission to store it.
  - Errors stay terse and never echo stored values, since these files hold
    personal data.
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
ANSWER_STATES = {"confirmed", "inferred", "missing", "sensitive"}
SESSION_STATUSES = {"watch", "active", "review", "completed", "abandoned"}
# Pre-submission lifecycle, then post-submission outcomes reported by the user.
HISTORY_EVENTS = {"started", "reviewed", "submitting", "completed", "abandoned",
                  "response", "interview", "offer", "rejected"}


class StoreError(Exception):
    pass


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def root_dir(override=None):
    if override:
        return Path(override).expanduser()
    return Path(os.environ.get("JOB_APPLICATION_DIR", "~/.job-application")).expanduser()


def paths(root):
    return {
        "root": str(root),
        "profile": str(root / "profile.json"),
        "answers": str(root / "answers.json"),
        "history": str(root / "applications.jsonl"),
        "sessions": str(root / "sessions"),
        "meta": str(root / "meta.json"),
    }


def write_private(path, payload):
    """Write JSON with owner-only permissions, atomically."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def read_json(path, default):
    path = Path(path)
    if not path.exists():
        return default
    try:
        with open(path) as fh:
            return json.load(fh)
    except json.JSONDecodeError:
        raise StoreError(f"{path.name} is not valid JSON; refusing to overwrite")


def load_input(spec):
    if spec == "-":
        return json.load(sys.stdin)
    with open(spec) as fh:
        return json.load(fh)


def safe_id(value):
    if not value or not all(c.isalnum() or c in "-_." for c in value):
        raise StoreError("application id must be alphanumeric with - _ . only")
    if ".." in value:
        raise StoreError("application id must not contain ..")
    return value


def answer_key(question):
    """Normalise a question into a stable lookup key.

    Wording varies between employers ("What is your notice period?" versus
    "Official Notice Period ?") so keys are normalised rather than literal.
    """
    cleaned = "".join(c.lower() if c.isalnum() else " " for c in question)
    words = [w for w in cleaned.split() if w not in {"the", "a", "an", "your", "you", "do", "is", "are", "what", "please", "indicate"}]
    return "-".join(words)[:80]


# --- commands ---------------------------------------------------------------


def cmd_init(args):
    root = root_dir(args.root)
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    (root / "sessions").mkdir(exist_ok=True)
    p = paths(root)
    if not Path(p["profile"]).exists():
        write_private(p["profile"], {})
    if not Path(p["answers"]).exists():
        write_private(p["answers"], {})
    Path(p["history"]).touch()
    os.chmod(p["history"], 0o600)
    out = dict(p)
    out["initialized"] = True
    out["schemaVersion"] = SCHEMA_VERSION
    return out


def cmd_profile_get(args):
    return read_json(paths(root_dir(args.root))["profile"], {})


def cmd_profile_replace(args):
    profile = load_input(args.input)
    if not isinstance(profile, dict):
        raise StoreError("profile must be a JSON object")
    for list_field in ("workHistory", "education", "skills"):
        if list_field in profile and not isinstance(profile[list_field], list):
            raise StoreError(f"{list_field} must be a list")
    profile["updatedAt"] = now()
    profile["schemaVersion"] = SCHEMA_VERSION
    write_private(paths(root_dir(args.root))["profile"], profile)
    return profile


def cmd_answer_put(args):
    entry = load_input(args.input)
    question = entry.get("question")
    if not question:
        raise StoreError("answer requires a question")
    state = entry.get("state", "confirmed")
    if state not in ANSWER_STATES:
        raise StoreError(f"state must be one of {sorted(ANSWER_STATES)}")

    if state == "sensitive" and not args.remember_sensitive:
        # Record that the question exists and is sensitive, but not the value.
        # Permission to fill is not permission to remember.
        entry["value"] = None
        entry["note"] = "value not stored; user did not consent to remembering"

    key = entry.get("key") or answer_key(question)
    entry["key"] = key
    entry["state"] = state
    entry["updatedAt"] = now()

    path = paths(root_dir(args.root))["answers"]
    answers = read_json(path, {})
    answers[key] = entry
    write_private(path, answers)
    return {"key": key, "state": state, "stored": entry.get("value") is not None}


def find_answer(answers, question):
    key = answer_key(question)
    if key in answers:
        return answers[key]
    # Fall back to overlap scoring so slightly different phrasings still match.
    # The bar is deliberately high: "product management" vs "project management"
    # scores 0.71 — one word apart, and the wrong answer.
    target = set(key.split("-"))
    scored = []
    for k, v in answers.items():
        other = set(k.split("-"))
        if not other:
            continue
        score = len(target & other) / len(target | other)
        if score > 0:
            scored.append((score, k, v))
    scored.sort(key=lambda t: (-t[0], t[1]))
    if scored:
        score, _, entry = scored[0]
        # Sensitive answers never fuzzy-match: compensation landing in a
        # near-miss field is the worst mis-fill this store can produce.
        if score >= 0.75 and entry.get("state") != "sensitive":
            return {"match": "fuzzy", "score": round(score, 2), **entry}
    # Candidates carry the stored question, never the value; to use one,
    # confirm it means the same thing, then look it up by its own question.
    candidates = [
        {"key": k, "question": v.get("question"), "state": v.get("state"), "score": round(s, 2)}
        for s, k, v in scored[:3] if s >= 0.4
    ]
    return {"match": "none", "key": key, "candidates": candidates}


def cmd_answer_find(args):
    answers = read_json(paths(root_dir(args.root))["answers"], {})
    return find_answer(answers, args.question)


def cmd_answers_resolve(args):
    """Resolve a whole form's questions in one call instead of one per field."""
    questions = load_input(args.input)
    if not isinstance(questions, list) or not all(isinstance(q, str) for q in questions):
        raise StoreError("input must be a JSON list of question strings")
    answers = read_json(paths(root_dir(args.root))["answers"], {})
    return {q: find_answer(answers, q) for q in questions}


def cmd_answer_list(args):
    return read_json(paths(root_dir(args.root))["answers"], {})


def cmd_history_append(args):
    event = load_input(args.input)
    if event.get("event") not in HISTORY_EVENTS:
        raise StoreError(f"event must be one of {sorted(HISTORY_EVENTS)}")
    for banned in ("answers", "values", "password", "profile"):
        if banned in event:
            raise StoreError(f"history must not contain {banned}")
    event["at"] = now()
    event["eventId"] = str(uuid.uuid4())
    path = paths(root_dir(args.root))["history"]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")
    os.chmod(path, 0o600)
    return event


def cmd_history_list(args):
    path = Path(paths(root_dir(args.root))["history"])
    if not path.exists():
        return []
    events = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    if args.company:
        events = [e for e in events if e.get("company", "").lower() == args.company.lower()]
    return events


def cmd_history_status(args):
    """Latest event per application: the quick check against reapplying."""
    events = cmd_history_list(argparse.Namespace(root=args.root, company=None))
    latest = {}
    for e in events:
        key = e.get("applicationId") or f"{e.get('company')}|{e.get('role')}"
        latest[key] = {"company": e.get("company"), "role": e.get("role"), "event": e.get("event"), "at": e.get("at")}
    return list(latest.values())


def cmd_session_save(args):
    session = load_input(args.input)
    app_id = safe_id(args.id)
    status = session.get("status", "active")
    if status not in SESSION_STATUSES:
        raise StoreError(f"status must be one of {sorted(SESSION_STATUSES)}")
    for field in session.get("pendingFields", []):
        if not isinstance(field, dict) or "question" not in field:
            raise StoreError("each pendingField needs a question")
        if "value" in field:
            raise StoreError("pendingFields must not contain values; store those as answers")
    session["applicationId"] = app_id
    session["status"] = status
    session["updatedAt"] = now()
    sessions = Path(paths(root_dir(args.root))["sessions"])
    sessions.mkdir(parents=True, exist_ok=True)
    write_private(sessions / f"{app_id}.json", session)
    return session


def cmd_session_load(args):
    path = Path(paths(root_dir(args.root))["sessions"]) / f"{safe_id(args.id)}.json"
    if not path.exists():
        raise StoreError("no session with that id")
    return read_json(path, {})


def cmd_session_list(args):
    sessions = Path(paths(root_dir(args.root))["sessions"])
    if not sessions.exists():
        return []
    out = []
    for f in sorted(sessions.glob("*.json")):
        data = read_json(f, {})
        out.append({
            "applicationId": data.get("applicationId", f.stem),
            "company": data.get("company"),
            "role": data.get("role"),
            "status": data.get("status"),
            "step": data.get("step"),
            "pending": len(data.get("pendingFields", [])),
            "updatedAt": data.get("updatedAt"),
        })
    return out


def cmd_session_delete(args):
    path = Path(paths(root_dir(args.root))["sessions"]) / f"{safe_id(args.id)}.json"
    if path.exists():
        path.unlink()
        return {"deleted": args.id}
    return {"deleted": None, "note": "no such session"}


FUNNEL_ORDER = ["started", "reviewed", "submitting", "completed",
                "response", "interview", "offer", "rejected"]


def cmd_stats(args):
    """The search as a funnel: what was started, what went out, what converted.

    bySource only counts submitted applications, so it reads as conversion —
    which channels produce responses — rather than raw activity.
    """
    events = cmd_history_list(argparse.Namespace(root=args.root, company=None))
    apps = {}
    for e in events:
        key = e.get("applicationId") or f"{e.get('company')}|{e.get('role')}"
        a = apps.setdefault(key, {"stages": set(), "source": None,
                                  "company": e.get("company"), "role": e.get("role")})
        a["stages"].add(e.get("event"))
        if e.get("source") and not a["source"]:
            a["source"] = e["source"]

    funnel = {s: sum(1 for a in apps.values() if s in a["stages"]) for s in FUNNEL_ORDER}

    by_source = {}
    for a in apps.values():
        if "completed" not in a["stages"]:
            continue
        src = a["source"] or "unknown"
        row = by_source.setdefault(src, {"submitted": 0, "response": 0,
                                         "interview": 0, "offer": 0, "rejected": 0})
        row["submitted"] += 1
        for s in ("response", "interview", "offer", "rejected"):
            if s in a["stages"]:
                row[s] += 1

    needs_verification = sorted(
        f"{a['company']} — {a['role']}" for a in apps.values()
        if "submitting" in a["stages"] and not ({"completed", "abandoned"} & a["stages"])
    )
    return {"applications": len(apps), "funnel": funnel,
            "bySource": by_source, "needsVerification": needs_verification}


def cmd_meta_set(args):
    """Small operational values (dashboard artifact URL, last sweep time).

    Never answer or profile data — those have confidence machinery this bypasses.
    """
    path = paths(root_dir(args.root))["meta"]
    meta = read_json(path, {})
    meta[args.key] = args.value
    meta["updatedAt"] = now()
    write_private(path, meta)
    return {args.key: args.value}


def cmd_meta_get(args):
    meta = read_json(paths(root_dir(args.root))["meta"], {})
    if args.key:
        return {args.key: meta.get(args.key)}
    return meta


def cmd_paths(args):
    return paths(root_dir(args.root))


COMMANDS = {
    "init": cmd_init,
    "paths": cmd_paths,
    "profile-get": cmd_profile_get,
    "profile-replace": cmd_profile_replace,
    "answer-put": cmd_answer_put,
    "answer-find": cmd_answer_find,
    "answers-resolve": cmd_answers_resolve,
    "answer-list": cmd_answer_list,
    "history-append": cmd_history_append,
    "history-list": cmd_history_list,
    "history-status": cmd_history_status,
    "stats": cmd_stats,
    "session-save": cmd_session_save,
    "session-load": cmd_session_load,
    "session-list": cmd_session_list,
    "session-delete": cmd_session_delete,
    "meta-set": cmd_meta_set,
    "meta-get": cmd_meta_get,
}


def build_parser():
    p = argparse.ArgumentParser(description="Local store for the job-application skill.")
    p.add_argument("--root", help="store directory (default ~/.job-application)")
    sub = p.add_subparsers(dest="command", required=True)

    for name in ("init", "paths", "profile-get", "answer-list", "history-status", "stats"):
        sub.add_parser(name)

    sp = sub.add_parser("profile-replace"); sp.add_argument("--input", required=True)
    sp = sub.add_parser("answer-put"); sp.add_argument("--input", required=True); sp.add_argument("--remember-sensitive", action="store_true")
    sp = sub.add_parser("answer-find"); sp.add_argument("--question", required=True)
    sp = sub.add_parser("answers-resolve"); sp.add_argument("--input", required=True)
    sp = sub.add_parser("history-append"); sp.add_argument("--input", required=True)
    sp = sub.add_parser("history-list"); sp.add_argument("--company")
    sp = sub.add_parser("session-save"); sp.add_argument("--id", required=True); sp.add_argument("--input", required=True)
    for name in ("session-load", "session-delete"):
        sp = sub.add_parser(name); sp.add_argument("--id", required=True)
    sub.add_parser("session-list")
    sp = sub.add_parser("meta-set"); sp.add_argument("--key", required=True); sp.add_argument("--value", required=True)
    sp = sub.add_parser("meta-get"); sp.add_argument("--key")
    return p


def main():
    args = build_parser().parse_args()
    try:
        result = COMMANDS[args.command](args)
    except StoreError as exc:
        print(f"job-application store: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"job-application store: file not found: {exc.filename}", file=sys.stderr)
        return 2
    except json.JSONDecodeError:
        print("job-application store: input is not valid JSON", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
