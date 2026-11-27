"""§11 A new setting MUST be added, in the same PR, to the configuration template and to
every environment. Compares setting names (never values) across the configured files.

Supports .env-style files (KEY=value) and JSON (nested keys flattened as A:B, the .NET
convention). Configure in .wow.toml:

    [config]
    template = ".env.example"
    environments = ["deploy/develop.env", "deploy/staging.env", "deploy/demo.env", "deploy/prod.env"]
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..util import Result

ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_.]*)\s*=")


def _flatten(obj, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}:{k}" if prefix else k
            sub = _flatten(v, path)
            keys |= sub or {path}
    return keys


def keys_of(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return _flatten(json.loads(text))
    return {m.group(1) for line in text.splitlines() if (m := ENV_LINE.match(line))}


def check(root: str, cfg: dict) -> Result:
    r = Result("Configuration parity")
    c = cfg["config"]
    if not c["template"] or not c["environments"]:
        r.skipped = "no [config] template/environments in .wow.toml"
        return r
    base = Path(root)
    template = base / c["template"]
    if not template.is_file():
        r.error(f"Configuration template {c['template']} is missing (§11).")
        return r
    tkeys = keys_of(template)
    for env in c["environments"]:
        p = base / env
        if not p.is_file():
            r.error(f"Environment configuration {env} is missing.")
            continue
        ekeys = keys_of(p)
        if missing := sorted(tkeys - ekeys):
            r.error(f"{env} is missing: {', '.join(missing)}")
        if extra := sorted(ekeys - tkeys):
            r.error(f"{env} has settings not in {c['template']}: {', '.join(extra)}. Add them to the template with a safe default.")
    return r
