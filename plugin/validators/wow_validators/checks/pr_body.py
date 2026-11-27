"""§4 Pull request description: required sections, filled in, with conditional sections
for UI changes (§4 screenshots) and new dependencies (§9 justification)."""
from __future__ import annotations

import re

from ..util import Result, glob_match

# key -> (heading keywords, human label)
SECTIONS = {
    "what": (("what changed", "what and why", "summary"), "What changed and why"),
    "work_item": (("work item", "ticket", "issue"), "Work item"),
    "screenshots": (("screenshot",), "Screenshots"),
    "impact": (("impact",), "Impact (database / configuration / infrastructure)"),
    "testing": (("how it was tested", "testing", "tested"), "How it was tested"),
    "dependencies": (("dependenc",), "Dependency justification"),
}
ALWAYS = ("what", "work_item", "screenshots", "impact", "testing")
EMPTY_VALUES = {"", "-", "n/a", "na", "none", "tbd", "todo", "...", "nil"}
HEADING = re.compile(r"^#{2,4}\s+(.+?)\s*#*\s*$")


def parse_sections(body: str) -> dict[str, str]:
    body = re.sub(r"<!--.*?-->", "", body or "", flags=re.S)
    sections: dict[str, list[str]] = {}
    current = None
    for line in body.splitlines():
        h = HEADING.match(line)
        if h:
            title = h.group(1).lower()
            current = next(
                (k for k, (keys, _) in SECTIONS.items() if any(kw in title for kw in keys)), None
            )
            if current:
                sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def _is_empty(text: str) -> bool:
    cleaned = re.sub(r"[\s*_`>]", " ", text).strip().lower()
    return cleaned in EMPTY_VALUES


def check(body: str, cfg: dict, changed: list[str] | None = None) -> Result:
    r = Result("PR description")
    changed = changed or []
    sections = parse_sections(body)

    for key in ALWAYS:
        if key not in sections:
            r.error(f"Missing section '## {SECTIONS[key][1]}'. Use the repository PR template.")

    for key in ("what", "testing"):
        if key in sections and _is_empty(sections[key]):
            r.error(f"Section '{SECTIONS[key][1]}' is empty.")

    if "impact" in sections and not sections["impact"].strip():
        r.error("Section 'Impact' is empty. Write 'None' if there is no database, configuration or infrastructure impact.")

    if "work_item" in sections:
        wi = sections["work_item"]
        if not (re.search(r"https?://\S+", wi) or re.search(rf"(?<![\w-]){cfg['work_item_pattern']}(?![\w-])", wi)):
            r.error("Section 'Work item' must contain a link or ID for the work item.")

    ui_files = [f for f in changed if glob_match(f, cfg["pr"]["ui_globs"])]
    if ui_files and "screenshots" in sections:
        shot = sections["screenshots"]
        if _is_empty(shot) or not re.search(r"!\[|<img|https?://|\.png|\.jpe?g|\.gif|\.webm|\.mp4", shot, re.I):
            r.error(f"UI files changed ({len(ui_files)}, e.g. {ui_files[0]}) but no screenshot is attached.")

    dep_files = [f for f in changed if glob_match(f, cfg["pr"]["dependency_globs"])]
    if dep_files:
        just = sections.get("dependencies", "")
        if _is_empty(just):
            r.error(
                f"Dependency manifests changed ({', '.join(dep_files[:3])}). Add a '## Dependency justification' "
                "section explaining any new or upgraded dependency (§9). Write 'No new dependencies' if only versions of existing ones changed."
            )
    return r
