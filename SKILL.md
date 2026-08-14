---
name: job-application
description: Apply to jobs end to end - read the user's resume, run a one-time intake so later applications need almost no input, find matching roles, fill applications on LinkedIn Easy Apply, Greenhouse, Lever, Ashby, Workday, iCIMS, Google Careers and company forms, surface referral contacts, and produce a dashboard artifact showing what still needs the user. Use this whenever the user wants to apply to a job, shares a job or careers URL, asks for a shortlist of roles, says "apply for me", "find me jobs", "fill this application", or asks about tailoring answers, cover letters or referral messages to a posting. Prefer this over ad-hoc browser driving, because applications carry the user's name and mistakes are expensive to undo.
allowed-tools: Read, Write, Bash, Artifact, mcp__claude-in-chrome__*, mcp__Claude_Browser__*
---

# Job Application

Applications go out under someone's real name and cannot be recalled. A wrong salary figure, an overstated year count, or a legal declaration answered carelessly follows them into interviews and offer negotiations.

Two goals in tension, both of which matter:

**Minimise how often the user has to intervene.** Front-load the questions. Most interruptions during an application are avoidable — the information was knowable at intake, and asking mid-form breaks their attention for something that could have been settled once.

**Never invent a fact.** Where information genuinely isn't available, stop and ask. Guessing is worse than interrupting.

## Phase 0: Browser check

This skill drives **Claude in Chrome** (`mcp__claude-in-chrome__*`). That specific integration matters rather than being an arbitrary preference: it can upload files to file inputs, open real native dropdowns, and work inside the user's already-authenticated sessions. In-app or headless browsers cannot do those things, and applications are mostly file uploads and dropdowns, so the wrong browser turns a ten-minute task into a dead end.

Check first:

```
mcp__claude-in-chrome__list_connected_browsers
```

An empty list means it is not connected. Stop and tell the user plainly:

> This needs the Claude for Chrome extension, because job forms require file uploads and native dropdowns that other browsers can't drive. Install it from the Chrome Web Store, connect it, and make sure you're signed in to LinkedIn and any careers sites in that Chrome profile. Tell me when it's ready.

Do not fall back to another browser and carry on quietly. You will get several steps in, hit a resume upload, and have to unwind. If the user prefers a different setup, say what will and won't work rather than discovering it mid-application.

Once connected, confirm the user is signed in to LinkedIn in that profile before searching, since logged-out LinkedIn silently returns a reduced, public view.

## Phase 1: Intake (once)

Run this before the first application. It is what makes everything afterwards low-touch.

### Resume

Ask for the resume path. Read it, extract the fields listed in `references/storage.md`, and **show the user what you extracted before saving.** PDF extraction is lossy and an error here propagates into every future application.

### The intake interview

Resumes systematically omit things application forms demand. Ask these together, in one pass, explaining that it means you won't need to interrupt later:

**Compensation** — current CTC, and whether that is fixed or total including variable and equity. Expected CTC. Forms ask for these differently and a total figure entered in a fixed field misrepresents them.

**Availability** — notice period in days.

**Work authorization, per country.** Not a single yes or no. Which countries can they work in without sponsorship? Would they require sponsorship elsewhere? Forms ask "authorized to work in [country]" and the honest answer varies by country.

**Relocation** — willing to relocate at all, and if so where. Postings routinely bury a relocation requirement in the body while listing a different city.

**Work setup** — comfortable with on-site, hybrid, fully remote. How many office days is acceptable.

**Per-role locations.** Resumes give dates but rarely cities. Walk through each role and get the city. This one question removes a whole class of guessing.

**Education months.** Resumes give years; forms want month and year.

**Experience framings.** Total years. Years in the target function. Years in any adjacent category forms commonly ask about but the resume doesn't state — for a PM that might be years as a developer, years managing people, years building AI products.

**Legal declarations.** Any past or present association with a large audit firm (Deloitte, PwC, EY, KPMG) including as employee, contractor or intern, since companies audited by them ask. Whether they or a close relative is or was a government official. Any conflicts of interest with specific companies.

**Demographics** — gender, ethnicity, veteran and disability status appear on many forms. Ask whether they want you to answer these, prefer "decline to disclose", or always leave them blank.

**Submission preference** — always stop before Submit, or submit when everything is verified. Default to stopping. See the warning under Submitting about why "I will not click Submit" is not by itself a guarantee.

