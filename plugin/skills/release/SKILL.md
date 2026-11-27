---
name: release
description: Promote a build through the environments (develop → staging → demo → prod) or ship a hotfix, the Way of Work way — SemVer bump from commits, promotion PRs with release notes (version, highlights, migrations, known issues, cross-component version dependencies), production tag, and hotfix back-merge. Use for "promote to staging", "release to prod", "cut a release", "ship the hotfix", "write release notes".
---

# Release and promotion (Way of Work §2, §5, §6, §11)

Repository leads merge promotions; this skill prepares them. `WOW` below means `python "<this skill's base directory>/../../validators/wow.py"`.

```bash
git fetch origin --tags
```
Ask which move the user wants if it isn't clear: **staging**, **demo**, **prod**, or **hotfix**.

## A. Promote develop → staging (this is where the version is bumped)

1. **What's going out:** `git log --no-merges origin/staging..origin/develop`. List merged PRs: `gh pr list --base develop --state merged --search "merged:>=<date of last promotion>"`.
2. **Next version:** on an up-to-date develop checkout, `WOW next-version --since <last tag or origin/staging>`. feat → MINOR, fix/perf → PATCH, breaking → MAJOR. Show the reason; let the user override.
3. **Bump on develop** (a version change needs its own PR, because develop is protected):
   ```bash
   git switch -c release/vX.Y.Z origin/develop
   # edit the single version source (WOW version --print shows the current one; the file is in .wow.toml or auto-detected)
   # optionally prepend `WOW changelog --version X.Y.Z` output to CHANGELOG.md
   git commit -am "chore(release): vX.Y.Z" -m "Refs: <release work item or n/a>"
   git push -u origin release/vX.Y.Z
   gh pr create --base develop --title "chore(release): vX.Y.Z" --body-file <notes>
   ```
   After it merges:
4. **Promotion PR** `develop → staging`, title `chore(release): promote vX.Y.Z to staging`, body = release notes (below). Request the repository lead.

## B. staging → demo, demo → prod
No version bump (it was bumped for staging). Open `gh pr create --base demo --head staging` / `--base prod --head demo` with the same release notes, updated for anything learned in QA. For **demo**, confirm the Ready-for-demo checklist (`/wow:done`) and the demo cut-off. For **prod**, the named production approver must approve the deployment; the release workflow then tags `vX.Y.Z` and publishes the GitHub release from this PR's body.

## C. Hotfix
1. Branch from prod with `/wow:start` (`hotfix/<id>-<slug>`).
2. Fix, with a test that fails before the fix. Bump **PATCH** in the hotfix branch.
3. PR `hotfix/* → prod`, release notes below.
4. After merge the release workflow tags it and opens back-merge PRs `prod → develop` (and into staging/demo if they're ahead). Make sure they're merged **the same day**.

## Release notes (PR body)

The PR checks need the standard sections; put the release notes inside them:

```markdown
## What changed and why
Release vX.Y.Z — <one-line theme>.
### Highlights
- <user-visible changes, from feat/fix commits; plain language>

## Work item
<IDs or links of every work item included>

## Screenshots
N/A (see individual PRs)

## Impact (database / configuration / infrastructure)
- Migrations: <list, and whether any are destructive or need manual steps>
- New/changed settings: <names; confirm set in the target environment>
- Infrastructure: <…>

## How it was tested
<staging QA / named tester / smoke test results>

## Release notes
- **Version:** X.Y.Z
- **Version dependencies:** <e.g. "needs Insights Portal API ≥ 2.4.0"> (MUST be stated, write "None" if none)
- **Known issues:** <…or None>
- **Rollback:** redeploy vA.B.C (previous version)
```
Derive highlights from `WOW changelog --version X.Y.Z --since <last tag>`, rewritten for stakeholders. Check merged PR descriptions for migrations, settings and contract changes; don't guess — ask the user about anything unclear.

## Rules
- Promotion only moves forward. Never cherry-pick or commit straight onto an environment branch; demo and prod are never patched by hand.
- Don't deploy floating tags (`latest`); artefacts carry the version and commit SHA.
- Every production release gets short release notes shared with stakeholders (§11): offer a 5-line summary the user can post in the release channel.
