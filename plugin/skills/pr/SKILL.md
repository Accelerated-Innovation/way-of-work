---
name: pr
description: Open or fix a pull request that passes the Way of Work checks — conventional title, every required description section, screenshots for UI, impact and dependency notes, primary reviewer as assignee, size kept reviewable. Use when the user says "open a PR", "create pull request", "ready for review", or a PR is failing the "wow / standards" check.
---

# Pull request (Way of Work §4, §13.1)

`WOW` below means `python "<this skill's base directory>/../../validators/wow.py"`.

## 1. Gather

```bash
git fetch origin
BRANCH=$(git rev-parse --abbrev-ref HEAD)
```
- **Base:** `develop` for `feature/*` and `fix/*`; `prod` for `hotfix/*`. Promotions between environment branches are `/wow:release`, not this skill.
- `git log --no-merges origin/<base>..HEAD` · `git diff --stat origin/<base>...HEAD` · `git diff --name-status origin/<base>...HEAD`
- Read the diff itself, enough to explain it.

## 2. Run the same checks CI runs

```bash
WOW branch
WOW commits --base origin/<base>
WOW size --base origin/<base>
WOW migrations --base origin/<base>
WOW secrets --range origin/<base> HEAD
```
Fix failures before opening. Bad commit messages on an unpushed branch can be reworded; on a pushed branch, ask the user before rewriting history. If size is over ~400 lines, suggest how to split it or put it behind a feature flag, and if the user keeps it, say why in the description.

## 3. Write the title and description

**Title:** Conventional Commit style, e.g. `feat(plans): target plans can be archived`.

**Body:** use the repo's `.github/pull_request_template.md` if it exists; otherwise these exact headings:

```markdown
## What changed and why
## Work item
## Screenshots
## Impact (database / configuration / infrastructure)
## How it was tested
## Dependency justification        <!-- only when dependency manifests changed -->
```
- **Work item:** a link (use `work_item_url` from `.wow.toml` if set) or the ID.
- **Screenshots:** required when UI files changed. Ask the user for them; never invent images. Otherwise `N/A`.
- **Impact:** migrations (and whether they are re-runnable / expand-migrate-contract), new settings (added to the config template and every environment?), infrastructure, contract changes. Write `None` if there is none.
- **How it was tested:** what was actually run. Ask if you don't know.
- **Dependency justification:** what each new or upgraded dependency is for and why this library.
- If any code was produced with AI assistance, it is reviewed to the same standard; no special label is needed.

Validate: write the body to a temp file and run `WOW pr-body --base origin/<base> --body-file <file>`.

## 4. Reviewers (§13.1)

- **Primary reviewer** (expected to approve) goes in **assignee**. Suggest someone who knows the area: `git log --format='%an <%ae>' -- <changed paths> | sort | uniq -c | sort -rn`, excluding the author. Confirm with the user and get their GitHub handle.
- Optionally add **awareness reviewers**, ideally someone outside the area for learning.
- If a **contract another repository depends on** changes, add a reviewer from the consuming team (MUST) and note that both must be released together.

## 5. Open it

```bash
git push -u origin "$BRANCH"
gh pr create --base <base> --title "<title>" --body-file <file> --assignee <primary> --reviewer <primary>[,<others>]
```
If `gh` isn't available, give the user the title and body to paste.

## 6. Fixing a failing "wow / standards" check

Run `gh pr checks` / read the check summary, fix the description with `gh pr edit --body-file`, or fix commits/branch as above. The check re-runs when the description is edited.

Reply with the PR link and any open item (e.g. "add screenshots").
