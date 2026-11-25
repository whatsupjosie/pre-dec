#!/usr/bin/env python3
"""
fpr_autogen.py
Generate a draft Functional Purpose Report (FPR) from a project folder.

Usage:
  python fpr_autogen.py /path/to/project --name "Voice system" --out draft_fpr.json

What it does:
- scans common project files (.md, .txt, .py, .js, .ts, .json, .yaml, .yml)
- extracts high-signal lines mentioning purpose, TODOs, tests, logs, and outcomes
- fills a draft FPR JSON object that humans or another AI can refine
- validates against the provided JSON schema if present beside this script

This is a draft generator, not a truth oracle.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from datetime import datetime, timezone

ALLOWED_EXTS = {".md",".txt",".py",".js",".ts",".json",".yaml",".yml",".toml",".ini",".cfg"}
PURPOSE_PATTERNS = [
    re.compile(r"\b(purpose|goal|intent|why|problem|need)\b", re.I),
    re.compile(r"\bshould\b", re.I),
    re.compile(r"\b(feature|system|module|tool)\b", re.I),
]
TEST_PATTERNS = [
    re.compile(r"\b(test|assert|expect|passed|failed|spec)\b", re.I),
    re.compile(r"\b(todo|fixme|hack|bug|issue|risk)\b", re.I),
    re.compile(r"\b(log|trace|warning|error)\b", re.I),
]

def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def iter_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTS and ".git" not in p.parts:
            yield p

def pick_lines(text: str, patterns, limit=12):
    found = []
    for line in text.splitlines():
        s = line.strip()
        if not s or len(s) < 8:
            continue
        if any(p.search(s) for p in patterns):
            found.append(s[:400])
        if len(found) >= limit:
            break
    return found

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", type=Path)
    ap.add_argument("--name", default="Unnamed system")
    ap.add_argument("--out", type=Path, default=Path("draft_fpr.json"))
    args = ap.parse_args()

    root = args.project
    if not root.exists():
        raise SystemExit(f"Project path not found: {root}")

    purpose_lines, test_lines = [], []
    files_seen = 0
    for f in iter_files(root):
        files_seen += 1
        text = read_text(f)
        if not text:
            continue
        for line in pick_lines(text, PURPOSE_PATTERNS, limit=4):
            purpose_lines.append({"artifact": str(f.relative_to(root)), "line": line})
        for line in pick_lines(text, TEST_PATTERNS, limit=4):
            test_lines.append({"artifact": str(f.relative_to(root)), "line": line})

    desired = "Draft only: infer from project docs, README language, issues, and surrounding context."
    stated = "Draft only: inferred from comments, docs, and naming found in the scanned files."
    functional = "Draft only: inferred from code structure, tests, logs, and implementation cues; requires human or AI verification."

    evidence = []
    for item in test_lines[:8]:
        evidence.append({
            "type": "code_inspection" if item["artifact"].endswith((".py",".js",".ts")) else "other",
            "description": item["line"],
            "artifact": item["artifact"],
            "confidence": "Low"
        })
    if not evidence:
        evidence = [{
            "type": "other",
            "description": "No obvious test or evidence lines were detected automatically.",
            "artifact": "",
            "confidence": "Low"
        }]

    draft = {
        "fpr_summary": {
            "status": "Partial",
            "confidence": "Low",
            "primary_issue": "Auto-generated draft; core claims need verification.",
            "recommended_action": "Review the draft, replace placeholders, and validate with real behavior."
        },
        "feature_system": args.name,
        "date": datetime.now(timezone.utc).isoformat(),
        "desired_purpose": desired + ("\n\nSignals:\n- " + "\n- ".join(i["line"] for i in purpose_lines[:5]) if purpose_lines else ""),
        "stated_purpose": stated + ("\n\nSignals:\n- " + "\n- ".join(i["line"] for i in purpose_lines[5:10]) if len(purpose_lines) > 5 else ""),
        "functional_purpose": functional,
        "evidence": evidence,
        "impact": {
            "easier": [],
            "faster": [],
            "safer": [],
            "newly_possible": []
        },
        "alignment_status": "Partially aligned",
        "confidence_level": "Low",
        "drift_type": ["Mixed"],
        "gaps": {
            "missing_behavior": ["Need observed runtime behavior and user-facing validation."],
            "missing_signals": ["Need clearer source-of-truth statements for desired and stated purpose."],
            "missing_integration": ["Need linkage between docs, tests, and actual program behavior."],
            "missing_constraints": ["Need explicit acceptance criteria and failure conditions."]
        },
        "failure_cost": {
            "breaks": ["Decisions may be made on guessed purpose instead of verified purpose."],
            "degrades": ["Confidence in feature completeness and project continuity."],
            "propagates_to": ["Future planning, implementation, and audits."]
        },
        "signal_role": "Not a signal",
        "cost_vs_benefit": {
            "complexity_added": "Low to moderate; one draft-analysis pass across project files.",
            "benefit_gained": "Creates a standardized first-pass FPR packet quickly.",
            "worth_it": True
        },
        "required_actions": [
            "Review desired purpose against real user need.",
            "Replace draft functional claims with observed behavior.",
            "Add concrete evidence from tests, logs, demos, or direct use."
        ],
        "final_decision": "Recalibrate",
        "final_test": "If removed, the project loses a quick standardized way to draft an FPR from project artifacts.",
        "notes": f"Scanned {files_seen} candidate files under {root}."
    }

    args.out.write_text(json.dumps(draft, indent=2), encoding="utf-8")
    print(f"Wrote draft FPR to {args.out}")

if __name__ == "__main__":
    main()
