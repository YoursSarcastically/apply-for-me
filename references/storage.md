# Storage contract

All persistent state lives under `~/.job-application/` and is reached only through `scripts/store.py`. Going around the helper produces files the next session cannot read.

```
~/.job-application/
  profile.json         identity, work history, education, skills
  answers.json         reusable answers, each with a confidence state
  applications.jsonl   append-only event log
  sessions/            resumable in-progress applications
```

## Commands

```bash
python3 store.py init                                  # create store, print paths
python3 store.py profile-get
python3 store.py profile-replace --input profile.json
python3 store.py answer-put --input answer.json [--remember-sensitive]
python3 store.py answer-find --question "..."
python3 store.py history-append --input event.json
python3 store.py history-list
python3 store.py session-save --id <app-id> --input session.json
python3 store.py session-load --id <app-id>
python3 store.py session-list
python3 store.py session-delete --id <app-id>
```

Pass JSON through a private temp file with `umask 077`, and delete it afterwards. Never echo stored values into logs or into the conversation unless the user asked to see them.

## Confidence states

Every stored answer and every inferred profile field carries a state. This is the mechanism that stops a guess from hardening into a fact across applications.

| State | Meaning | Reuse without asking? |
|---|---|---|
| `confirmed` | The user stated or approved it | Yes, when non-sensitive and the question matches |
| `inferred` | You derived it from context | No. Show it and confirm |
| `missing` | Unknown | No. Ask |
| `sensitive` | Compensation, visa, demographics, disability | Never silently. Confirm before every use |

`inferred` is the state that matters most in practice. When a form needs a job's city and the resume only gives years, that value is inferred forever after — not because it is likely wrong, but because neither you nor the next session can tell it apart from a fact once the label is gone.

## Sensitive answers: two separate permissions

Using a sensitive answer now and storing it for later are different decisions. Ask them separately:

1. May I use this for this application?
2. May I save it for future applications?

Only pass `--remember-sensitive` after a clear yes to the second. Permission to fill is not permission to remember. Even a stored sensitive answer gets shown and reconfirmed before each future use, because circumstances change — expected compensation in particular.

## Events

```json
{"event": "reviewed", "company": "...", "role": "...", "ats": "greenhouse", "applicationId": "..."}
```

`reviewed` means the form reached final review. `completed` means the user confirmed submission, or you directly observed a confirmation state.

Keeping these apart is what prevents duplicate applications weeks later. When you cannot tell whether something submitted, log `reviewed` and say so — an honest gap is more useful than a confident wrong entry.

## Sessions

Save a session whenever an application is left incomplete. Record the ATS, company, role, URL, the step reached, and each pending field with the reason it is pending — "user must answer", "needs CAPTCHA", "unknown to assistant".

Sessions hold field *descriptions*, never answer values. Values live in the answer store, which has the confidence machinery around them.

Delete a session once the user confirms submission or abandons it. History is separate and stays.
