#!/usr/bin/env python3
"""Merge Semgrep JSON + Gitleaks JSON into unified findings.json."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SEVERITY_MAP_SEMGREP = {
    "error": "HIGH",
    "warning": "MEDIUM",
    "info": "LOW",
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
}


def _sha1(*parts: str) -> str:
    h = hashlib.sha1()
    for p in parts:
        h.update((p or "").encode("utf-8", errors="replace"))
        h.update(b"\0")
    return h.hexdigest()[:16]


def _priority(severity: str, source: str) -> int:
    """1 = highest, 5 = lowest."""
    base = {
        "CRITICAL": 1,
        "HIGH": 2,
        "MEDIUM": 3,
        "LOW": 4,
        "INFO": 5,
    }.get(severity.upper(), 3)
    # Secrets often need faster human eyes
    if source == "gitleaks" and base > 1:
        base = max(1, base - 1)
    return base


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None
    return json.loads(text)


def normalize_semgrep(data: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if data is None:
        return findings
    results = data.get("results", data) if isinstance(data, dict) else data
    if not isinstance(results, list):
        return findings
    for r in results:
        if not isinstance(r, dict):
            continue
        check_id = str(r.get("check_id") or r.get("rule_id") or "unknown")
        path = str(r.get("path") or (r.get("extra") or {}).get("path") or "")
        start = r.get("start") or {}
        line = int(start.get("line") or r.get("line") or 0)
        extra = r.get("extra") or {}
        msg = str(
            extra.get("message")
            or r.get("message")
            or check_id
        )
        sev_raw = (
            (extra.get("severity") or r.get("severity") or "WARNING")
        )
        severity = SEVERITY_MAP_SEMGREP.get(str(sev_raw).lower(), "MEDIUM")
        meta = extra.get("metadata") or {}
        if isinstance(meta, dict):
            impact = str(meta.get("impact") or meta.get("severity") or "").lower()
            if impact in SEVERITY_MAP_SEMGREP:
                severity = SEVERITY_MAP_SEMGREP[impact]
        fp_src = str(extra.get("fingerprint") or "")
        fingerprint = fp_src or _sha1("semgrep", check_id, path, str(line), msg[:80])
        fid = _sha1("semgrep", check_id, fingerprint)
        findings.append(
            {
                "id": f"semgrep:{fid}",
                "source": "semgrep",
                "rule_id": check_id,
                "severity": severity,
                "file": path,
                "line": line,
                "message": msg,
                "fingerprint": fingerprint,
                "status": "open",
                "triage_priority": _priority(severity, "semgrep"),
            }
        )
    return findings


def normalize_gitleaks(data: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if data is None:
        return findings
    # gitleaks JSON is typically a list; sometimes {"Findings": [...]}
    if isinstance(data, dict):
        results = data.get("Findings") or data.get("findings") or data.get("results") or []
    else:
        results = data
    if not isinstance(results, list):
        return findings
    for r in results:
        if not isinstance(r, dict):
            continue
        rule_id = str(r.get("RuleID") or r.get("rule_id") or r.get("Description") or "gitleaks")
        path = str(r.get("File") or r.get("file") or "")
        line = int(r.get("StartLine") or r.get("line") or r.get("Line") or 0)
        msg = str(r.get("Description") or r.get("message") or rule_id)
        # Secrets default HIGH unless tagged
        tags = r.get("Tags") or []
        severity = "HIGH"
        if isinstance(tags, list) and any(str(t).lower() == "low" for t in tags):
            severity = "MEDIUM"
        fingerprint = str(
            r.get("Fingerprint")
            or r.get("fingerprint")
            or _sha1("gitleaks", rule_id, path, str(line), str(r.get("Commit") or ""))
        )
        fid = _sha1("gitleaks", rule_id, fingerprint)
        findings.append(
            {
                "id": f"gitleaks:{fid}",
                "source": "gitleaks",
                "rule_id": rule_id,
                "severity": severity,
                "file": path,
                "line": line,
                "message": msg,
                "fingerprint": fingerprint,
                "status": "open",
                "triage_priority": _priority(severity, "gitleaks"),
            }
        )
    return findings


def merge_findings(semgrep: list[dict], gitleaks: list[dict]) -> dict[str, Any]:
    combined = semgrep + gitleaks
    # Dedupe by fingerprint+source
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for f in combined:
        key = f"{f['source']}:{f['fingerprint']}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)
    unique.sort(key=lambda x: (x.get("triage_priority", 99), x.get("file", ""), x.get("line", 0)))
    return {
        "schema_version": "1.0",
        "finding_count": len(unique),
        "findings": unique,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize Semgrep + Gitleaks into findings.json")
    parser.add_argument("--semgrep", type=Path, required=True, help="Path to Semgrep JSON")
    parser.add_argument("--gitleaks", type=Path, required=True, help="Path to Gitleaks JSON")
    parser.add_argument("--out", type=Path, required=True, help="Output findings.json path")
    args = parser.parse_args(argv)

    try:
        sem_data = load_json(args.semgrep)
    except json.JSONDecodeError as e:
        print(f"warning: invalid semgrep JSON ({e}); treating as empty", file=sys.stderr)
        sem_data = None
    try:
        git_data = load_json(args.gitleaks)
    except json.JSONDecodeError as e:
        print(f"warning: invalid gitleaks JSON ({e}); treating as empty", file=sys.stderr)
        git_data = None

    # Missing files → empty
    if not args.semgrep.exists():
        print(f"warning: semgrep file missing: {args.semgrep}", file=sys.stderr)
        sem_data = None
    if not args.gitleaks.exists():
        print(f"warning: gitleaks file missing: {args.gitleaks}", file=sys.stderr)
        git_data = None

    out = merge_findings(normalize_semgrep(sem_data), normalize_gitleaks(git_data))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out} ({out['finding_count']} findings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
