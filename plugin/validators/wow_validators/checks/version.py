"""§5 Versioning: one SemVer source per component, bumped when promoting to staging,
tagged vX.Y.Z on prod. Also computes the next version and changelog from commits."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..util import GitError, Result, git
from .commits import MERGE_OR_REVERT, header_regex

try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")
AUTODETECT = ["package.json", "pyproject.toml", "Directory.Build.props", "VERSION"]


def detect_file(root: str, cfg: dict) -> str | None:
    if cfg["version"]["file"]:
        return cfg["version"]["file"]
    for name in AUTODETECT:
        if (Path(root) / name).is_file():
            return name
    csprojs = sorted(Path(root).glob("*.csproj")) + sorted(Path(root).glob("src/*/*.csproj"))
    return str(csprojs[0].relative_to(root)).replace("\\", "/") if len(csprojs) == 1 else None


def read_text_version(name: str, text: str) -> str | None:
    lower = name.lower()
    if lower.endswith("package.json"):
        return json.loads(text).get("version")
    if lower.endswith("pyproject.toml") and tomllib:
        data = tomllib.loads(text)
        return data.get("project", {}).get("version") or data.get("tool", {}).get("poetry", {}).get("version")
    if lower.endswith((".csproj", ".props")):
        m = re.search(r"<(?:Version|VersionPrefix)>\s*([^<\s]+)\s*</", text)
        return m.group(1) if m else None
    first = text.strip().splitlines()[0] if text.strip() else ""
    return first.lstrip("v") or None


def read_version(root: str, cfg: dict, ref: str | None = None) -> tuple[str | None, str | None]:
    """Return (file, version). With `ref`, read the file as it is on that git ref."""
    name = detect_file(root, cfg)
    if not name:
        return None, None
    try:
        text = git("show", f"{ref}:{name}", cwd=root) if ref else (Path(root) / name).read_text(encoding="utf-8")
    except (GitError, FileNotFoundError):
        return name, None
    return name, read_text_version(name, text)


def parse(v: str) -> tuple[int, int, int]:
    m = SEMVER.match(v or "")
    if not m:
        raise ValueError(v)
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def check(root: str, cfg: dict, base: str | None = None, base_ref: str | None = None) -> Result:
    r = Result("Version")
    name, version = read_version(root, cfg)
    if not name:
        r.error(
            "No version source found. Set [version] file in .wow.toml (package.json, pyproject.toml, "
            "*.csproj, Directory.Build.props or VERSION). Every deployable component MUST be versioned (§5)."
        )
        return r
    if not version:
        r.error(f"{name} has no version.")
        return r
    try:
        head_v = parse(version)
    except ValueError:
        r.error(f"{name} version '{version}' is not SemVer MAJOR.MINOR.PATCH.")
        return r
    r.note(f"{name}: {version}")

    if base in ("staging", "prod") and base_ref:
        _, base_version = read_version(root, cfg, ref=base_ref)
        if base_version:
            try:
                if head_v <= parse(base_version):
                    r.error(
                        f"A PR into {base} must bump the version (§5): {base} has {base_version}, this PR has {version}. "
                        "Promotions to staging bump MAJOR/MINOR/PATCH from the commits; hotfixes into prod bump PATCH. "
                        "Run /wow:release or `wow.py next-version` to compute it."
                    )
            except ValueError:
                r.warn(f"staging version '{base_version}' is not SemVer; cannot compare.")
    return r


# --- next version and changelog -------------------------------------------------

def last_tag(root: str) -> str | None:
    try:
        return git("describe", "--tags", "--abbrev=0", "--match", "v[0-9]*", cwd=root).strip() or None
    except GitError:
        return None


def commits_since(root: str, since: str | None, head: str = "HEAD") -> list[str]:
    rng = f"{since}..{head}" if since else head
    raw = git("log", "--no-merges", "--format=%B%x1e", rng, cwd=root)
    return [c.strip() for c in raw.split("\x1e") if c.strip()]


def next_version(current: str, messages: list[str], cfg: dict) -> tuple[str, str]:
    """Return (next_version, reason) from Conventional Commit messages."""
    major, minor, patch = parse(current)
    rx = header_regex(cfg)
    level = 0  # 0 none, 1 patch, 2 minor, 3 major
    for msg in messages:
        header = msg.splitlines()[0]
        m = rx.match(header)
        if not m:
            continue
        if m.group("bang") or re.search(r"(?m)^BREAKING[ -]CHANGE:", msg):
            level = 3
        elif m.group("type") == "feat":
            level = max(level, 2)
        elif m.group("type") in ("fix", "perf"):
            level = max(level, 1)
    if level == 3:
        return f"{major + 1}.0.0", "breaking change"
    if level == 2:
        return f"{major}.{minor + 1}.0", "new feature"
    if level == 1:
        return f"{major}.{minor}.{patch + 1}", "fix"
    return current, "no releasable changes (only chore/docs/ci/test/refactor/build)"


def changelog(messages: list[str], cfg: dict, version: str) -> str:
    rx = header_regex(cfg)
    groups: dict[str, list[str]] = {"⚠ Breaking changes": [], "Features": [], "Fixes": [], "Performance": [], "Other": []}
    for msg in messages:
        header = msg.splitlines()[0]
        if MERGE_OR_REVERT.match(header):
            continue
        m = rx.match(header)
        if not m:
            groups["Other"].append(header)
            continue
        scope = f"**{m.group('scope')}:** " if m.group("scope") else ""
        line = f"{scope}{m.group('summary')}"
        if m.group("bang") or re.search(r"(?m)^BREAKING[ -]CHANGE:", msg):
            groups["⚠ Breaking changes"].append(line)
        elif m.group("type") == "feat":
            groups["Features"].append(line)
        elif m.group("type") == "fix":
            groups["Fixes"].append(line)
        elif m.group("type") == "perf":
            groups["Performance"].append(line)
        else:
            groups["Other"].append(f"{m.group('type')}: {line}")
    out = [f"## v{version}", ""]
    for title, lines in groups.items():
        if lines:
            out += [f"### {title}", *[f"- {l}" for l in lines], ""]
    return "\n".join(out).rstrip() + "\n"
