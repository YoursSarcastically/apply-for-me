# Platform notes

Identify the ATS from the URL, then read the matching section. The point of this file is to let you tell the user what will block them **before** you spend twenty actions finding out.

## Blocker summary

| Platform | URL contains | Expected blocker |
|---|---|---|
| Greenhouse | `job-boards.greenhouse.io`, `boards.greenhouse.io` | reCAPTCHA at submit. Everything before it is drivable |
| LinkedIn Easy Apply | in-app modal | Native selects in an iframe. **Closing the modal can submit** |
| Google Careers | `google.com/about/careers` | Native OS file picker for resume. 3 applications per 30 days |
| Google Forms | `docs.google.com/forms` | Resume upload uses the Drive picker |
| iCIMS | `*.icims.com` | Requires account creation plus hCaptcha |
| Amazon | `amazon.jobs` | Separate `passport.amazon.jobs` login |
| SuccessFactors | `career*.successfactors.eu` | Requires account creation with a new password |
| Workday | `*.myworkdayjobs.com` | Usually account creation. Custom widgets throughout |
| Ashby | `jobs.ashbyhq.com` | Generally drivable. Location is a combobox |
| Lever | company domain, `?lever-source=` | Radio buttons often sit under custom overlays |

Account creation, password entry, and CAPTCHAs are all hard stops. Say so early.

## Greenhouse

Single long page. Click Apply to reveal the form.

Field IDs are stable: `#first_name`, `#last_name`, `#email`, `#phone`. Resume is a file input near a visible "Attach" button — target the input, not the button.

Country and location are searchable comboboxes: click, type a prefix, click the suggestion. Employment and education blocks use "Add another" to repeat. Month dropdowns respond to typing the full month name.

Screening questions sit below and vary by employer. Some are compliance rather than screening — see the legal declarations guidance in SKILL.md.

The submit button is visible from early on. Because the whole form is one page, avoid stray clicks near it.

## LinkedIn Easy Apply

Modal wizard, typically 2 to 5 steps, with a percentage indicator.

Contact details and resume usually prefill from the profile. Work history and education can auto-populate from the LinkedIn profile, which is worth checking against the resume — the two drift.

Two specific hazards:

**The modal's controls live in an iframe.** Accessibility-tree reads of the main document will not see them, and `form_input` by reference generally fails. Focus the field and type the exact option label instead; that selects reliably where clicking does not.

**Closing can submit.** A completed form closed via the X has been observed to submit. Do not treat closing as a safe abort.

If the user's LinkedIn headline contradicts their resume (a stale years-of-experience claim is common), flag it — the headline accompanies every Easy Apply.

## Google Careers

Signed-in flow with four steps: Careers profile, Role information, Voluntary self-identification, Review and apply.

**Quota: three applications per 30 days.** Stated at the top of the form. Raise it before spending a slot.

**The stored profile is often stale.** Check the attached resume's filename and date, and check that the legal name is split correctly across First and Last.

Uploading a new resume triggers a re-parse that repopulates work history, education and skills. The parse is decent on employer, title and dates, but leaves city and country empty on every job, and may create more job blocks than the user has roles.

Resume upload offers "My computer" (native OS picker, undrivable) and "Google Drive". If the file is not in Drive, the user must attach it.

The final gate is an attestation checkbox certifying accuracy. Do not tick it.

## Google Forms

Common for startups linking out from LinkedIn.

Radio buttons and checkboxes are `div[role=radio]` and `div[role=checkbox]`. The page reflows as you fill, so coordinate clicks drift badly. Verify by reading `aria-checked` rather than trusting the click.

Long forms often mix required and optional in ways the layout obscures — check for the asterisk.

Resume upload uses the Drive picker, which needs the user.

Submitting produces "Your response has been recorded" and a `formResponse` URL. That is your confirmation signal.

## Workday

Multi-page wizard, heavy custom widgets, usually gated behind account creation. Pause for the user there.

Dropdowns are custom: click, wait for the list, read options, click. Dates are format-sensitive. Use "Save and Continue" for intermediate steps and stop before the final action.

## Ashby, Lever, iCIMS

**Ashby**: simple single page. Location is a combobox needing type-then-click. There are two file inputs — the resume field and a separate autofill input. Use the resume field.

**Lever**: form sits below a long job description. Radio buttons frequently have overlays that intercept clicks; if a click does not register, that is usually why.

**iCIMS**: account creation plus hCaptcha before the form opens. Effectively a full stop.

## Email applications

Some postings use a `mailto:` link. Clicking it opens a compose window with the recipient and subject prefilled.

Draft the body, attach the resume through the file input, and **stop**. Sending needs explicit permission. Say clearly that it is a draft and confirm the attachment landed.
