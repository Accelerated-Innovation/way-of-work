"""Local conformance audit of a repository against the Way of Work (§2–§12).

Checks what can be seen from the working tree. GitHub-side settings (rulesets,
environments, secret scanning, push protection) are checked by the /wow:audit
skill through the GitHub API, because they are not in the repository.
"""
from __future__ import annotations

import re
from pathlib import Path

from .checks import manifests, secrets, version
from .util import Result, git

ADR_DIR_NAMES = {"adr", "adrs", "decisions", "decision-records", "architecture-decisions"}
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "bin", "obj", "__pycache__", ".wow"}


def _exists_any(root: Path, names: list[str]) -> str | None:
    for n in names:
        if (root / n).exists():
            return n
    return None


def find_adr_dir(root: Path, cfg: dict, max_depth: int = 5) -> str | None:
    """Configured [docs] adr_path, else the first folder named adr/ADR/decisions/… that holds .md files."""
    configured = cfg.get("docs", {}).get("adr_path", "")
    if configured:
        return configured if (root / configured).is_dir() else None
    stack = [(root, 0)]
    while stack:
        d, depth = stack.pop()
        try:
            children = sorted((c for c in d.iterdir() if c.is_dir()), reverse=True)
        except OSError:
            continue
        for c in children:
            if c.name in SKIP_DIRS:
                continue
            if c.name.lower() in ADR_DIR_NAMES and any(c.glob("*.md")):
                return str(c.relative_to(root)).replace("\\", "/")
            if depth + 1 < max_depth:
                stack.append((c, depth + 1))
    return None


def run(root_str: str, cfg: dict, history: bool = False) -> list[Result]:
    root = Path(root_str)
    results: list[Result] = []

    r = Result("Way of Work wiring")
    if not (root / ".wow.toml").is_file():
        r.warn(".wow.toml is missing; defaults apply. Copy templates/.wow.toml to customise.")
    wf_dir = root / ".github" / "workflows"
    wf_text = "\n".join(p.read_text(encoding="utf-8") for p in wf_dir.glob("*.y*ml")) if wf_dir.is_dir() else ""
    if "/.github/workflows/pr-checks.yml" not in wf_text:
        r.error("No workflow calls the Way of Work PR checks. Add templates/.github/workflows/wow.yml.")
    if "way-of-work/.github/workflows/release.yml" not in wf_text:
        r.warn("No workflow calls the Way of Work release workflow (tags vX.Y.Z on prod). Add templates/.github/workflows/wow-release.yml.")
    if not _exists_any(root, [".github/pull_request_template.md", ".github/PULL_REQUEST_TEMPLATE.md", "docs/pull_request_template.md"]):
        r.error("No PR template. Add templates/.github/pull_request_template.md (§4 required sections).")
    if not _exists_any(root, [".pre-commit-config.yaml"]):
        r.warn("No .pre-commit-config.yaml. Developers without Claude get no local secret scan before commit.")
    if not _exists_any(root, ["CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"]):
        r.warn("No CODEOWNERS. Use it for high-risk paths only: auth, contracts, migrations, pipelines (§13.1).")
    results.append(r)

    r = Result("Secrets hygiene")
    gi = (root / ".gitignore").read_text(encoding="utf-8") if (root / ".gitignore").is_file() else ""
    if not re.search(r"(?m)^\s*\*?\*?/?\.env(\*|\.\*)?\s*$", gi):
        r.error(".gitignore does not ignore .env files. Add `.env` and `.env.*` with `!.env.example`.")
    tracked = [p for p in git("ls-files", cwd=root_str).splitlines() if p]
    for p in tracked:
        if secrets.forbidden_file(p, cfg):
            r.error(f"{p} is tracked and must not be. Remove it, rotate anything it contained, and commit a template instead.")
    scan = secrets.check_files(tracked, cfg, root_str)
    r.errors += scan.errors
    results.append(r)
    if history:
        results.append(secrets.check_history(cfg, cwd=root_str))

    results.append(version.check(root_str, cfg))
    results.append(manifests.check(root_str, cfg))

    r = Result("Documentation (§12)")
    readme = _exists_any(root, ["README.md", "README.rst", "README"])
    if not readme:
        r.error("No README.")
    else:
        text = (root / readme).read_text(encoding="utf-8").lower()
        for topic, words in {
            "what it is": ("overview", "about", "what"),
            "how to run it locally": ("run", "local", "getting started", "setup"),
            "how to test it": ("test",),
            "how it's deployed": ("deploy", "release"),
        }.items():
            if not any(w in text for w in words):
                r.warn(f"README does not seem to cover {topic}.")
    adr = find_adr_dir(root, cfg)
    if adr:
        r.note(f"ADRs: {adr}")
    elif cfg.get("docs", {}).get("adr_path"):
        r.warn(f"[docs] adr_path '{cfg['docs']['adr_path']}' does not exist.")
    else:
        r.warn("No ADR folder found (e.g. docs/adr). Record architecture decisions in the repository, "
               "or set [docs] adr_path in .wow.toml if they live somewhere else.")
    results.append(r)
    return results
