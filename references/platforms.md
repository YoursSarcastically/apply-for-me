# Platform recipes

Identify the ATS from the URL, then follow its recipe. Two purposes: tell the user what will block them **before** spending twenty actions finding out, and never re-derive a form's mechanics that a previous cycle already learned.

Every recipe records the **cheapest known path**. If you find yourself probing a layout this file already describes, read it first. If you learn something new, add it here — that is the only way the cost per application goes down.

## Blocker summary

| Platform | URL contains | Typical cost | Expected blocker |
|---|---|---|---|
| LinkedIn Easy Apply | in-app modal | ~6 calls | **Closing the modal can submit.** JS reads blocked |
| Ashby | `jobs.ashbyhq.com` | ~6 calls | None. Real file inputs. The cheapest ATS |
| Greenhouse | `job-boards.greenhouse.io` | ~10 calls | Invisible reCAPTCHA (passes). Company iframes need the embed URL |
| Google Forms | `docs.google.com/forms` | ~5 calls | Resume upload uses the Drive picker |
| Workday | `*.myworkdayjobs.com` | ~25 calls | Account creation. 5 steps, custom widgets, stripped attributes |
| Amazon | `amazon.jobs` | ~20 calls | `passport.amazon.jobs` account. **Stored profile goes stale** |
| BrassRing | `sjobs.brassring.com` | blocked | Resume upload sits in a cross-origin iframe |
| SuccessFactors | `career*.sapsf.com` | blocked | Account wall before the form is visible |
| iCIMS | `*.icims.com` | blocked | Account creation plus hCaptcha |
| Google Careers | `google.com/about/careers` | blocked | Native OS file picker. 3 applications per 30 days |
| Lever | `jobs.lever.co` | ~10 calls | Radio buttons often sit under click-intercepting overlays |

Account creation, password entry, and CAPTCHAs are hard stops. Say so early rather than discovering them at field twenty.

## The two techniques that decide cost

**Set a whole section in one JS call.** Where inputs are real DOM nodes, this replaces one tool call per field:

```js
function setVal(el, val){
  var p = el.tagName==='TEXTAREA' ? window.HTMLTextAreaElement.prototype
                                  : window.HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(p,'value').set.call(el, val);
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true}));
}
```

The native setter matters: React and Workday ignore a plain `el.value = x`. Always dispatch both events.

This fails on custom dropdowns, comboboxes and anything in a cross-origin iframe. Those need click-type-click and there is no way around it.

**Read back with JS, not screenshots.** Dump every field's value in one call and compare against the fill plan. A screenshot costs roughly ten times as much and is easier to misread. Reserve screenshots for widgets that will not report their state, and for the final pre-submit check.

---

## LinkedIn Easy Apply

Modal wizard, 2 to 5 steps, percentage indicator. The cheapest real applications after Ashby, because contact details and resume prefill.

**Recipe**
1. `find` the Easy Apply button and click by ref. A second click is often needed — the first only focuses.
2. Step through with `Next`. Contact info and resume are usually already correct; verify the resume filename and date rather than assuming.
3. Additional Questions is where the work is. Numeric fields reject text.
4. On the review step, **Tab from the last field** to reach Submit — see below.
5. Uncheck **Follow \<company\>**, which defaults to on and posts to their profile.

**Hazards**

- **Closing can submit.** A completed form closed via the X has been observed to submit. Never treat closing as a safe abort.
- **JS reads are blocked** on LinkedIn (`[BLOCKED: Cookie/query string data]`). Verify by screenshot here; this is the one platform where that is unavoidable.
- **The modal is often taller than the viewport and will not scroll** to reveal Submit. Click a non-interactive area inside the modal, then press Tab repeatedly. Focus moves through the remaining controls and scrolls the modal with it. Mouse scrolling over the modal body frequently does nothing.
- **Numeric fields validate silently.** "15 days" in a notice-period field was rejected with "Enter a decimal number larger than 0.0". Store bare-number variants of notice period and CTC for exactly this.
- **Prefills can be wrong.** An MBA question came prefilled as Yes for a candidate with no MBA. Always read prefilled values back.
- Coordinate clicks drift when the option list re-renders. A gender dropdown landed on "Non-binary" instead of "Man" this way. Prefer refs; screenshot immediately before and after any coordinate click.

## Ashby

`jobs.ashbyhq.com/<company>` lists roles; the form is at `/<company>/<uuid>/application`.

The cheapest ATS. Short forms, **real file inputs** (use `file_upload` with the ref), and stable structure. Fields appear progressively: name, email and resume first, then LinkedIn URL and Location once those are filled, so read the page again after the first pass.

Location is a combobox: click, type a prefix, click the suggestion. **Verify the value committed** — a viewport resize between reading the coordinate and clicking left it as "Bengaluru" instead of "Bengaluru, Karnataka, India".

Submit gives an inline green Success banner, not a new page.

## Greenhouse

