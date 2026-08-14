# Sourcing: searching beyond LinkedIn

LinkedIn is one index, not the market. Treating it as the whole market produces a predictable failure: you conclude a role type "barely exists" when in fact you searched one channel with loose keyword matching.

A real symptom of this: a senior AI product search on LinkedIn returned 1,000+ results that were overwhelmingly banking and insurance PM roles, while the actual AI-native openings sat on company boards and startup-specific aggregators that LinkedIn never indexed.

Run sourcing as **research**, not as one query. Sweep several channels, dedupe, then rank.

## Channel map

Pick by what the user is looking for. Two or three channels usually beat exhaustive coverage of one.

### General aggregators

| Source | Search URL pattern | Strength |
|---|---|---|
| LinkedIn | `linkedin.com/jobs/search/?keywords=&location=&f_TPR=r604800` | Network signals, recency, Easy Apply |
| Indeed | `indeed.com/jobs?q=&l=&fromage=7` | Widest coverage, many duplicates |
| Glassdoor | `glassdoor.com/Job/jobs.htm?sc.keyword=` | Salary context |
| Google Jobs | search `<role> jobs <location>` and open the jobs pane | Aggregates boards LinkedIn misses |

### Startup and tech-native

Where AI-native and early-stage roles actually live, and where the LinkedIn sweep is weakest.

| Source | URL | Strength |
|---|---|---|
| Y Combinator | `workatastartup.com/jobs` | YC portfolio, often unlisted elsewhere |
| Wellfound (AngelList) | `wellfound.com/jobs` | Equity ranges shown |
| Hacker News Who's Hiring | `hn.algolia.com/?query=<role>&type=comment` | Monthly thread; direct-to-founder |
| Otta | `otta.com` | Curated, strong filters |
| Built In | `builtin.com/jobs` | Tech hub cities |

### Regional

| Region | Sources |
|---|---|
| India | Naukri, Instahyre, Cutshort, Hirist, Foundit |
| Middle East | Bayt, GulfTalent, Naukrigulf |
| Europe | Otta, Welcome to the Jungle, Honeypot |
| Remote-first | RemoteOK, WeWorkRemotely, Remotive |

### Company boards directly

The highest-signal channel and the most often skipped. When a company is a genuine target, go straight to its careers page — roles appear there first, and aggregator listings are frequently stale or truncated.

Most run on a handful of ATS platforms with predictable URLs:
- `job-boards.greenhouse.io/<company>`
- `jobs.lever.co/<company>`
- `jobs.ashbyhq.com/<company>`
- `<company>.wd1.myworkdayjobs.com`

Searching `site:job-boards.greenhouse.io <role keyword>` on Google finds roles across every Greenhouse customer at once. The same works for Lever and Ashby.

## How to run the sweep

**1. Decide the query set.** Titles vary more than people expect. "AI Product Manager", "GenAI Product Manager", "Agentic AI PM", "LLM Product Manager", "ML Product Manager", "Applied AI PM" surface substantially different results. Search each; do not assume one covers the others.

**2. Sweep in parallel where the tooling allows**, keeping one tab per source so state does not collide.

**3. Dedupe by company plus normalised title.** The same role appears on four aggregators. Keep the listing that links to the company's own ATS, since that one is current and applying there avoids a redirect chain.

**4. Read each surviving posting's full body.** Titles misdescribe roles often enough that this is not optional. Check for relocation buried in the body, seniority below the title, contract-versus-permanent, and sponsorship exclusions.

**5. Rank on fit, not recency.** Weight: how squarely the body matches the user's actual work; whether a referral path exists; applicant count and posting age; and whether the seniority band matches.

**6. Report what you searched**, including channels that returned nothing. "No ServiceNow AI PM roles in India this month" is a finding. Silence about a channel reads as coverage when it was absence.

## Signals worth capturing per role

Beyond title, company, location and link:

- **Applicant count and posting age.** A role with 3 applicants an hour old is a different proposition from 200+ applicants at two weeks. This single pair changes prioritisation more than almost anything else.
- **Referral path.** First-degree connections, alumni from past employers, named recruiter or poster. See the referral section in SKILL.md.
- **The apply route.** Easy Apply, company ATS, email, or a form. This determines what will block, per `platforms.md`.
- **Quota or reapply limits.**
- **Compensation**, when shown. Glassdoor and Wellfound often show ranges that LinkedIn hides.

## Diminishing returns

Sourcing has a stopping point, and recognising it is part of doing this well.

When new searches keep returning roles already seen, the market for that profile in that geography has been covered. Say so. At that point the highest-value work shifts from finding more roles to **converting the ones already found**: referral outreach, finishing part-filled applications, tightening the resume.

Volume past that point is motion, not progress. Users often ask for more roles when what they actually need is to close the loop on the roles they have.
