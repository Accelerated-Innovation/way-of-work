---
name: start
description: Start work on a work item the Way of Work way — create a correctly named feature/fix/hotfix branch from the right base. Use when the user says "start ticket 1234", "new branch for…", "pick up WOW-12", "start a hotfix", or begins coding without a work branch.
---

# Start work (Way of Work §2)

Creates `feature|fix|hotfix/<work-item>-<slug>` from the right base branch.

`WOW` below means `python "<this skill's base directory>/../../validators/wow.py"`.

## Steps

1. **Get the work item.** You need its ID (e.g. `1234` or `WOW-1234`) and a short title.
   - If a work-tracking tool is connected (Jira, Azure Boards, GitHub Issues, Linear…), read the item to get its title and type. Otherwise ask the user for the ID and a few words describing it.
   - The repo's `.wow.toml` may define `work_item_pattern` and `work_item_url`; respect them.

2. **Pick the type and base.**
   | Work | Type | Base |
   |---|---|---|
   | New behaviour | `feature` | `develop` |
   | Bug fix | `fix` | `develop` |
   | Urgent production fix | `hotfix` | `prod` |
   Ask only if it is unclear. A hotfix should be rare; confirm the user means production is affected.

3. **Make the slug.** Branch names are all lowercase, including the work item key (`AI-204` → `ai-204`). Then 2–5 lowercase words from the title, joined by hyphens, no ticket words ("fix", "bug") repeated. Examples: `feature/1234-target-plans`, `feature/ai-204-vision-builder`.

4. **Validate before creating:** `WOW branch <name>`. Fix and re-run until it passes.

5. **Check the working tree.** If `git status --porcelain` shows changes, tell the user and ask whether to bring them along, stash them, or stop. Never discard work.

6. **Make sure the base exists.** `git ls-remote --exit-code --heads origin <base>`. If it doesn't, the repository hasn't adopted the branch model yet (e.g. only `main` exists). Don't branch from `main` instead: tell the user the repository lead must create the environment branches first (`/wow:audit` → "Bootstrap the branch model"), then come back.

7. **Create the branch from the up-to-date base:**
   ```bash
   git fetch origin <base>
   git switch -c <name> origin/<base>
   ```

8. If a tracker is connected and the user agrees, move the item to *In progress*.

9. Reply with the branch name, the base, and one line on what's next (commit with `/wow:commit`, open a PR with `/wow:pr`). For a hotfix, remind them: bump the PATCH version in this branch, and after it reaches `prod` it must be merged back into `develop` the same day (the release workflow opens that PR).

## Rules
- Never create branches from `staging` or `demo`, and never commit on `develop`, `staging`, `demo` or `prod`.
- Keep branches short-lived (under a week); suggest `git merge origin/develop` regularly.
