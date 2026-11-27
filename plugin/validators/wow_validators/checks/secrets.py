"""§3 / §6.2 No secrets in source control. AI provider keys are a hard block.

This is the fast, dependency-free scanner used by the Claude hooks, the pre-commit
hook and `wow.py secrets`. In CI, gitleaks runs as well (config/gitleaks.toml), and
GitHub push protection is the first wall. Keep the AI-provider rules here in sync
with config/gitleaks.toml.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..util import Result, git, glob_match

# (rule id, description, regex). Provider rules are high-confidence and always block.
PROVIDER_RULES: list[tuple[str, str, re.Pattern]] = [
    ("anthropic-key", "Anthropic API key", re.compile(r"sk-ant-(?:api|admin)\d{2}-[A-Za-z0-9_\-]{20,}|sk-ant-[A-Za-z0-9_\-]{32,}")),
    ("openai-key", "OpenAI API key", re.compile(r"sk-(?:proj|svcacct|admin|None)-[A-Za-z0-9_\-]{20,}|sk-[A-Za-z0-9]{20}T3BlbkFJ[A-Za-z0-9]{20}|\bsk-[A-Za-z0-9]{40,}\b")),
    ("google-api-key", "Google / Gemini API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("huggingface-token", "Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{30,}\b")),
    ("groq-key", "Groq API key", re.compile(r"\bgsk_[A-Za-z0-9]{40,}\b")),
    ("xai-key", "xAI API key", re.compile(r"\bxai-[A-Za-z0-9]{40,}\b")),
    ("replicate-token", "Replicate token", re.compile(r"\br8_[A-Za-z0-9]{30,}\b")),
    ("azure-openai-key", "Azure OpenAI / AI Services key",
     re.compile(r"(?i)(?:azure|openai|cognitive|aoai|ai[_-]?services?)[\w.-]{0,30}?(?:key|secret)[\"']?\s*[:=]\s*[\"']?(?:[0-9a-f]{32}|[A-Za-z0-9]{84})\b")),
    ("aws-access-key", "AWS access key ID", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", "GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{60,}\b")),
    ("slack-token", "Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("stripe-key", "Stripe secret key", re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{20,}\b")),
    ("private-key", "Private key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY( BLOCK)?-----")),
]

PLACEHOLDER = re.compile(
    r"(?i)^(?:\$\{.*\}|\$\(.*\)|\{\{.*\}\}|<[^>]*>|%[A-Z_]+%|\*+|x{3,}.*|.*(?:your|example|sample|placeholder|changeme|"
    r"change_me|dummy|fake|test|local|redacted|replace|todo|secret_here|key_here|xxxx).*)$"
)
GENERIC_RULES: list[tuple[str, str, re.Pattern]] = [
    ("generic-secret", "Hard-coded credential",
     re.compile(r"(?i)\b[\w.-]*(?:api[_-]?key|secret|token|password|passwd|pwd|access[_-]?key|client[_-]?secret)\b[\"']?\s*[:=]\s*[\"']([^\"'\s]{12,})[\"']")),
    ("connection-string", "Connection string with password",
     re.compile(r"(?i)(?:Password|Pwd)\s*=\s*([^;\"'\s]{6,})\s*;")),
    ("url-credentials", "Credentials in URL",
     re.compile(r"\b[a-z][a-z0-9+.-]*://[^:/\s@]+:([^@/\s]{6,})@[^\s\"']+")),
]


@dataclass
class Finding:
    rule: str
    description: str
    line: int
    preview: str

    def __str__(self) -> str:
        return f"line {self.line}: {self.description} ({self.rule}) → {self.preview}"


def _mask(s: str) -> str:
    s = s.strip()
    return (s[:6] + "…" + s[-2:]) if len(s) > 10 else "…"


def scan_text(text: str) -> list[Finding]:
    findings: list[Finding] = []
    for n, line in enumerate(text.splitlines(), 1):
        for rule, desc, rx in PROVIDER_RULES:
            for m in rx.finditer(line):
                findings.append(Finding(rule, desc, n, _mask(m.group(0))))
        for rule, desc, rx in GENERIC_RULES:
            for m in rx.finditer(line):
                value = m.group(1)
                if PLACEHOLDER.match(value) or "${" in value or "{{" in value or "os.environ" in line \
                        or "process.env" in line or "Environment.GetEnvironmentVariable" in line:
                    continue
                findings.append(Finding(rule, desc, n, _mask(value)))
    return findings


def forbidden_file(path: str, cfg: dict) -> bool:
    s = cfg["secrets"]
    return glob_match(path, s["forbidden_files"]) and not glob_match(path, s["allowed_files"])


def check_files(paths: list[str], cfg: dict, root: str = ".") -> Result:
    r = Result("Secrets")
    for rel in paths:
        if forbidden_file(rel, cfg):
            r.error(f"{rel}: this kind of file must not be committed. Commit a template with placeholder values (e.g. .env.example).")
            continue
        p = Path(root) / rel
        if not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for f in scan_text(text):
            r.error(f"{rel} {f}")
    return r


def check_diff(diff: str, cfg: dict, label: str = "staged changes") -> Result:
    """Scan only added lines of a unified diff (what is about to enter history)."""
    r = Result(f"Secrets ({label})")
    current, new_line = "", 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else line[4:]
            if current != "/dev/null" and forbidden_file(current, cfg):
                r.error(f"{current}: this kind of file must not be committed. Use a template with placeholders.")
            continue
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            new_line = int(m.group(1)) if m else 0
            continue
        if line.startswith("+") and not line.startswith("+++"):
            for f in scan_text(line[1:]):
                f.line = new_line
                r.error(f"{current} {f}")
            new_line += 1
        elif not line.startswith("-"):
            new_line += 1
    return r


def check_staged(cfg: dict, cwd: str | None = None) -> Result:
    return check_diff(git("diff", "--cached", "-U0", "--no-color", cwd=cwd), cfg)


def check_range(base: str, head: str, cfg: dict, cwd: str | None = None) -> Result:
    return check_diff(git("diff", "-U0", "--no-color", f"{base}...{head}", cwd=cwd), cfg, f"{base}...{head}")


def check_history(cfg: dict, cwd: str | None = None) -> Result:
    """Scan every commit on every branch (used by /wow:audit on adoption)."""
    r = Result("Secrets (full history)")
    log = git("log", "--all", "-p", "-U0", "--no-color", "--format=commit %H", cwd=cwd)
    commit = ""
    for chunk in re.split(r"(?m)^(?=commit [0-9a-f]{40}$)", log):
        if not chunk.strip():
            continue
        commit = chunk[7:15]
        sub = check_diff(chunk, cfg)
        r.errors += [f"{commit} {e}" for e in sub.errors]
    if r.errors:
        r.note("A key that was ever pushed is compromised: rotate it first. Rewriting history does not un-leak it.")
    return r
