# way-of-work

Accelerated Innovation's **Way of Work**, made executable: a Claude plugin (`wow`), the shared validators behind it, and the reusable GitHub workflows that enforce the same rules on every pull request.

> The rules are written once in [`plugin/validators`](plugin/validators). Claude (skills and hooks), local git hooks and CI all run that same code, so "Claude says it's fine" means "CI will pass".

```
Developer + Claude                          GitHub
──────────────────                          ──────
/wow:start  → branch name ✓                 push protection ── blocks API keys on push
/wow:commit → message ✓ secrets ✓           wow / standards ── branch, commits, PR description,
hooks       → no keys in files, no                              promotion, migrations, size,
              commits/pushes to env branches                    config, manifests, version
/wow:pr     → description ✓ size ✓          wow / secrets   ── gitleaks on the PR's commits
/wow:review → standards review (no approve) ruleset         ── 1 approval, required checks
/wow:release→ bump, notes, promotion PRs    wow-release     ── tag vX.Y.Z, release, back-merge
```

## What's here

| Path | What it is |
|---|---|
| `plugin/` | The Claude plugin **wow**: skills, hooks, validators, templates |
| `plugin/skills/` | `/wow:start` `/wow:commit` `/wow:pr` `/wow:review` `/wow:release` `/wow:audit` `/wow:done` |
| `plugin/hooks/` | PreToolUse guard: blocks secrets in files/commits, `--no-verify`, commits and pushes to `develop/staging/demo/prod`, bad commit messages |
| `plugin/validators/` | `wow.py` + `wow_validators` package. Python 3.11+, standard library only |
| `plugin/templates/` | What each product repository adds: caller workflows, PR template, `.wow.toml`, pre-commit, rulesets, CODEOWNERS |
| `.github/workflows/pr-checks.yml` | Reusable PR checks → `wow / standards`, `wow / secrets` (+ optional dependency review) |
| `.github/workflows/release.yml` | Reusable release on `prod`: tag, GitHub release, hotfix back-merge PRs |
| `config/gitleaks.toml` | Secret rules for CI (default gitleaks rules + stricter AI-provider rules) |
| `.pre-commit-hooks.yaml` | Same checks as git hooks for people not using Claude |
| `docs/github-setup.md` | Org and repository settings (push protection, rulesets, environments) |
| `docs/proposed-changes.md` | Gaps found while implementing the standard, proposed for the doc |

## Install the plugin (each developer)

In Claude Code:
```
/plugin marketplace add Accelerated-Innovation/way-of-work
/plugin install wow@accelerated-innovation
```
Needs `git`, Python 3.11+ and, for PR/release skills, the GitHub CLI (`gh auth login`).

## Adopt in a repository (repository lead)

1. Copy from `plugin/templates/`: `.github/workflows/wow.yml`, `.github/workflows/wow-release.yml`, `.github/pull_request_template.md`, `.wow.toml`, `.pre-commit-config.yaml`, and append `gitignore-secrets.txt` to `.gitignore`. Or run `/wow:audit` and let Claude do it on a branch.
2. Open the PR; once `wow / standards` and `wow / secrets` have run, make them required (see [docs/github-setup.md](docs/github-setup.md)).
3. Run `/wow:audit` (it includes a full-history secret scan) and fix what it reports.

## Run the validators locally

```bash
python plugin/validators/wow.py --help
python plugin/validators/wow.py ci --base origin/develop --base-branch develop --head-branch "$(git branch --show-current)" --body-file pr.md --title "feat(x): y"
python plugin/validators/wow.py secrets --history      # every commit, every branch
python plugin/validators/wow.py next-version           # SemVer from commits since last tag
```

## Test

```bash
python -m unittest discover -s tests -v
```
CI runs the tests on Python 3.11–3.13, scans this repo for secrets, and runs the reusable PR checks on this repo's own PRs.

## Release (deploy)

This repository is consumed by tag. Bump `VERSION`, `plugin/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `pyproject.toml` and the `rev:` in `plugin/templates/.pre-commit-config.yaml` together (a test enforces this), merge, then tag `vX.Y.Z`. The publish workflow moves the major tag (`v0`) that product repositories reference.

## Changing a rule

1. Change the validator and its test; update the skill text if behaviour changes.
2. Keep AI-provider patterns in `checks/secrets.py` and `config/gitleaks.toml` in sync.
3. A rule change that could fail existing PRs is a MINOR bump at least; announce it before tagging.
