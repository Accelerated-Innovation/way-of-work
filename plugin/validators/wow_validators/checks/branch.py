"""§2 Branch naming: feature|fix|hotfix/<work-item>-<slug>."""
from __future__ import annotations

import re

from ..util import Result, glob_match


def pattern(cfg: dict) -> re.Pattern:
    types = "|".join(map(re.escape, cfg["branches"]["work_types"]))
    return re.compile(rf"^(?:{types})/{cfg['work_item_pattern']}-[a-z0-9]+(?:-[a-z0-9]+)*$")


def work_item_from_branch(name: str, cfg: dict) -> str | None:
    m = re.match(rf"^[^/]+/({cfg['work_item_pattern']})-", name)
    return m.group(1) if m else None


def check(name: str, cfg: dict) -> Result:
    r = Result("Branch name")
    if name in cfg["branches"]["environment"]:
        r.note(f"'{name}' is an environment branch; promotion rules apply instead.")
        return r
    if glob_match(name, cfg["branches"]["exempt"]):
        r.note(f"'{name}' is exempt from the naming rule.")
        return r
    if not pattern(cfg).match(name):
        types = "|".join(cfg["branches"]["work_types"])
        r.error(
            f"'{name}' does not match ({types})/<work-item>-<slug>, "
            "e.g. feature/1234-target-plans. Use lowercase words joined by hyphens for the slug."
        )
    return r
