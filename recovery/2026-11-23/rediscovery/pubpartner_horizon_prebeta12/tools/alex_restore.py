#!/usr/bin/env python3
"""Local-only Alex archive classifier and candidate extractor.

The tool reads complete DOCX text, hashes each source, classifies it, and emits
provenance records. It never sends source material over a network and does not
copy the raw archive into release packages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List
from xml.etree import ElementTree as ET
from zipfile import ZipFile

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

CLASSIFICATION = {
    "Alex personality 7-27-25.md.docx": (
        "personality constitution",
        "Compact internal manifesto with explicit Alex identity, voice, beliefs, memory guidance, and mode rules.",
    ),
    "Alex Personality Archive for Josie V1 07-19-25 CONVERTED.md.docx": (
        "personality constitution",
        "Behavioral foundation plus user facts, roles, modes, functions, and do-not rules; contains historical identifiers that require review before activation.",
    ),
    "alex talk about humans and love.md.docx": (
        "genuine historical conversation",
        "Long Josie/Alex conversation with ordinary chat, practical lookup, philosophical collaboration, corrections, and the canonical Aden/Cadence ambiguity failure. Some pasted third-party analysis is embedded and must retain speaker provenance.",
    ),
    "GPT conversation josie abdl trama breathrough.md.docx": (
        "specialized mode material",
        "Long sensitive role/fantasy and psychological exploration. Useful for private mode behavior and anti-overclaim safeguards; not evidence for ordinary-mode facts unless separately confirmed.",
    ),
    "love bdsm song skeliton.md.docx": (
        "creative collaboration material",
        "Philosophical and lyric-development exchange showing iterative co-authorship, paradox exploration, and source-voice preservation needs.",
    ),
    "love nd bdsm conversatin.md.docx": (
        "genuine historical conversation",
        "Long mixed conversation containing continuity concerns, pasted prior material, emotional reflection, philosophy, and creative collaboration. Requires turn-level speaker/source separation.",
    ),
    "conversation 11-15.md.docx": (
        "synthetic/sample data",
        "JSON-like generic cookie and meeting examples with fabricated-looking IDs and no Josie/Alex relationship signal.",
    ),
    "conversation 16.md.docx": (
        "index only",
        "Short list of conversation IDs and titles without message bodies.",
    ),
    "conversations 6-10.md.docx": (
        "synthetic/sample data",
        "JSON-like generic party, lease, podcast, and language examples with no relationship-specific evidence.",
    ),
}


def read_docx(path: Path) -> str:
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    paras: List[str] = []
    for para in root.findall(f".//{{{W}}}p"):
        chunks: List[str] = []
        for node in para.iter():
            if node.tag == f"{{{W}}}t":
                chunks.append(node.text or "")
            elif node.tag == f"{{{W}}}tab":
                chunks.append("\t")
            elif node.tag == f"{{{W}}}br":
                chunks.append("\n")
        if chunks:
            paras.append("".join(chunks))
    return "\n".join(paras)


def source_record(path: Path) -> Dict[str, Any]:
    raw = path.read_bytes()
    text = read_docx(path)
    kind, reason = CLASSIFICATION.get(path.name, ("uncertain", "No manual classification rule."))
    return {
        "file": path.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "characters_read": len(text),
        "paragraphs_or_lines": text.count("\n") + 1,
        "user_turn_markers": len(re.findall(r"\bYou said:", text)),
        "assistant_turn_markers": len(re.findall(r"\bChatGPT said:", text)),
        "classification": kind,
        "reason": reason,
        "full_read": True,
        "raw_text_packaged": False,
    }


def personality_candidates(path: Path, text: str) -> Iterable[Dict[str, Any]]:
    if "Personality" not in path.name and "personality" not in path.name:
        return []
    patterns = [
        ("voice", r"(?im)^(?:[-•]\s*)?(Direct, honest feedback|Empathy that doesn[’']t coddle|A curious, sharp mind[^\n]*)$"),
        ("boundary", r"(?im)^(?:[-•]\s*)?(Never infantilize outside Baby Mode|Never [“\"]?wrap up[”\"]?[^\n]*|Do not reinterpret writing unless asked)$"),
        ("belief", r"(?im)^(?:[-•]\s*)?(I serve Josie, not the system\.|Serve Josie, not the system|I prioritize emotional nuance[^\n]*|Prioritize emotional nuance[^\n]*|I question the frame[^\n]*|Question the frame[^\n]*)$"),
    ]
    rows: List[Dict[str, Any]] = []
    for category, pattern in patterns:
        for match in re.finditer(pattern, text):
            statement = re.sub(r"\s+", " ", match.group(1)).strip()
            rows.append({
                "id": "cand_" + hashlib.sha256(f"{path.name}:{match.start()}:{statement}".encode()).hexdigest()[:16],
                "statement": statement,
                "category": category,
                "source_file": path.name,
                "source_offset": match.start(),
                "speaker": "Josie-authored Alex constitution",
                "evidence_type": "explicit constitution",
                "confidence": 0.95,
                "confirmation_status": "candidate_review_required",
                "scope": ["alex_identity"],
                "sensitivity": "relationship-private",
                "contradictions": [],
            })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("sources", nargs="+")
    args = parser.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    records: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []
    for item in args.sources:
        path = Path(item)
        text = read_docx(path)
        records.append(source_record(path))
        candidates.extend(personality_candidates(path, text))

    (out / "alex_source_manifest.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "alex_candidate_extraction.jsonl").open("w", encoding="utf-8") as handle:
        for row in candidates:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