**If the company's careers page iframes the form**, the fields are cross-origin and undrivable. Get the job id from the `gh_jid` query parameter or the posting's anchor href, then go directly to:

```
https://job-boards.greenhouse.io/embed/job_app?for=<company>&token=<jobid>
```

That renders the same form standalone and fully drivable. This single trick turned a blocked application into a submitted one.

**Mechanics**

- Field IDs are stable: `#first_name`, `#last_name`, `#email`, `#phone`. Resume is a real file input near a visible "Attach" button — target the input.
- Country, Location and month pickers are **search-input comboboxes**. Their `value` reads empty when closed even after a correct selection, so verify by screenshot, not by JS dump. This looks like a failure and is not.
- Employment and education blocks repeat via "Add another".
- reCAPTCHA is the invisible badge variety and passes without interaction. Its presence in the DOM is not a blocker.
- Submitting lands on `/confirmation`.

## Google Forms

Common for startups linking out from LinkedIn.

**Recipe**: one JS call sets every text and textarea via the native setter. Radios and checkboxes are `div[role=radio]` / `div[role=checkbox]` and need `.click()`, which can also go in the same call. A 17-field form dropped to about five tool calls this way.

Verify with `aria-checked` rather than trusting the click, and note the page reflows as you fill, so coordinate clicks drift badly.

**Resume upload uses the Drive picker.** Hard stop. Fill everything else, then hand over.

Submitting produces "Your response has been recorded" and a `formResponse` URL.

## Workday

Five steps: My Information, My Experience, Application Questions, Voluntary Disclosures, Review. Almost always behind account creation — pause there.

**The key discovery: Workday strips `data-automation-id` from rendered inputs.** Selector-based filling fails. Fall back to **positional indices** over `input[type=text], input:not([type])`, set them in one JS call, dump every index in the same call, then take one screenshot to confirm the mapping. Verified layout on the My Information step:

| Index | Field |
|---|---|
| 1 | First Name |
| 3 | Last Name |
| 4, 5, 6 | Local Given / Middle / Family Name |
| 7 | Address Line 1 |
| 8 | City |
| 9 | Postal Code |

Indices 0 and 11 hold hex session tokens; ignore them.

**State, Country Phone Code and all other dropdowns are custom widgets** that ignore programmatic setting. Click to open, type a prefix (`Karn`), then click the highlighted option. Typing without opening does nothing.

Work Experience often **prefills from LinkedIn** when the application is entered from a LinkedIn link. Check it against the resume rather than retyping it.

Use "Save and Continue" between steps; stop before the final action.

## Amazon (`amazon.jobs` + Passport)

Needs a `passport.amazon.jobs` account, which the user must create. Once it exists, applications are fast because the profile persists.

**That persistence is the trap. Audit the stored profile before every application.** Observed on a real account: the attached resume was **two years old**, the employer list omitted the three most recent jobs including the current one, and the skills field listed hadoop and figma with no AI terms at all. Every section showed a green ✓.

Check, in order: Resume filename and upload date, Work history employer list, Skills, Education school name, Contact information.

**Mechanics**

- The apply link may offer only "Apply in English" first; click through it.
- Job-specific questions are `<select>` elements and **can all be set in one JS call**.
- The skills field caps at **200 characters** with the error appearing only on Continue. Draft short.
- Work Eligibility holds the legal declarations. Answer from the stored bank, never by default.
- Before submitting, a consent dialog asks permission for AI recommendations, recruiter referrals and interview transcription. Declining triggers a second dark-pattern confirmation ("Are you sure? You'll miss out..."). Take the privacy-preserving option and tell the user it is changeable under Preferences.
- Success is confirmed by a `summary?result=success` URL.

## BrassRing

`sjobs.brassring.com`. Offers **"Skip sign in"**, which gets you into the form without an account — worth taking.

But the résumé upload widget is a **cross-origin iframe**, so the file input is unreachable and "Browse" opens a native OS picker. Fill what you can and hand over for the upload.

## SuccessFactors

`career*.sapsf.com`. The Apply button leads straight to a sign-in wall with "Create an account". The form is not visible until then. Hard stop; ask the user to sign in, then fill in one pass.

## Lever, iCIMS, Google Careers, SmartRecruiters

**Lever**: form sits below a long job description. Radio buttons frequently have overlays intercepting clicks; a click that does not register is usually this.

**iCIMS**: account creation plus hCaptcha before the form opens. Effectively a full stop.

**Google Careers**: **quota of three applications per 30 days** — raise it before spending a slot. The stored profile goes stale like Amazon's. Uploading a new resume triggers a re-parse that repopulates work history and **wipes city and country on every job**. Upload offers a native OS picker or Drive. The final gate is a truth attestation; do not tick it.

**SmartRecruiters**: usually reached through LinkedIn Easy Apply rather than directly, so follow the Easy Apply recipe.

## Email applications

Some postings use a `mailto:` link. Draft the body, attach the resume through the file input, and **stop**. Sending needs explicit permission. Say clearly that it is a draft and confirm the attachment landed.
