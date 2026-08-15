# Changelog

## Unreleased

### Safety and correctness
- Page content is now explicitly data, not instructions: prompt-injection defenses for postings and forms, out-of-scope data requests (bank details, government ID) are hard stops, sensitive answers only go to fields that plainly ask for them.
- Write-ahead `submitting` event makes submission crash-safe: a session dying mid-submit can no longer cause a duplicate application. Orphans surface in `stats` (`needsVerification`) and on the dashboard.
- Answer matching hardened: fuzzy threshold raised to 0.75 ("product management" no longer matches "project management"), sensitive answers never fuzzy-match, near-misses return value-free candidates instead of a silent best guess.
- Exclusion list at intake — never applies to the current employer or listed companies.
- Dashboard sanitizes scraped URLs (http/https only) and escapes all store data.

### Accuracy and cost per application
- `answers-resolve` resolves a whole form's questions in one call; missing info is asked once, not field by field.
- Verification is read-back (DOM value vs. fill plan, string compare) instead of screenshot-eyeballing; a pre-submit manifest diffs every field.
- Staged triage: metadata gate before full-body reads; posting extractions and company briefs cached in watch entries, read once ever.
- Heavy browser work isolated per sweep/per fill so page dumps don't compound across a cycle.

### Research
- Persistent sweep plan (queries × geos × channels) with per-cell last-swept stamps for incremental cycles.
- Explicit fit rubric: intake-derived hard filters, then weighted scoring with recorded reasons.
- Five-fact company brief per shortlisted role.
- Outcome events (`response`, `interview`, `offer`, `rejected`) with per-source conversion via `store.py stats`; sweep budget follows what converts.

### Quality and trust
- `references/tailoring.md`: user's voice from writing samples, story bank, truth ledger (every claim traceable), resume variants with per-application tracking.
- Practice form fixture reproducing real ATS hazards, including a planted injection trap — first runs rehearse before touching a real application.
- 18-test unit suite for the store and dashboard.
- `meta-set`/`meta-get` for operational state (dashboard artifact URL, sweep stamps); volume caps and pacing rules.
