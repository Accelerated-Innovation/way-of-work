---
name: audit
description: Audit a repository's conformance to the Way of Work and set up what's missing — CI wiring, PR template, secret hygiene (including a full-history scan for API keys), versioning, README/ADRs, and GitHub settings (rulesets, environments, push protection, merge methods). Use for "is this repo compliant?", "onboard this repo to Way of Work", "set up the repo", "check for leaked keys", or filling the §13.2 setup table.
---

# Repository audit and setup (Way of Work §2–§13)

`WOW` means `python "<this skill's base directory>/../../validators/wow.py"`.
`TEMPLATES` means `<this skill's base directory>/../../templates`.

## 1. Local audit
Run from the repository root:
```bash
WOW audit --history
```
`--history` scans every commit on every branch for secrets. **If it finds an API key, that comes first:** tell the user it must be rotated now (it is compromised regardless of history rewriting), then continue.

## 2. GitHub settings (needs `gh` with repo admin read)
```bash
R=$(gh repo view --json nameWithOwner -q .nameWithOwner)
gh api repos/$R --jq '{default_branch, allow_merge_commit, allow_squash_merge, allow_rebase_merge, delete_branch_on_merge, visibility, security: .security_and_analysis}'
gh api repos/$R/rulesets
gh api repos/$R/environments --jq '.environments[] | {name, rules: [.protection_rules[]?.type]}'
gh api repos/$R/branches --paginate --jq '.[].name'
```
Check against:
| Expectation | Rule |
|---|---|
| Default branch is `develop`; `develop`, `staging`, `demo`, `prod` exist | §2 |
| Ruleset on all four: PR required, 1 approval, last-push approval, no force-push/deletion, required checks `wow / standards` and `wow / secrets` (+ the repo's own build/test) | §2, §4 |
| Merge commits allowed on develop (rulesets `allowed_merge_methods: ["merge"]`) | §4 |
| staging/demo/prod: only the repository lead can merge | §2, §13.1 |
| Environment `prod` has required reviewers (named approver) | §6.1 |
| Secret scanning **and push protection** enabled; bypass delegated, not self-service | §3, §6.2 |
| CODEOWNERS only on high-risk paths | §13.1 |

## 3. Report
A short table: area · status (✅/⚠️/❌) · what to do. Then the repo's row for the §13.2 table:
`| <repo> | Rulesets ☐/☑ | Environments ☐/☑ | PR check ☐/☑ | Auto-deploy develop ☐/☑ | Auto-deploy staging ☐/☑ |`
(auto-deploy: look for workflows triggered on push to develop/staging that deploy.)

## 4. Fix (only with the user's go-ahead, on a work branch via `/wow:start`)
Copy from `TEMPLATES`, adapting to the repo:
- `.github/workflows/wow.yml` and `.github/workflows/wow-release.yml` (caller workflows)
- `.github/pull_request_template.md`
- `.wow.toml` (set `[version] file`, migrations paths, config template/environments, manifest paths for this stack)
- `.pre-commit-config.yaml` (secret scan + commit message checks for people not using Claude)
- `.gitignore` additions from `gitignore-secrets.txt`; `.env.example` with placeholders only
- `CODEOWNERS` for high-risk paths
- README sections that are missing (what it is, run locally, test, deploy); `docs/adr/0001-record-architecture-decisions.md`

GitHub settings: `TEMPLATES/rulesets/*.json` can be imported (Settings → Rules → Rulesets → Import) or applied with
`gh api -X POST repos/$R/rulesets --input <file>` after replacing the lead team ID placeholder (`gh api orgs/<org>/teams/<slug> --jq .id`). Changing settings needs admin rights: show the user the exact commands and run them only when they confirm. Org-level items (push protection enforcement, delegated bypass, custom secret patterns) are in `docs/github-setup.md` in the way-of-work repo; point the user to an org admin for those.
