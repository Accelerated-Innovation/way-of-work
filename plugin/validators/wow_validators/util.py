"""Shared helpers: result reporting, glob matching and git access."""
from __future__ import annotations

import functools
import os
import re
import subprocess
from dataclasses import dataclass, field

IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"


@dataclass
class Result:
    """Outcome of one check. Errors block; warnings inform."""

    name: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    skipped: str = ""

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    def render(self) -> str:
        if self.skipped:
            return f"⏭  {self.name}: skipped ({self.skipped})"
        icon = "❌" if self.errors else ("⚠️ " if self.warnings else "✅")
        lines = [f"{icon} {self.name}"]
        lines += [f"   ✖ {m}" for m in self.errors]
        lines += [f"   ⚠ {m}" for m in self.warnings]
        lines += [f"   · {m}" for m in self.notes]
        return "\n".join(lines)

    def annotate(self) -> None:
        """Emit GitHub Actions annotations so problems show on the PR."""
        if not IN_CI:
            return
        for m in self.errors:
            print(f"::error title=Way of Work: {self.name}::{_escape(m)}")
        for m in self.warnings:
            print(f"::warning title=Way of Work: {self.name}::{_escape(m)}")


def _escape(msg: str) -> str:
    return msg.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


@functools.lru_cache(maxsize=512)
def _glob_regex(pattern: str) -> re.Pattern:
    """Translate a glob with `**` support into a regex (POSIX-style paths)."""
    i, out = 0, []
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def glob_match(path: str, patterns: list[str]) -> bool:
    path = path.replace("\\", "/")
    return any(_glob_regex(p).match(path) for p in patterns)


class GitError(RuntimeError):
    pass


def git(*args: str, cwd: str | None = None, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def current_branch(cwd: str | None = None) -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd).strip()


def changed_files(base: str, head: str = "HEAD", cwd: str | None = None) -> list[tuple[str, str]]:
    """Return (status, path) pairs for base...head. Renames report the old path as R."""
    out = git("diff", "--name-status", "-M", f"{base}...{head}", cwd=cwd)
    pairs: list[tuple[str, str]] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if not parts or not parts[0]:
            continue
        status = parts[0][0]
        if status == "R":
            pairs.append(("R", parts[1]))
            pairs.append(("A", parts[2]))
        else:
            pairs.append((status, parts[-1]))
    return pairs
