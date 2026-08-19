# Storage contract

All persistent state lives under `~/.job-application/` and is reached only through `scripts/store.py`. Going around the helper produces files the next session cannot read.

```
~/.job-application/
  profile.json         identity, work history, education, skills
  answers.json         reusable answers, each with a confidence state
  applications.jsonl   append-only event log
  sessions/            resumable in-progress applications
  meta.json            small operational values: dashboard artifact URL, last sweep time
```

## Commands

```bash
python3 store.py init                                  # create store, print paths
python3 store.py profile-get
python3 store.py profile-replace --input profile.json
python3 store.py answer-put --input answer.json [--remember-sensitive]
python3 store.py answer-find --question "..."
python3 store.py answers-resolve --input questions.json   # whole form in one call
python3 store.py history-append --input event.json
python3 store.py history-list
python3 store.py stats                                 # funnel, per-source conversion, needsVerification
python3 store.py session-save --id <app-id> --input session.json
python3 store.py session-load --id <app-id>
python3 store.py session-list
python3 store.py session-delete --id <app-id>
python3 store.py meta-set --key artifactUrl --value <url>
python3 store.py meta-get [--key artifactUrl]
```

Pass JSON through a private temp file with `umask 077`, and delete it afterwards. Never echo stored values into logs or into the conversation unless the user asked to see them.

## Session status, and where watch entries live

A session is not only an in-progress form. `dashboard.py` groups sessions by their `status` field, and one value is load-bearing:

| `status` | Meaning | Dashboard |
|---|---|---|
| `watch` | A role that has been sourced but not applied to. This is the **watch entry** referred to throughout `SKILL.md` — the place the one-time posting extraction is written so no later cycle re-reads the body. | Watching tab |
| anything else | An application in progress | Needs-you / in-progress |

Write one with `session-save`, using a stable slug derived from company and role so a later sweep updates the entry instead of duplicating it:

```bash
python3 store.py session-save --id acme-senior-ai-pm --input watch.json
```

```json
{"status": "watch", "company": "Acme", "role": "Senior AI PM",
 "url": "https://job-boards.greenhouse.io/acme/jobs/123", "source": "greenhouse",
 "location": "Bengaluru (hybrid)", "bodyRead": true,
 "note": "Body matches title. Owns eval pipeline. No sponsorship offered."}
```

There is no `watch-*` command and no separate watchlist file. Putting sourced roles anywhere else — `meta.json` in particular — stores them where the dashboard cannot find them, which is the failure this document opens by warning about.

## Confidence states

Every stored answer and every inferred profile field carries a state. This is the mechanism that stops a guess from hardening into a fact across applications.

| State | Meaning | Reuse without asking? |
|---|---|---|
| `confirmed` | The user stated or approved it | Yes, when non-sensitive and the question matches |
| `inferred` | You derived it from context | No. Show it and confirm |
| `missing` | Unknown | No. Ask |
| `sensitive` | Compensation, visa, demographics, disability | Never silently. Confirm before every use |

`inferred` is the state that matters most in practice. When a form needs a job's city and the resume only gives years, that value is inferred forever after — not because it is likely wrong, but because neither you nor the next session can tell it apart from a fact once the label is gone.

## Matching answers to form questions

`answer-find` returns an exact match when the normalised keys agree. Below that it fuzzy-matches, and the rules are deliberately conservative:

- A fuzzy match needs at least 0.75 token overlap. "Years of experience in product management" versus "…in project management" scores 0.71 — one word apart, and the wrong answer. Below the bar the result is `match: none` plus up to three `candidates` carrying key, stored question, state and score — never values. To use a candidate, confirm it means the same thing, then fetch it exactly via `answer-find` with the candidate's own stored question.
- **Sensitive answers never fuzzy-match.** A compensation figure landing in a near-miss field is the worst mis-fill this store can produce. Exact key or nothing.
- A `match: fuzzy` result is a lead, not an authority: the score measures wording overlap, not meaning. Confirm it fits the question before filling.

`answers-resolve` takes a JSON list of question strings and returns the full map in one call. Use it to build a form's fill plan upfront — which fields are covered, which need confirming, which block — instead of paying one round-trip per field.

## Sensitive answers: two separate permissions

Using a sensitive answer now and storing it for later are different decisions. Ask them separately:

1. May I use this for this application?
2. May I save it for future applications?

Only pass `--remember-sensitive` after a clear yes to the second. Permission to fill is not permission to remember. Even a stored sensitive answer gets shown and reconfirmed before each future use, because circumstances change — expected compensation in particular.

## Events

```json
{"event": "reviewed", "company": "...", "role": "...", "ats": "greenhouse", "applicationId": "..."}
```

Useful optional fields: `source` (the channel the role came from — `linkedin`, `greenhouse`, `wellfound` — put it on every `completed` event; it is what powers the per-channel conversion in `stats`) and `resumeVariant` (which resume the employer received, per `tailoring.md`).

`reviewed` means the form reached final review. `submitting` is written immediately **before** any potentially-final interaction — Submit, closing a completed modal, navigating away. `completed` means the user confirmed submission, or you directly observed a confirmation state.

`submitting` is a write-ahead record. Its value is what it means when it is the *last* event for an application: a session died between the click and the confirmation check. On seeing that, verify on the platform whether the application went through, then log `completed` or `abandoned` — never treat the role as un-applied and fill the form again.

Keeping these apart is what prevents duplicate applications weeks later. When you cannot tell whether something submitted, leave the `submitting` event as the latest and say so — an honest gap is more useful than a confident wrong entry.

After submission, log outcomes as the user reports them: `response`, `interview`, `offer`, `rejected`. These stay on the Submitted tab with their status, and they are what lets sourcing shift budget toward the channels that actually convert (see the outcomes section in `sourcing.md`).

## Sessions

Save a session whenever an application is left incomplete. Record the ATS, company, role, URL, the step reached, and each pending field with the reason it is pending — "user must answer", "needs CAPTCHA", "unknown to assistant".

Sessions hold field *descriptions*, never answer values. Values live in the answer store, which has the confidence machinery around them.

Delete a session once the user confirms submission or abandons it. History is separate and stays.
