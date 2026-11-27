# GitHub setup for the Way of Work

What has to be switched on in GitHub itself. These are settings, not checks; `/wow:audit` reports on them per repository.

## 1. Organisation (org owner, once)

### Secrets: push protection is the first wall
Settings → Code security → Configurations → create **"Way of Work"** and apply it to **all repositories**, with *Enforce configuration* on so repositories can't switch it off:

- **Secret scanning: Enabled**, **Push protection: Enabled**. OpenAI (`sk-proj-…`) and Anthropic (`sk-ant-…`) keys are GitHub-supported patterns, so a push containing one is rejected before it reaches GitHub.
- **Push protection bypass: delegated.** Developers can't click "allow" themselves; a reviewer group (the repository leads) approves or denies bypass requests.
- **Custom patterns** (Settings → Code security → Secret scanning → Custom patterns) for what GitHub doesn't detect well, e.g. Azure OpenAI keys assigned in config: copy the regexes from [`config/gitleaks.toml`](../config/gitleaks.toml).
- For private repositories this needs **GitHub Secret Protection** (part of Advanced Security). If the org doesn't have it, the `wow / secrets` check (gitleaks) and the local hooks still apply, but nothing stops a push before CI runs, so the licence is strongly recommended.

### Actions
- Settings → Actions → General: allow `Accelerated-Innovation/way-of-work` reusable workflows. If `way-of-work` is **private**, set its Actions access to *"Accessible from repositories in the organization"*, and create an org secret `WOW_TOKEN` (GitHub App installation token or fine-grained PAT with read on `way-of-work`). Making `way-of-work` public or internal avoids the token for reading.
- `WOW_TOKEN` with **contents + pull-requests write** on product repos also lets back-merge PRs (opened after a hotfix) start their own checks. PRs opened with the default `GITHUB_TOKEN` don't trigger workflows.

### Teams
- One team per repository lead group, used for promotion rulesets, `CODEOWNERS` and push-protection bypass review.
- Code review auto-assignment on the developer team (round robin or load balance), per §13.1.

## 2. Each repository (repository lead)

| Setting | Value | Rule |
|---|---|---|
| Branches | `develop` (default), `staging`, `demo`, `prod` | §2 |
| Merge button | Allow **merge commits**; squash/rebase off (or limited by ruleset) | §4 |
| Automatically delete head branches | On | §2 (short-lived branches) |
| Ruleset `templates/rulesets/environment-branches.json` | Import: PR + 1 approval + last-push approval, no force push/delete, required checks `wow / standards`, `wow / secrets` **plus the repo's own build/test checks** | §2, §4 |
| Ruleset `templates/rulesets/promotion-branches.json` | Replace `actor_id: 0` with the lead team's ID (`gh api orgs/Accelerated-Innovation/teams/<slug> --jq .id`), then import | §2, §13.1 |
| Environment `prod` | Required reviewers = named production approver; deployment branch = `prod` only | §6.1 |
| Environments `develop`, `staging`, `demo` | Deployment branch = matching branch only; environment-scoped secrets until the vault is in place | §6.2 |
| Workflows | `wow.yml`, `wow-release.yml` from `plugin/templates/.github/workflows/` | §4, §5 |

Import a ruleset: Settings → Rules → Rulesets → New ruleset → **Import a ruleset**, or
`gh api -X POST repos/Accelerated-Innovation/<repo>/rulesets --input <file>.json`.

## 3. Rollout order
1. Org security configuration (push protection) — protects everything immediately.
2. Tag `way-of-work` `v0.1.0` (moves `v0`).
3. Per repository: add `wow.yml` in a PR → let it run → then make its checks required in the ruleset (making a check required before it has ever run blocks every PR).
4. `/wow:audit --history` per repository; rotate anything it finds.
