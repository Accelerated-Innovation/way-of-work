"""Load per-repository settings from `.wow.toml`, falling back to Way of Work defaults.

Every key is optional. A repository only needs a `.wow.toml` to change a default
(for example, its version file or where its migrations live).
"""
from __future__ import annotations

import copy
import os
from pathlib import Path

try:  # Python 3.11+
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]

CONFIG_FILE = ".wow.toml"

DEFAULTS: dict = {
    # Work item IDs: numeric (1234) or tracker keys (WOW-1234). See Way of Work §14 Q3.
    "work_item_pattern": r"(?:\d+|[A-Z][A-Z0-9]+-\d+)",
    # Optional: link template used by skills, e.g. "https://example.atlassian.net/browse/{id}"
    "work_item_url": "",
    "branches": {
        "environment": ["develop", "staging", "demo", "prod"],
        "work_types": ["feature", "fix", "hotfix"],
        # Branches exempt from the naming rule (bots, release bumps).
        "exempt": ["dependabot/**", "renovate/**", "release/v*"],
    },
    # base branch -> allowed head branches (glob). Promotion only moves forward (§2);
    # `prod` may flow back into earlier branches for hotfix back-merges.
    "promotion": {
        "develop": ["feature/*", "fix/*", "hotfix/*", "release/v*", "dependabot/**", "renovate/**", "prod"],
        "staging": ["develop", "prod"],
        "demo": ["staging", "prod"],
        "prod": ["demo", "hotfix/*"],
    },
    "commits": {
        "types": ["feat", "fix", "refactor", "perf", "test", "docs", "ci", "build", "chore"],
        "max_header_length": 100,
        "banned_summaries": [
            "wip", "minor fix", "minor fixes", "fix", "fixes", "fixed", "update", "updates",
            "updated", "changes", "change", "misc", "stuff", "tmp", "temp", "test", "tests",
            "refactor", "cleanup", "small fix", "small fixes", "some fixes", "work", "done",
        ],
    },
    "pr": {
        "max_changed_lines": 400,
        "generated_globs": [
            "**/package-lock.json", "**/yarn.lock", "**/pnpm-lock.yaml", "**/poetry.lock",
            "**/uv.lock", "**/packages.lock.json", "**/*.min.js", "**/*.min.css", "**/*.snap",
            "**/*.Designer.cs", "**/*ModelSnapshot.cs", "**/dist/**", "**/build/**",
            "**/generated/**", "**/__generated__/**",
        ],
        "ui_globs": [
            "**/*.tsx", "**/*.jsx", "**/*.vue", "**/*.svelte", "**/*.css", "**/*.scss",
            "**/*.less", "**/*.html", "**/*.razor", "**/*.cshtml",
        ],
        "dependency_globs": [
            "**/package.json", "**/requirements*.txt", "**/pyproject.toml", "**/Pipfile",
            "**/*.csproj", "**/Directory.Packages.props", "**/go.mod", "**/Cargo.toml",
        ],
    },
    "migrations": {
        "paths": ["**/Migrations/**", "**/migrations/**", "**/alembic/versions/**", "**/db/migrate/**"],
        # Files inside migration folders that tools legitimately rewrite.
        "mutable": ["**/*ModelSnapshot.cs", "**/alembic/env.py", "**/script.py.mako", "**/__init__.py"],
    },
    "version": {
        # package.json | pyproject.toml | *.csproj | Directory.Build.props | VERSION
        "file": "",
    },
    "config": {
        # e.g. template = ".env.example", environments = ["deploy/develop.env", "deploy/staging.env"]
        "template": "",
        "environments": [],
    },
    "secrets": {
        # Files that must never be committed. Templates with placeholder values are fine.
        "forbidden_files": [
            "**/.env", "**/.env.*", "**/*.pem", "**/*.key", "**/*.pfx", "**/*.p12", "**/*.jks",
            "**/id_rsa", "**/id_rsa.*", "**/id_ed25519", "**/id_ed25519.*", "**/credentials.json",
            "**/service-account*.json", "**/*.publishsettings", "**/appsettings.*.local.json",
            "**/secrets.json",
        ],
        "allowed_files": [
            "**/.env.example", "**/.env.sample", "**/.env.template", "**/.env.dist",
            "**/*.example.*", "**/*.sample.*", "**/*.template.*", "**/*.pub",
        ],
    },
    "manifests": {
        "paths": [],  # e.g. ["deploy/**/*.yaml", "charts/**/templates/*.yaml"]
    },
}


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load(repo_root: str | os.PathLike | None = None) -> dict:
    root = Path(repo_root or os.getcwd())
    path = root / CONFIG_FILE
    if not path.is_file() or tomllib is None:
        return copy.deepcopy(DEFAULTS)
    with path.open("rb") as fh:
        return _merge(DEFAULTS, tomllib.load(fh))