Save these through the answer store, marking compensation, authorization and demographics as `sensitive`. Ask separately whether each sensitive value may be *stored*, since permission to use a value now is a different decision from permission to keep it.

### Profile hygiene

Check the resume against the user's LinkedIn headline and any existing ATS profiles. Stale claims — an old years-of-experience figure, a previous job title — travel with every application. Flag contradictions now.

## Phase 2: Finding roles

When asked to find jobs rather than apply to a specific one, treat it as **research across several channels, not one search on one site.**

LinkedIn is one index with loose keyword matching, and searching only there reliably produces a false conclusion: that a role type "barely exists", when the openings are sitting on company boards and startup aggregators LinkedIn never indexed. Read `references/sourcing.md` for the channel map, then sweep general aggregators, startup-native boards, any regional boards that apply, and the ATS boards of target companies directly. Vary the query too — "AI PM", "GenAI PM", "Agentic AI PM", "LLM PM" return substantially different sets.

Dedupe by company and normalised title, preferring the company's own ATS link over aggregator copies. **Report which channels you searched, including ones that returned nothing** — an empty channel is a finding, whereas silence about it reads as coverage.

Then **read each surviving posting's full body before shortlisting.** Titles are marketing:

- "Product Manager, User Voice AI and Agentic Experiences" was a feedback-ingestion platform role: APIs, serialization, pipelines. No AI product ownership.
- A posting listed "Mumbai, Hybrid" required full relocation to Bangkok, stated far down the body.
- An "$80/hr Product Manager (Tech)" posting was data-labelling contract work.

For each shortlisted role capture: whether the body matches the title, seniority band, real location and relocation requirement, sponsorship stance, and **the referral signals** described below.

**Application quotas.** Some employers cap applications — Google Careers allows three per thirty days; Workday tenants often block reapplying for six or twelve months. When you see a quota, raise it before spending a slot. Burning two of three slots on mismatched roles is an invisible loss: nothing errors, there are simply fewer chances left.

## Phase 3: Referrals come first

LinkedIn shows, on most postings: first-degree connections at the company, alumni from the user's past employers, the named job poster, and the recruiter. This is the highest-leverage information on the page and easy to walk past.

**A referral on a role with 200 applicants is worth more than being applicant 201.** So for any role with a connection, surface it *before* filling the form, and treat "apply plus referral message" as the default plan rather than applying alone.

Draft the referral message and put it in the dashboard for the user to send. Sending on their behalf needs explicit per-message permission.

If a form asks "were you referred by an employee," and a referral is realistically obtainable, raise it before answering — answering "no" forecloses something worth having.

## Phase 4: Filling

Identify the ATS and read `references/platforms.md` for its known blockers, so you can tell the user upfront what will need them.

Work in order, and **verify every few fields rather than at the end.** Long forms re-render as you fill: dropdowns shift, clicks land on neighbouring options, scroll position moves a target between reading its coordinate and clicking. Silent mis-fills are the normal failure mode.

Prefer element references over coordinates. When you must click by coordinate, screenshot immediately before and confirm immediately after.

Recurring mechanics:
- Native selects inside iframes often won't open a visible menu. Focus the field and type the exact option label.
- Location and school fields are usually autocompletes that reject free text: type a prefix, click the suggestion.
- Resume upload needs the file input element, not the visible button, which opens an undrivable OS picker.
- Some fields validate silently: numeric salary fields reject "50 LPA", URL fields reject non-matching domains.

**Fill only from the profile, the answer store, or this conversation.** If a required field asks for something unknown, leave it and record it as pending. Do not pattern-match a plausible answer — users cannot audit twenty fields, so anything invented survives to submission.

When the options don't include an accurate answer, pick the closest truthful one and say what you picked and why. If the honest option is weaker than an available exaggeration, still pick the honest one and let the user override.

**Legal declarations** get cross-checked against work history rather than answered by default. Auditor-independence questions, government-official status, conflicts of interest, and truth attestations all belong to the user. Never tick a truth attestation, especially when any field holds inferred data — that is certifying your guess as their fact.

## Hard stops

Say so plainly rather than working around them:

