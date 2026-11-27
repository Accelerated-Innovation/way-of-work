"""`wow` command line. One entry point for CI, git hooks, Claude hooks and skills.

    python wow.py <command> [options]        (from a checkout or the plugin)
    wow <command> [options]                  (when installed via pre-commit / pip)

Exit code 0 = pass (warnings allowed), 1 = a rule failed, 2 = usage/internal error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import audit, config
from .checks import branch, commits, config_parity, manifests, migrations, pr_body, promotion, secrets, size, version
from .util import GitError, Result, changed_files, current_branch, git


def _emit(results: list[Result], summary_title: str | None = None) -> int:
    for r in results:
        print(r.render())
        r.annotate()
    failed = [r for r in results if not r.ok]
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and summary_title:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"## {summary_title}\n\n```\n" + "\n".join(r.render() for r in results) + "\n```\n")
            if failed:
                fh.write("\nSee the Way of Work for each rule, or run `/wow:pr` in Claude to fix the description.\n")
    return 1 if failed else 0


def _body(args) -> str:
    if getattr(args, "body_file", None):
        return Path(args.body_file).read_text(encoding="utf-8")
    if getattr(args, "body", None) is not None:
        return args.body
    return os.environ.get("WOW_PR_BODY", "")


def cmd_branch(a, cfg):
    name = a.name or current_branch()
    r = branch.check(name, cfg)
    if a.forbid_environment and name in cfg["branches"]["environment"]:
        r.error(f"You are on '{name}'. Never commit to environment branches (§2); create a work branch first.")
    return _emit([r])


def cmd_commit_msg(a, cfg):
    msg = Path(a.file).read_text(encoding="utf-8") if a.file else (a.message or "")
    return _emit([commits.check_message(msg, cfg)])


def cmd_commits(a, cfg):
    return _emit([commits.check_range(a.base, a.head, cfg)])


def cmd_pr_body(a, cfg):
    changed = [p for s, p in changed_files(a.base, a.head) if s != "D"] if a.base else []
    return _emit([pr_body.check(_body(a), cfg, changed)])


def cmd_size(a, cfg):
    return _emit([size.check(a.base, a.head, cfg)])


def cmd_promotion(a, cfg):
    return _emit([promotion.check(a.base_branch, a.head_branch, cfg)])


def cmd_migrations(a, cfg):
    return _emit([migrations.check(a.base, a.head, cfg)])


def cmd_config(a, cfg):
    return _emit([config_parity.check(os.getcwd(), cfg)])


def cmd_manifests(a, cfg):
    return _emit([manifests.check(os.getcwd(), cfg)])


def cmd_version(a, cfg):
    if a.print:
        name, v = version.read_version(os.getcwd(), cfg)
        if not v:
            print("no version found", file=sys.stderr)
            return 1
        print(v)
        return 0
    return _emit([version.check(os.getcwd(), cfg, a.base_branch, a.base_ref)])


def cmd_next_version(a, cfg):
    root = os.getcwd()
    _, current = version.read_version(root, cfg)
    since = a.since or version.last_tag(root)
    msgs = version.commits_since(root, since, a.head)
    nxt, reason = version.next_version(current, msgs, cfg) if current else (None, "no current version")
    print(json.dumps({"current": current, "next": nxt, "reason": reason, "since": since, "commits": len(msgs)}, indent=2))
    return 0 if nxt else 1


def cmd_changelog(a, cfg):
    root = os.getcwd()
    since = a.since or version.last_tag(root)
    v = a.version or version.read_version(root, cfg)[1] or "unreleased"
    print(version.changelog(version.commits_since(root, since, a.head), cfg, v))
    return 0


def cmd_secrets(a, cfg):
    if a.staged:
        res = secrets.check_staged(cfg)
    elif a.range:
        res = secrets.check_range(a.range[0], a.range[1], cfg)
    elif a.history:
        res = secrets.check_history(cfg)
    elif a.stdin:
        res = Result("Secrets (stdin)")
        res.errors += [str(f) for f in secrets.scan_text(sys.stdin.read())]
    else:
        files = a.files or [p for p in git("ls-files").splitlines() if p]
        res = secrets.check_files(files, cfg)
    if not res.ok:
        res.note("Move the value to the secret store / vault and read it from configuration at runtime (§6.2). "
                 "If it was ever pushed, rotate it now.")
    return _emit([res], "Secrets")


def cmd_audit(a, cfg):
    return _emit(audit.run(os.getcwd(), cfg, history=a.history), "Way of Work audit")


def cmd_ci(a, cfg):
    """Everything the PR workflow enforces, in one run."""
    base, head = a.base, a.head
    results = [promotion.check(a.base_branch, a.head_branch, cfg)]
    is_work_pr = a.head_branch not in cfg["branches"]["environment"]
    if is_work_pr:
        results.append(branch.check(a.head_branch, cfg))
    title = a.title if a.title is not None else os.environ.get("WOW_PR_TITLE", "")
    t = commits.check_message(title, cfg, label="(PR title)")
    t.name = "PR title"
    t.warnings = [w for w in t.warnings if "work item" not in w]  # the PR body carries the link
    results.append(t)
    if is_work_pr:
        results.append(commits.check_range(base, head, cfg))
    changed = [p for s, p in changed_files(base, head) if s != "D"]
    results.append(pr_body.check(_body(a), cfg, changed))
    results.append(size.check(base, head, cfg))
    results.append(migrations.check(base, head, cfg))
    results.append(secrets.check_range(base, head, cfg))
    results.append(config_parity.check(os.getcwd(), cfg))
    results.append(manifests.check(os.getcwd(), cfg))
    results.append(version.check(os.getcwd(), cfg, a.base_branch, base))
    return _emit(results, "Way of Work checks")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wow", description="Way of Work validators")
    p.add_argument("-C", dest="cwd", help="run as if started in this directory")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("branch", help="check a branch name (default: current)")
    s.add_argument("name", nargs="?")
    s.add_argument("--forbid-environment", action="store_true", help="fail on develop/staging/demo/prod (git hooks)")
    s.set_defaults(fn=cmd_branch)

    s = sub.add_parser("commit-msg", help="check one commit message")
    s.add_argument("file", nargs="?", help="message file (git commit-msg hook passes this)")
    s.add_argument("-m", "--message")
    s.set_defaults(fn=cmd_commit_msg)

    def rng(sp, need=True):
        sp.add_argument("--base", required=need, help="base ref, e.g. origin/develop")
        sp.add_argument("--head", default="HEAD")

    s = sub.add_parser("commits", help="check all commits in base..head"); rng(s); s.set_defaults(fn=cmd_commits)
    s = sub.add_parser("size", help="PR size against the 400 line guideline"); rng(s); s.set_defaults(fn=cmd_size)
    s = sub.add_parser("migrations", help="applied migrations are not edited"); rng(s); s.set_defaults(fn=cmd_migrations)

    s = sub.add_parser("pr-body", help="check a PR description")
    rng(s, need=False)
    s.add_argument("--body-file"); s.add_argument("--body")
    s.set_defaults(fn=cmd_pr_body)

    s = sub.add_parser("promotion", help="check PR source → target")
    s.add_argument("--base-branch", required=True); s.add_argument("--head-branch", required=True)
    s.set_defaults(fn=cmd_promotion)

    sub.add_parser("config", help="configuration parity across environments").set_defaults(fn=cmd_config)
    sub.add_parser("manifests", help="deployment manifest hygiene").set_defaults(fn=cmd_manifests)

    s = sub.add_parser("version", help="check the version source")
    s.add_argument("--print", action="store_true", help="print the current version and exit")
    s.add_argument("--base-branch"); s.add_argument("--base-ref")
    s.set_defaults(fn=cmd_version)

    s = sub.add_parser("next-version", help="compute the next SemVer from commits since the last tag")
    s.add_argument("--since"); s.add_argument("--head", default="HEAD")
    s.set_defaults(fn=cmd_next_version)

    s = sub.add_parser("changelog", help="changelog from commits since the last tag")
    s.add_argument("--since"); s.add_argument("--head", default="HEAD"); s.add_argument("--version")
    s.set_defaults(fn=cmd_changelog)

    s = sub.add_parser("secrets", help="scan for secrets (default: all tracked files)")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--staged", action="store_true")
    g.add_argument("--range", nargs=2, metavar=("BASE", "HEAD"))
    g.add_argument("--history", action="store_true")
    g.add_argument("--stdin", action="store_true")
    s.add_argument("files", nargs="*")
    s.set_defaults(fn=cmd_secrets)

    s = sub.add_parser("audit", help="local conformance audit")
    s.add_argument("--history", action="store_true", help="also scan full git history for secrets")
    s.set_defaults(fn=cmd_audit)

    s = sub.add_parser("ci", help="run every PR check (used by the reusable workflow)")
    rng(s)
    s.add_argument("--base-branch", required=True); s.add_argument("--head-branch", required=True)
    s.add_argument("--title"); s.add_argument("--body-file"); s.add_argument("--body")
    s.set_defaults(fn=cmd_ci)

    a = p.parse_args(argv)
    if a.cwd:
        os.chdir(a.cwd)
    cfg = config.load(os.getcwd())
    try:
        return a.fn(a, cfg)
    except GitError as e:
        print(f"wow: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
