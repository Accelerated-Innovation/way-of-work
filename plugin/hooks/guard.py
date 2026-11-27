"""Way of Work guard for Claude Code (PreToolUse hook).

Blocks, before they happen:
  * writing an API key or other credential into a file that git would track
  * creating .env / key files that are not git-ignored
  * `git commit` with secrets staged, with --no-verify, with a non-conforming message,
    or directly on develop / staging / demo / prod
  * `git push` to develop / staging / demo / prod
  * `git add -f` of a forbidden file

Exit code 2 blocks the tool call and shows stderr to Claude. Any internal error fails
open (exit 0) because CI and GitHub push protection still enforce the same rules.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "validators"))

from wow_validators import config as wow_config  # noqa: E402
from wow_validators.checks import commits, secrets  # noqa: E402

SECRET_HELP = (
    "Way of Work §3/§6.2: secrets never go in source control. Read the value from the secret store / "
    "vault or an environment variable at runtime, and put a placeholder in .env.example. "
    "If this key was real and has been shared anywhere, rotate it."
)


def block(msg: str) -> None:
    print(f"⛔ Way of Work: {msg}", file=sys.stderr)
    sys.exit(2)


def git(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def repo_root(cwd: str) -> str | None:
    p = git(["rev-parse", "--show-toplevel"], cwd)
    return p.stdout.strip() if p.returncode == 0 else None


def is_ignored(path: str, cwd: str) -> bool:
    return git(["check-ignore", "-q", path], cwd).returncode == 0


# --- file writes -------------------------------------------------------------------

def written_text(tool: str, ti: dict) -> str:
    if tool == "Write":
        return ti.get("content", "")
    if tool == "Edit":
        return ti.get("new_string", "")
    if tool == "MultiEdit":
        return "\n".join(e.get("new_string", "") for e in ti.get("edits", []))
    if tool == "NotebookEdit":
        return ti.get("new_source", "")
    return ""


def guard_write(tool: str, ti: dict, cwd: str) -> None:
    path = ti.get("file_path") or ti.get("notebook_path") or ""
    if not path:
        return
    abspath = path if os.path.isabs(path) else os.path.join(cwd, path)
    root = repo_root(os.path.dirname(abspath) if os.path.isdir(os.path.dirname(abspath)) else cwd)
    if not root:
        return  # not in a git repo; nothing will be committed
    cfg = wow_config.load(root)
    rel = os.path.relpath(abspath, root).replace("\\", "/")
    ignored = is_ignored(rel, root)

    if secrets.forbidden_file(rel, cfg) and not ignored:
        block(
            f"{rel} is a local secrets/key file but it is not git-ignored, so it could be committed. "
            "Add it to .gitignore first (e.g. `.env` and `.env.*` with `!.env.example`), "
            "or write a template with placeholder values instead."
        )
    if ignored:
        return  # git-ignored local files (e.g. .env) may hold local values
    findings = secrets.scan_text(written_text(tool, ti))
    if findings:
        block(f"refusing to write a credential into {rel} ({findings[0]}). {SECRET_HELP}")


# --- shell commands ----------------------------------------------------------------

SPLIT = re.compile(r"\s*(?:&&|\|\||;|\||\n)\s*")


def git_invocations(command: str) -> list[tuple[list[str], str | None]]:
    """Yield (git args, -C dir) for every `git ...` segment of a shell command."""
    out = []
    for seg in SPLIT.split(command):
        try:
            words = shlex.split(seg, posix=True)
        except ValueError:
            words = seg.split()
        # skip env assignments / sudo / command prefixes
        while words and (re.match(r"^\w+=", words[0]) or words[0] in ("sudo", "command", "exec", "env")):
            words.pop(0)
        if not words or os.path.basename(words[0]) not in ("git", "git.exe"):
            continue
        args, cdir = words[1:], None
        while args and args[0].startswith("-"):
            if args[0] == "-C" and len(args) > 1:
                cdir = args[1]
                args = args[2:]
            elif args[0] in ("-c",) and len(args) > 1:
                args = args[2:]
            else:
                args = args[1:]
        if args:
            out.append((args, cdir))
    return out


def current_branch(cwd: str) -> str:
    return git(["rev-parse", "--abbrev-ref", "HEAD"], cwd).stdout.strip()


def guard_push(args: list[str], cwd: str, cfg: dict) -> None:
    protected = cfg["branches"]["environment"]
    positional = [a for a in args[1:] if not a.startswith("-")]
    refspecs = positional[1:]  # first positional is the remote
    targets = []
    for spec in refspecs:
        spec = spec.lstrip("+")
        dst = spec.split(":", 1)[1] if ":" in spec else spec
        targets.append(dst.removeprefix("refs/heads/"))
    if not refspecs:
        targets.append(current_branch(cwd))
    hit = [t for t in targets if t in protected]
    if hit:
        block(
            f"pushing directly to '{hit[0]}' is not allowed (§2). Push your work branch and open a pull request; "
            "environment branches are promoted through PRs (/wow:pr, /wow:release)."
        )


def guard_commit(args: list[str], cwd: str, cfg: dict) -> None:
    if "--no-verify" in args or "-n" in args:
        block("`git commit --no-verify` skips the secret scan. Fix what the hook reports instead.")
    branch = current_branch(cwd)
    if branch in cfg["branches"]["environment"]:
        block(f"you are on '{branch}'. Never commit to environment branches (§2). Create a work branch first (/wow:start).")

    all_flag = any(a in ("-a", "--all") or (re.fullmatch(r"-[a-zA-Z]*a[a-zA-Z]*", a) and not a.startswith("--")) for a in args)
    diff = git(["diff", "HEAD" if all_flag else "--cached", "-U0", "--no-color"], cwd).stdout
    res = secrets.check_diff(diff, cfg)
    if not res.ok:
        block(f"secret in the commit: {res.errors[0]}. Unstage it (`git restore --staged <file>`), remove it. {SECRET_HELP}")

    # Validate -m / --message when present (multiple -m are joined like git does).
    msgs, i = [], 0
    while i < len(args):
        a = args[i]
        if a in ("-m", "--message") and i + 1 < len(args):
            msgs.append(args[i + 1]); i += 2; continue
        if a.startswith("--message="):
            msgs.append(a.split("=", 1)[1])
        elif re.fullmatch(r"-[a-zA-Z]*m", a) and i + 1 < len(args):  # e.g. -am "msg"
            msgs.append(args[i + 1]); i += 2; continue
        elif a.startswith("-m") and len(a) > 2:
            msgs.append(a[2:])
        i += 1
    # Messages built by shell substitution (e.g. -m "$(cat <<'EOF' ...)") can't be read
    # reliably here; the commit-msg hook and CI check those.
    if msgs and not any("$(" in m or "`" in m or "<<" in m for m in msgs):
        r = commits.check_message("\n\n".join(msgs), cfg)
        if not r.ok:
            block(f"commit message does not follow §3: {r.errors[0]} (/wow:commit writes one for you).")


def guard_add(args: list[str], cwd: str, cfg: dict) -> None:
    if not any(a in ("-f", "--force") for a in args):
        return
    for a in args[1:]:
        if not a.startswith("-") and secrets.forbidden_file(a.replace("\\", "/"), cfg):
            block(f"`git add -f {a}` would commit a secrets/key file. Commit a template with placeholders instead.")


def guard_bash(ti: dict, cwd: str) -> None:
    command = ti.get("command", "")
    if "git" not in command:
        return
    for args, cdir in git_invocations(command):
        where = os.path.join(cwd, cdir) if cdir and not os.path.isabs(cdir) else (cdir or cwd)
        root = repo_root(where)
        if not root:
            continue
        cfg = wow_config.load(root)
        verb = args[0]
        if verb == "push":
            guard_push(args, where, cfg)
        elif verb == "commit":
            guard_commit(args, where, cfg)
        elif verb == "add":
            guard_add(args, where, cfg)


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return
    tool = event.get("tool_name", "")
    ti = event.get("tool_input", {}) or {}
    cwd = event.get("cwd") or os.getcwd()
    try:
        if tool == "Bash":
            guard_bash(ti, cwd)
        elif tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            guard_write(tool, ti, cwd)
    except SystemExit:
        raise
    except Exception as e:  # fail open; CI is the wall
        print(f"Way of Work guard skipped: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
