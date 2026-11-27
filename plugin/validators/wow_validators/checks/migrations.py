"""§7 Migrations already applied to a shared environment MUST NOT be edited.

Anything that already exists on the base branch is treated as applied: `develop`
deploys automatically on merge, so a migration on `develop` has run on a shared
environment. New migrations may be added; existing ones may not be modified,
renamed or deleted.
"""
from __future__ import annotations

from ..util import Result, changed_files, glob_match


def check(base: str, head: str, cfg: dict, cwd: str | None = None) -> Result:
    r = Result("Migrations")
    mcfg = cfg["migrations"]
    added = 0
    for status, path in changed_files(base, head, cwd):
        if not glob_match(path, mcfg["paths"]) or glob_match(path, mcfg["mutable"]):
            continue
        if status == "A":
            added += 1
        elif status in ("M", "D", "R"):
            verb = {"M": "modified", "D": "deleted", "R": "renamed"}[status]
            r.error(
                f"{path} was {verb}. It already exists on '{base}', so it has been applied to a shared "
                "environment. Add a new migration instead."
            )
    if added:
        r.note(f"{added} new migration file(s). Call them out under 'Impact' in the PR and in the release notes.")
    return r
