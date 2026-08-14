# apply-for-me

A [Claude Skill](https://docs.claude.com/en/docs/claude-code/skills) that runs your job search as a standing agent. Reads your resume once, interviews you once, then searches, applies, and hands you a board of what still needs a human.

```bash
git clone https://github.com/YoursSarcastically/apply-for-me.git ~/.claude/skills/job-application
```

Needs Python 3.9+ and the Claude for Chrome extension.

---

## What you get

### Every blocked application, and exactly what is blocking it

![Needs you tab showing five application cards, each naming the specific missing field](docs/needs-you.png)

Green means ready to submit. Each card names the field a human has to answer and why, then opens straight to that page. **Mark submitted** greys it out when you are done.

### Who can refer you, with the message already written

![Referrals tab showing a first-degree contact and a network pool, each with a drafted message and copy button](docs/referrals.png)

A referral beats being applicant 201. It surfaces the connection *before* filling the form, drafts the note, and waits for you to send it.

### Roles it found, and why each one is there

![Watching tab showing four roles with a note explaining why each was kept](docs/watching.png)

It sweeps LinkedIn, Indeed, YC, Wellfound, HN, regional boards and company ATS boards directly, then reads each full posting, because titles lie.

---

## Why it works this way

Every rule came from something going wrong in real use.

| What happened | What it does now |
|---|---|
| Closing a form's modal **submitted** the application | Treats any interaction with a filled form as potentially final, then verifies |
| A role titled *"AI and Agentic Experiences"* was a data-pipeline job. One listing said **"Mumbai"**, the body required moving to **Bangkok** | Reads the full body before shortlisting |
| An employer allows **3 applications per 30 days**, silently | Detects quotas, raises them before spending one |
| A careers profile still held a **two-year-old resume** under an old title | Audits prefilled ATS data first |
| A form asked about association with an **audit firm**; the candidate had worked there years earlier | Cross-checks declarations against work history, then hands them back |
| Searching one job board suggested a role type barely existed | Sweeps many channels, and reports which returned nothing |

---

## What it will not do

Boundaries, not gaps: type passwords, create accounts, solve CAPTCHAs, send messages without per-message permission, answer demographic questions, tick truth attestations, or invent a value to fill a required field.

Where a fact is unknown, it leaves the field and tells you.

---

## Under the hood

```
SKILL.md              the instructions Claude follows
scripts/store.py      profile, answers, history, sessions
scripts/dashboard.py  builds the board
references/           per-ATS quirks, sourcing channels, storage contract
```

State lives in `~/.job-application/`, owner-readable only. Every stored value carries a confidence state, `confirmed` / `inferred` / `missing` / `sensitive`, so a guess is never silently reused as a fact. Sensitive values need separate permission to use and to store.

MIT.
