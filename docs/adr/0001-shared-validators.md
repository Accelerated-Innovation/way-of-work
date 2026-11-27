# 1. One set of validators for Claude, git hooks and CI

Date: 2026-11-28 · Status: accepted

## Context
The Way of Work has rules that a script can decide (branch names, commit format, PR
description, migrations, secrets) and rules that need judgment (security, contracts,
tests). People may or may not use Claude. If Claude and CI checked rules with different
code, they would drift, and "Claude said it was fine" would stop meaning anything.

## Decision
- Every deterministic rule is implemented once, in `plugin/validators` (Python, stdlib only).
- The same code is run by the Claude hooks and skills (from the installed plugin), by
  pre-commit (`.pre-commit-hooks.yaml`), and by the reusable workflows in CI.
- CI is the enforcement point. Every MUST that a script can check is a required status
  check. Skills and hooks make passing it easy; they are not the wall.
- Secrets have more layers: GitHub push protection (org-enforced), gitleaks in CI, the
  local scanner in hooks/pre-commit.
- Judgment rules live in skills (`/wow:review`, `/wow:release`, `/wow:done`), never in CI.

## Consequences
- Product repositories reference workflows by tag (`@v0`); a rule change ships by tagging.
- The validators can't use third-party packages, so they run anywhere Python 3.11 exists.
- Some checks are heuristics (manifests, README coverage); they warn rather than fail
  where false positives are likely.