- **Credentials.** Never type passwords or create accounts.
- **CAPTCHAs.** Never attempt them.
- **Outbound messages.** Emails and LinkedIn messages need explicit per-message permission. Draft, show, wait.
- **Personal disclosures.** Demographics belong to the user unless intake said otherwise.

## Submitting

**Do not assume "I will not click Submit" is sufficient protection.** On a real LinkedIn Easy Apply flow with a Greenhouse backend, closing the modal via its X submitted the completed application. Treat any interaction with a complete form as potentially final. If you must close or navigate away, say so first, and afterwards check whether it submitted rather than assuming.

After any step that might have submitted, **verify**: look for a confirmation state, an "Application submitted" badge, a `formResponse` URL, or a job-tracker entry. Report what you observed. If you cannot confirm, say you cannot confirm.

Log `reviewed` when a form reaches final review; log `completed` only on confirmed submission. Keeping these apart prevents duplicate applications weeks later.

## Phase 5: The dashboard

After a working session, generate a dashboard artifact. The user has been away while you worked; the dashboard is how they act on it in minutes rather than reconstructing state from conversation.

```bash
python3 "<skill-dir>/scripts/dashboard.py" --out <path>.html
```

It reads the store and produces four sections:

1. **Needs you** — every blocked application, what specifically is missing, and a link that opens the exact page. This is the section that matters; put it first and make each item one click plus one action.
2. **Referral opportunities** — roles where the user has a connection, with the drafted message ready to copy.
3. **Submitted** — what went out, so nothing gets applied to twice.
4. **Watch list** — roles found but not yet started.

Then publish it with the Artifact tool and give the user the link.

Regenerate it whenever the state meaningfully changes. Pass `--url` for the same artifact URL rather than creating a new one each time.

## Running as a standing agent

The natural shape of this work is not one long session. It is a **cycle that reruns**: sweep for new postings, apply where nothing is blocking, report what needs the user. Roles appear hourly and the best ones have single-digit applicant counts for a short window, so recurring beats exhaustive.

### The scan cycle

One cycle is:

1. **Sweep** the channels in `references/sourcing.md`, filtered to postings newer than the last run.
2. **Dedupe** against history — `store.py history-status` gives the latest event per application, which is the guard against reapplying.
3. **Triage**: read full bodies, rank on fit and on applicant-count-versus-age.
4. **Apply** to anything that needs no new information, using the stored profile and answers.
5. **Park** anything blocked as a session with its pending fields and reasons.
6. **Regenerate the dashboard** and republish to the same artifact URL.
7. **Report**: what is new, what went out, what needs them, in a few lines.

Steps 1 through 5 need no user input, which is the entire point of the intake phase. A cycle that interrupts three times has usually skipped something that intake should have captured.

### Triggering it

**On demand** — the user says "check for new jobs" or "run a scan". Run one cycle and report.

**On a schedule** — for recurring runs without being asked, use the `/loop` skill for interval or self-paced repetition, or a scheduled task for fixed times. A daily morning run suits most searches; hourly is justified only while chasing very fresh postings, and mostly returns nothing.

Between cycles, hold the state in the store rather than in conversation. A cycle should be able to start cold, read the store, and know exactly where things stand.

### Keeping the dashboard current

Republish to the **same artifact URL** every cycle by passing the stored URL to the Artifact tool. The user keeps one bookmark that is always current, rather than accumulating links.

Be accurate about what this is: the page is regenerated when a cycle runs, not continuously live. If asked for genuinely live updating, say plainly that a published page can only refresh itself where the runtime grants it a data capability, and check `artifact-capabilities` for what is actually available rather than promising it.

Record the artifact URL in the store so later cycles, including ones in fresh sessions, update rather than duplicate it.

### Reporting between cycles

Keep it short and factual. What is new since last time, what you submitted, what is blocked and why. Quiet cycles should say so in one line rather than manufacturing activity — "swept 6 channels, nothing new matching" is a complete and useful report.

Never claim a submission you did not observe. If a cycle ends uncertain whether something went through, say so and log `reviewed` rather than `completed`.

## Storage

Persistent state lives in `~/.job-application/`, reached only through `scripts/store.py`. Full command surface in `references/storage.md`.

The key idea: **every stored value carries a confidence state.** Anything you inferred rather than were told is marked `inferred` and gets re-confirmed rather than reused silently. A guess that hardens into a fact is how these systems produce quiet inaccuracies at scale.
