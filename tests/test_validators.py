"""Tests for the Way of Work validators. Run: python -m unittest discover -s tests"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin" / "validators"))

from wow_validators import config  # noqa: E402
from wow_validators.checks import (  # noqa: E402
    branch, commits, config_parity, manifests, migrations, pr_body, promotion, secrets, size, version,
)
from wow_validators.util import glob_match  # noqa: E402

CFG = config.load("/nonexistent")

# Fake keys are assembled at runtime so this file never contains a real-looking key
# (otherwise our own secret scanning would, correctly, block it).
FAKE_ANTHROPIC = "sk-" + "ant-" + "api03-" + "A1b2C3d4" * 12
FAKE_OPENAI = "sk-" + "proj-" + "Z9y8X7w6" * 8
FAKE_AWS = "AK" + "IA" + "ABCDEFGHIJKLMNOP"

GOOD_BODY = """## What changed and why
Expired sessions now log the user out.

## Work item
https://tracker.example.com/browse/WOW-1234

## Screenshots
N/A

## Impact (database / configuration / infrastructure)
None

## How it was tested
Unit tests plus manual check on develop.
"""


def sh(cwd, *cmd):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)


class Repo:
    """Throwaway git repo with a `develop` branch."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = self.tmp.name
        sh(self.path, "git", "init", "-q", "-b", "develop")
        sh(self.path, "git", "config", "user.email", "t@example.com")
        sh(self.path, "git", "config", "user.name", "T")
        sh(self.path, "git", "config", "commit.gpgsign", "false")

    def write(self, rel, text):
        p = Path(self.path) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def commit(self, msg):
        sh(self.path, "git", "add", "-A")
        sh(self.path, "git", "commit", "-q", "-m", msg)

    def checkout(self, *args):
        sh(self.path, "git", "checkout", "-q", *args)

    def close(self):
        self.tmp.cleanup()


class TestGlob(unittest.TestCase):
    def test_double_star(self):
        self.assertTrue(glob_match("package-lock.json", ["**/package-lock.json"]))
        self.assertTrue(glob_match("web/app/package-lock.json", ["**/package-lock.json"]))
        self.assertTrue(glob_match("src/Api/Migrations/2024_Init.cs", ["**/Migrations/**"]))
        self.assertFalse(glob_match("src/Api/Program.cs", ["**/Migrations/**"]))
        self.assertTrue(glob_match("hotfix/12-x", ["hotfix/*"]))
        self.assertFalse(glob_match("hotfix/12/x", ["hotfix/*"]))


class TestBranch(unittest.TestCase):
    def test_valid(self):
        for name in ["feature/1234-target-plans", "fix/WOW-12-login-loop", "hotfix/88-null-tenant",
                     "feature/ai-204-vision-builder"]:
            self.assertTrue(branch.check(name, CFG).ok, name)

    def test_invalid(self):
        for name in ["my-changes", "feature/target-plans", "feature/1234", "feature/1234_Target",
                     "feat/1234-x", "feature/1234-Target-Plans"]:
            self.assertFalse(branch.check(name, CFG).ok, name)

    def test_exempt_and_environment(self):
        self.assertTrue(branch.check("dependabot/npm_and_yarn/axios-1.7.0", CFG).ok)
        self.assertTrue(branch.check("develop", CFG).ok)

    def test_work_item(self):
        self.assertEqual(branch.work_item_from_branch("feature/WOW-12-x", CFG), "WOW-12")
        self.assertEqual(branch.work_item_from_branch("feature/ai-204-vision-builder", CFG), "AI-204")
        self.assertEqual(branch.work_item_from_branch("fix/1234-login", CFG), "1234")


