"""§5/§6.2 Deployment manifests: no floating `latest` images, readiness and liveness
probes on every workload, resource requests and limits declared.

Text-based and dependency-free on purpose; it targets plain Kubernetes YAML and Helm
templates. For deeper policy checks use kube-linter or conftest alongside it.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..util import Result, glob_match

WORKLOAD = re.compile(r"(?m)^kind:\s*(Deployment|StatefulSet|DaemonSet)\s*$")
IMAGE = re.compile(r"(?m)^\s*-?\s*image:\s*[\"']?([^\"'\s#]+)")


def _files(root: Path, patterns: list[str]) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and p.suffix in (".yaml", ".yml")
            and glob_match(str(p.relative_to(root)).replace("\\", "/"), patterns)]


def check(root: str, cfg: dict) -> Result:
    r = Result("Deployment manifests")
    patterns = cfg["manifests"]["paths"]
    if not patterns:
        r.skipped = "no [manifests] paths in .wow.toml"
        return r
    base = Path(root)
    files = _files(base, patterns)
    if not files:
        r.skipped = "no manifest files matched"
        return r
    for f in files:
        rel = str(f.relative_to(base)).replace("\\", "/")
        for i, doc in enumerate(re.split(r"(?m)^---\s*$", f.read_text(encoding="utf-8"))):
            for image in IMAGE.findall(doc):
                if "{{" in image:
                    continue  # templated; the tag is set at deploy time
                tag = image.rsplit("/", 1)[-1]
                if "@sha256:" in image:
                    continue
                if ":" not in tag or tag.endswith(":latest"):
                    r.error(f"{rel}: image '{image}' uses a floating tag. Deploy an explicit version (§5).")
            kind = WORKLOAD.search(doc)
            if not kind:
                continue
            where = f"{rel} ({kind.group(1)} #{i + 1})"
            for probe in ("readinessProbe", "livenessProbe"):
                if probe not in doc:
                    r.error(f"{where}: missing {probe} (§6.2 MUST).")
            if not re.search(r"(?m)^\s*requests:", doc) or not re.search(r"(?m)^\s*limits:", doc):
                r.warn(f"{where}: declare resource requests and limits (§6.2 SHOULD).")
    r.note(f"{len(files)} manifest file(s) checked.")
    return r
