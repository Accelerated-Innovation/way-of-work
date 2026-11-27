---
name: commit
description: Write and make a Way of Work commit — Conventional Commits format, summary phrased as the behaviour now true, work item footer, breaking changes marked, secrets checked. Use whenever the user asks to commit, "commit this", "save my changes", or to write/fix a commit message.
---

# Commit (Way of Work §3)

`WOW` below means `python "<this skill's base directory>/../../validators/wow.py"`.

## Steps

1. **See what's being committed.**
   ```bash
   git status --short
   git diff --cached --stat
   git diff --cached
   ```
   If nothing is staged, show the changed files and ask what to include. Never stage `.env`, key files, or anything git-ignored. If the staged changes do two unrelated things, suggest splitting into two commits.

2. **Check for secrets first:** `WOW secrets --staged`. If it fails, stop. Tell the user which file and line, unstage it (`git restore --staged <file>`), and move the value to configuration read at runtime with a placeholder in `.env.example`. If the key was ever pushed or shared, say it must be rotated.

3. **Write the message.**
   ```
   type(scope): summary

   Optional body: why, not how. Wrap at ~72 characters.

   Refs: <work item>
   BREAKING CHANGE: <only if a contract or user-facing behaviour breaks>
   ```
   - **type:** `feat` new behaviour · `fix` bug fix · `refactor` no behaviour change · `perf` · `test` · `docs` · `ci` · `build` · `chore`
   - **scope:** the module or area (`auth`, `plans`, `api`, `web`), lowercase.
   - **summary:** the behaviour that is now true, lowercase start, no full stop. "expired sessions are logged out", not "updated session code". Never "wip", "minor fixes", "updates".
   - **Refs:** take the work item from the branch name (`feature/1234-…` → `Refs: 1234`).
   - **Breaking:** if a published contract (API fields, types, meaning) or user-facing behaviour breaks, use `type!:` **and** a `BREAKING CHANGE:` footer saying what consumers must do.

4. **Validate:** `WOW commit-msg -m "<full message>"`. Fix until it passes (warnings are fine to mention).

5. **Commit** with the message in a file so formatting survives:
   ```bash
   git commit -F <tmpfile>
   ```
   Do not use `--no-verify`. If a hook fails, fix the cause.

6. Reply with the commit header and short hash. Nothing else unless something needs attention.