class TestCommits(unittest.TestCase):
    def test_good(self):
        r = commits.check_message("fix(auth): expired sessions are logged out\n\nRefs: 1234", CFG)
        self.assertTrue(r.ok)
        self.assertFalse(r.warnings)

    def test_warns_without_ref(self):
        r = commits.check_message("feat(plans): target plans can be archived", CFG)
        self.assertTrue(r.ok)
        self.assertTrue(any("work item" in w for w in r.warnings))

    def test_bad_format(self):
        for msg in ["updated session code", "Fix: thing", "feature: x", "fix(auth):missing space"]:
            self.assertFalse(commits.check_message(msg, CFG).ok, msg)

    def test_vague(self):
        for msg in ["fix: minor fixes", "chore: wip", "feat: updates", "fix(api): fix", "chore: WIP on login"]:
            self.assertFalse(commits.check_message(msg, CFG).ok, msg)

    def test_breaking_and_merge(self):
        self.assertTrue(commits.check_message("feat(api)!: tenants endpoint requires auth\n\nBREAKING CHANGE: x\nRefs: 1", CFG).ok)
        self.assertTrue(commits.check_message("Merge pull request #12 from org/feature/1-x", CFG).ok)


class TestPrBody(unittest.TestCase):
    def test_good(self):
        self.assertTrue(pr_body.check(GOOD_BODY, CFG, ["src/api/session.py"]).ok)

    def test_missing_sections(self):
        r = pr_body.check("Fixed it", CFG)
        self.assertEqual(len(r.errors), 5)

    def test_template_comments_do_not_count(self):
        body = GOOD_BODY.replace("Unit tests plus manual check on develop.", "<!-- describe testing -->")
        self.assertFalse(pr_body.check(body, CFG).ok)

    def test_work_item_needs_link_or_id(self):
        body = GOOD_BODY.replace("https://tracker.example.com/browse/WOW-1234", "the login ticket")
        self.assertFalse(pr_body.check(body, CFG).ok)

    def test_ui_needs_screenshot(self):
        self.assertFalse(pr_body.check(GOOD_BODY, CFG, ["web/src/Login.tsx"]).ok)
        body = GOOD_BODY.replace("## Screenshots\nN/A", "## Screenshots\n![login](https://example.com/a.png)")
        self.assertTrue(pr_body.check(body, CFG, ["web/src/Login.tsx"]).ok)

    def test_dependencies_need_justification(self):
        self.assertFalse(pr_body.check(GOOD_BODY, CFG, ["package.json"]).ok)
        body = GOOD_BODY + "\n## Dependency justification\nAdds zod for request validation; widely used.\n"
        self.assertTrue(pr_body.check(body, CFG, ["package.json"]).ok)


class TestPromotion(unittest.TestCase):
    def test_allowed(self):
        for head, base in [("feature/1-x", "develop"), ("develop", "staging"), ("staging", "demo"),
                           ("demo", "prod"), ("hotfix/9-y", "prod"), ("prod", "develop")]:
            self.assertTrue(promotion.check(base, head, CFG).ok, f"{head}->{base}")

    def test_blocked(self):
        for head, base in [("feature/1-x", "staging"), ("develop", "prod"), ("staging", "develop"),
                           ("feature/1-x", "prod"), ("develop", "demo")]:
            self.assertFalse(promotion.check(base, head, CFG).ok, f"{head}->{base}")


class TestSecrets(unittest.TestCase):
    def test_provider_keys(self):
        for key in (FAKE_ANTHROPIC, FAKE_OPENAI, FAKE_AWS):
            self.assertTrue(secrets.scan_text(f'client = Client(api_key="{key}")'), key[:8])

    def test_azure_openai(self):
        self.assertTrue(secrets.scan_text("AZURE_OPENAI_API_KEY=" + "0123456789abcdef" * 2))

    def test_placeholders_pass(self):
        for line in ['OPENAI_API_KEY=""', 'api_key = os.environ["OPENAI_API_KEY"]',
                     'password: "${DB_PASSWORD}"', 'ANTHROPIC_API_KEY="your-key-here"',
                     'const apiKey = process.env.OPENAI_API_KEY;', 'token = "<paste-token>"']:
            self.assertFalse(secrets.scan_text(line), line)

    def test_generic(self):
        pw = "Pr0d" + "S3cret" + "Value9"
        self.assertTrue(secrets.scan_text(f'db_password = "{pw}"'))
        self.assertTrue(secrets.scan_text(f"Server=sql;Database=app;User Id=sa;Password={pw};"))
        self.assertTrue(secrets.scan_text(f"postgres://app:{pw}@db:5432/app"))

    def test_forbidden_files(self):
        for f in [".env", "web/.env.production", "certs/server.pem", "src/appsettings.Development.local.json"]:
            self.assertTrue(secrets.forbidden_file(f, CFG), f)
        for f in [".env.example", "web/.env.sample", "keys/deploy.pub", "src/env.py"]:
            self.assertFalse(secrets.forbidden_file(f, CFG), f)

    def test_diff_only_added_lines(self):
        diff = f"+++ b/app.py\n@@ -1,0 +1,2 @@\n+x = 1\n+KEY = '{FAKE_OPENAI}'\n-old = '{FAKE_ANTHROPIC}'\n"
        r = secrets.check_diff(diff, CFG)
        self.assertEqual(len(r.errors), 1)
        self.assertIn("line 2", r.errors[0])


