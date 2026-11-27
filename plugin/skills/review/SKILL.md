---
name: review
description: First-pass code review of a pull request or local diff against the Way of Work engineering standards (security, tenancy, contracts, migrations, errors, logging, front-end safety, tests). Use when asked to "review this PR", "check my changes against the standards", or before requesting human review. Never approves; the human approval is still required.
---

# Review (Way of Work §4, §7, §8, §9, §13.1)

An AI first pass: catch issues early so the human reviewer can focus on design and behaviour. It does **not** replace the required human approval, so never submit an "Approve" review.

`WOW` below means `python "<this skill's base directory>/../../validators/wow.py"`.

## 1. Get the change
- PR: `gh pr view <n> --json title,body,baseRefName,headRefName,files` and `gh pr diff <n>`. Check it out (`gh pr checkout <n>`) if you need surrounding code.
- Local: `git diff origin/develop...HEAD`.
Read enough of the touched files to understand context, not only the hunks.

## 2. Mechanical checks first (don't repeat them by hand)
Run `WOW ci --base origin/<base> --head HEAD --base-branch <base> --head-branch <head> --body-file <pr body file> --title "<title>"` and report its failures briefly. CI enforces these anyway; your value is in what follows.

## 3. Judgment checklist
Report only what applies to this diff, each with `file:line`, the rule, and a concrete fix.

**Security & data (§7)**
- New endpoints require authorisation by default; nothing is accidentally anonymous.
- Tenant isolation goes through the central mechanism, never ad-hoc filters in callers; no query can cross tenants.
- Security-relevant actions (auth, permission, data export, admin changes) are audited.
- No secrets, tokens or personal data in logs, errors, or client bundles (§8, §11). Logs are structured and carry the correlation ID.

**Contracts (§7)**
- Removed/renamed fields, changed types or meaning = breaking. Needs a versioned contract or a coordinated release, a `!`/`BREAKING CHANGE`, and a consumer-team reviewer.
- Changes are additive where possible; consumers tolerate unknown fields. Contract docs are regenerated.

**Database (§7)**
- Schema change has a migration in the same PR; no edit to an applied migration.
- Re-runnable where possible; destructive changes follow expand → migrate → contract; data migrations and manual steps are called out in the PR.

**Errors, messaging, background work (§7)**
- Consistent error format with stable codes; no stack traces or queries leaked outside development.
- Consumers are idempotent and handle redelivery, retries and dead-lettering.

**Front-end (§8)**
- Design tokens/components only: no hard-coded colours, spacing, one-off styles.
- Any HTML from users, external systems or AI output is sanitised before rendering.
- No secrets/privileged tokens shipped to the client; backend calls go through the server-side layer, configured at runtime.
- Keyboard reachable, visible focus, semantic markup, WCAG AA contrast; works at narrow widths and in every theme.
- Display business rules live in one place, not repeated across components.

**Configuration & dependencies (§9, §11)**
- New settings exist in the config template (safe default) and every environment, same name everywhere.
- New dependencies are justified, maintained and pinned; no surprise framework upgrades.

**Tests (§7, §8)**
- Core business rules have unit tests; critical flows have integration tests.
- A bug fix comes with a test that fails without the fix.
- Warnings aren't suppressed without an explanatory comment.

**General**
- The code does what the PR says; edge cases, error paths, null/empty, concurrency.
- AI-generated code is held to the same standard: watch for invented APIs, dead code, over-broad try/catch, copy-paste duplication.

## 4. Report
Group as **Blockers** (a MUST is broken or a real bug), **Should fix** (a SHOULD, or risk), **Nits** (optional). Lead with the count of each. Be specific and brief; skip praise and restating the diff.

Post to GitHub only if the user asks: `gh pr review <n> --comment --body-file <file>` (or inline comments via the API). Use **comment**, not request-changes, unless the user is the primary reviewer and says otherwise (§13.1).
