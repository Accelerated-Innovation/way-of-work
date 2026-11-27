---
name: done
description: Check a work item against the Way of Work Definition of Done (§10) or the Ready-for-demo checklist (§13.4), gathering evidence from the PR, CI and deployments, and listing what's still missing. Use for "is this done?", "can I close 1234?", "ready for demo?", "DoD check".
---

# Definition of Done / Ready for demo (Way of Work §10, §13.4)

Report each item as ✅ verified (with the evidence), ❓ can't verify (ask the user), or ❌ missing (with the next step). Never mark something ✅ without evidence.

## Gather
- Work item: from the user, the branch name, or the PR. If a tracker is connected, read it (status, links, comments).
- PR: `gh pr list --search "<id>" --state all --json number,title,state,mergedAt,baseRefName,headRefName,url` then `gh pr view <n> --json body,files,reviews,statusCheckRollup,mergeCommit`.
- Deployment to development: `gh run list --branch develop --limit 20 --json name,conclusion,headSha,createdAt` (a successful deploy run whose commit contains the merge commit) or `gh api repos/{owner}/{repo}/deployments?environment=<dev env name>`.

## Definition of Done (§10)
- [ ] Merged through a reviewed PR (≥1 approval from someone else) with a passing build
- [ ] Tests added or updated, and passing (look for test files in the PR's changes)
- [ ] Database migrations included and verified (if schema changed)
- [ ] Contract changes documented and consumers updated (if a contract changed)
- [ ] UI checked against the design at supported widths and themes (if UI changed: screenshots in PR)
- [ ] Documentation updated where behaviour or rules changed
- [ ] Deployed to the development environment and smoke-tested
- [ ] Work item updated with the PR link and any release notes

## Ready for demo (§13.4) — only when asked
- [ ] Tested on staging by a **named** tester
- [ ] Any feature flag it needs exists and is **off by default**
- [ ] Migrations and configuration changes are listed on the work item
- [ ] A short "how to demo it" note, including the data it needs

Board flow: `In progress → In review → In develop → In staging (QA) → Ready for demo → On demo → Done`. The tester moves it to *Ready for demo*; the repository lead promotes to `demo`; the demo tester moves it to *On demo*.

## Output
The checklist with marks and evidence, then a one-line verdict ("Done" / "2 items open"). Offer to draft the missing pieces (e.g. the "how to demo it" note, or a work-item comment with the PR link) and, if a tracker is connected, to post them, only when the user says yes.