class TestGitChecks(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        r = self.repo
        r.write("package.json", json.dumps({"name": "x", "version": "1.2.0"}))
        r.write("src/Migrations/001_init.sql", "create table t(id int);")
        r.write("README.md", "# x")
        r.commit("chore: initial commit for tests\n\nRefs: 1")

    def tearDown(self):
        self.repo.close()

    def test_migrations(self):
        r = self.repo
        r.checkout("-b", "feature/1-x")
        r.write("src/Migrations/002_add.sql", "alter table t add c int;")
        r.commit("feat(db): t has column c\n\nRefs: 1")
        self.assertTrue(migrations.check("develop", "HEAD", CFG, r.path).ok)
        r.write("src/Migrations/001_init.sql", "create table t(id bigint);")
        r.commit("fix(db): t id is bigint\n\nRefs: 1")
        res = migrations.check("develop", "HEAD", CFG, r.path)
        self.assertFalse(res.ok)
        self.assertIn("001_init.sql", res.errors[0])

    def test_commit_range(self):
        r = self.repo
        r.checkout("-b", "feature/1-x")
        r.write("a.txt", "a")
        r.commit("wip")
        self.assertFalse(commits.check_range("develop", "HEAD", CFG, r.path).ok)

    def test_size(self):
        r = self.repo
        r.checkout("-b", "feature/1-x")
        r.write("big.py", "x = 1\n" * 450)
        r.write("package-lock.json", "{}\n" * 5000)
        r.commit("feat: big change\n\nRefs: 1")
        res = size.check("develop", "HEAD", CFG, r.path)
        self.assertTrue(res.ok)  # size is a warning, never a block
        self.assertTrue(res.warnings)
        self.assertEqual(size.count("develop", "HEAD", CFG, r.path), (450, 5000))

    def test_version_bump_on_staging(self):
        r = self.repo
        sh(r.path, "git", "branch", "staging")
        cwd = os.getcwd()
        os.chdir(r.path)
        try:
            self.assertFalse(version.check(r.path, CFG, "staging", "staging").ok)
            r.write("package.json", json.dumps({"name": "x", "version": "1.3.0"}))
            r.commit("chore(release): v1.3.0\n\nRefs: 1")
            self.assertTrue(version.check(r.path, CFG, "staging", "staging").ok)
        finally:
            os.chdir(cwd)

    def test_staged_secret(self):
        r = self.repo
        r.write("settings.py", f'OPENAI_API_KEY = "{FAKE_OPENAI}"\n')
        sh(r.path, "git", "add", "-A")
        self.assertFalse(secrets.check_staged(CFG, r.path).ok)


class TestVersionMath(unittest.TestCase):
    def test_next(self):
        self.assertEqual(version.next_version("1.2.3", ["fix: a\n"], CFG)[0], "1.2.4")
        self.assertEqual(version.next_version("1.2.3", ["fix: a", "feat(x): b"], CFG)[0], "1.3.0")
        self.assertEqual(version.next_version("1.2.3", ["feat!: c"], CFG)[0], "2.0.0")
        self.assertEqual(version.next_version("1.2.3", ["fix: a\n\nBREAKING CHANGE: y"], CFG)[0], "2.0.0")
        self.assertEqual(version.next_version("1.2.3", ["docs: a"], CFG)[0], "1.2.3")

    def test_readers(self):
        self.assertEqual(version.read_text_version("a.csproj", "<Project><PropertyGroup><Version>2.1.0</Version>"), "2.1.0")
        self.assertEqual(version.read_text_version("pyproject.toml", '[project]\nversion = "0.4.1"\n'), "0.4.1")
        self.assertEqual(version.read_text_version("VERSION", "v3.0.0\n"), "3.0.0")

    def test_changelog(self):
        out = version.changelog(["feat(plans): plans can be archived", "fix: login loop is gone", "feat!: x"], CFG, "2.0.0")
        self.assertIn("### ⚠ Breaking changes", out)
        self.assertIn("- **plans:** plans can be archived", out)


class TestFiles(unittest.TestCase):
    def test_config_parity(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, ".env.example").write_text("DB_HOST=localhost\nFEATURE_X=false\n")
            Path(d, "dev.env").write_text("DB_HOST=db\nFEATURE_X=true\n")
            Path(d, "prod.env").write_text("DB_HOST=db\n")
            cfg = config._merge(CFG, {"config": {"template": ".env.example", "environments": ["dev.env", "prod.env"]}})
            r = config_parity.check(d, cfg)
            self.assertEqual(len(r.errors), 1)
            self.assertIn("FEATURE_X", r.errors[0])

    def test_manifests(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "deploy").mkdir()
            Path(d, "deploy/api.yaml").write_text(
                "kind: Deployment\nspec:\n  containers:\n    - name: api\n      image: acr.io/api:latest\n"
            )
            cfg = config._merge(CFG, {"manifests": {"paths": ["deploy/**"]}})
            r = manifests.check(d, cfg)
            self.assertEqual(len(r.errors), 3)  # latest + 2 probes
            self.assertTrue(r.warnings)


if __name__ == "__main__":
    unittest.main()


class TestAdrDetection(unittest.TestCase):
    def test_finds_nested_and_configured(self):
        from wow_validators import audit
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertIsNone(audit.find_adr_dir(root, CFG))
            adr = root / "docs/backend/architecture/ADR"
            adr.mkdir(parents=True)
            self.assertIsNone(audit.find_adr_dir(root, CFG))  # empty folder doesn't count
            (adr / "0001-use-fastapi.md").write_text("# 1")
            self.assertEqual(audit.find_adr_dir(root, CFG), "docs/backend/architecture/ADR")
            (root / "node_modules/x/adr").mkdir(parents=True)
            (root / "node_modules/x/adr/a.md").write_text("x")
            self.assertEqual(audit.find_adr_dir(root, CFG), "docs/backend/architecture/ADR")
            cfg = config._merge(CFG, {"docs": {"adr_path": "decisions"}})
            self.assertIsNone(audit.find_adr_dir(root, cfg))


class TestRepoConsistency(unittest.TestCase):
    """Version numbers that must move together when this repo is released."""

    def test_versions_match(self):
        v = (ROOT / "VERSION").read_text().strip()
        plugin = json.loads((ROOT / "plugin/.claude-plugin/plugin.json").read_text())
        market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        import tomllib
        py = tomllib.loads((ROOT / "pyproject.toml").read_text())
        precommit = (ROOT / "plugin/templates/.pre-commit-config.yaml").read_text()
        self.assertEqual(plugin["version"], v)
        self.assertEqual(market["plugins"][0]["version"], v)
        self.assertEqual(py["project"]["version"], v)
        self.assertIn(f"rev: v{v}", precommit)

    def test_skills_have_frontmatter(self):
        for skill in (ROOT / "plugin/skills").glob("*/SKILL.md"):
            text = skill.read_text()
            self.assertTrue(text.startswith("---\nname: " + skill.parent.name + "\n"), skill)
            self.assertIn("\ndescription: ", text.split("---")[1], skill)

    def test_gitleaks_rules_in_sync(self):
        import tomllib
        rules = tomllib.loads((ROOT / "config/gitleaks.toml").read_text())["rules"]
        by_id = {r["id"]: r["regex"] for r in rules}
        py = {rid: rx.pattern for rid, _, rx in secrets.PROVIDER_RULES}
        self.assertEqual(by_id["wow-anthropic-api-key"], py["anthropic-key"])
        self.assertTrue(by_id["wow-openai-api-key"] in py["openai-key"])
