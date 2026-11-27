"""§2 Promotion only moves forward: develop → staging → demo → prod.
Hotfixes go into prod and are merged back from prod."""
from __future__ import annotations

from ..util import Result, glob_match


def check(base: str, head: str, cfg: dict) -> Result:
    r = Result("Target branch")
    allowed = cfg["promotion"].get(base)
    if allowed is None:
        if base in cfg["branches"]["environment"]:
            r.error(f"No promotion rule is configured for '{base}'.")
        else:
            r.note(f"'{base}' is not an environment branch; no promotion rule applies.")
        return r
    if not glob_match(head, allowed):
        r.error(
            f"'{head}' → '{base}' is not allowed. '{base}' accepts only: {', '.join(allowed)}. "
            "Work branches target develop; environments are promoted in order develop → staging → demo → prod."
        )
    if base == "prod" and head.startswith("hotfix/"):
        r.note("Hotfix into prod: merge prod back into develop (and any environment ahead of prod) the same day.")
    return r
