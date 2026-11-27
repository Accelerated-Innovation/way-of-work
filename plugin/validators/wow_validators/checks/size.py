"""§4 Keep pull requests reviewable: warn above ~400 changed lines (excluding generated files)."""
from __future__ import annotations

from ..util import Result, git, glob_match


def count(base: str, head: str, cfg: dict, cwd: str | None = None) -> tuple[int, int]:
    """Return (counted_lines, excluded_lines)."""
    counted = excluded = 0
    for line in git("diff", "--numstat", "--no-renames", f"{base}...{head}", cwd=cwd).splitlines():
        added, deleted, path = (line.split("\t") + ["", "", ""])[:3]
        n = (int(added) if added.isdigit() else 0) + (int(deleted) if deleted.isdigit() else 0)
        if glob_match(path, cfg["pr"]["generated_globs"]):
            excluded += n
        else:
            counted += n
    return counted, excluded


def check(base: str, head: str, cfg: dict, cwd: str | None = None) -> Result:
    r = Result("PR size")
    counted, excluded = count(base, head, cfg, cwd)
    limit = cfg["pr"]["max_changed_lines"]
    r.note(f"{counted} changed lines ({excluded} more in generated files, not counted).")
    if counted > limit:
        r.warn(
            f"{counted} changed lines is over the ~{limit} line guideline. Split the work or put it "
            "behind a feature flag, or explain in the PR why it has to land together."
        )
    return r
