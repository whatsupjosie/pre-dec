from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Sequence

CACHE_PATTERNS = (
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
)
BINARY_CACHE_SUFFIXES = (".pyc", ".pyo")

OWNED_TEXT_SUFFIXES = (".py", ".md", ".json", ".jsonl", ".txt", ".yaml", ".yml")
DEFAULT_EXCLUDE_DIRS = {
    "source_locked",  # Verbatim evidence may contain upstream words; do not rewrite it.
    ".git",
    "__pycache__",
    ".pytest_cache",
}

@dataclass(frozen=True)
class QualityIssue:
    code: str
    path: str
    detail: str

@dataclass
class ReleaseQualityReport:
    ok: bool
    issues: List[QualityIssue] = field(default_factory=list)

    def require_ok(self) -> None:
        if self.ok:
            return
        details = "\n".join(f"{i.code}: {i.path} :: {i.detail}" for i in self.issues)
        raise AssertionError(details)


def _is_excluded(path: Path, root: Path, exclude_dirs: set[str]) -> bool:
    rel_parts = path.relative_to(root).parts
    return any(part in exclude_dirs for part in rel_parts)


def scan_tree_for_cache_artifacts(root: Path | str) -> ReleaseQualityReport:
    root = Path(root)
    issues: List[QualityIssue] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root).as_posix()
        if path.is_dir() and path.name in {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}:
            issues.append(QualityIssue("CACHE_DIR", rel, "cache directory must not be shipped"))
        elif path.is_file() and path.suffix in BINARY_CACHE_SUFFIXES:
            issues.append(QualityIssue("CACHE_FILE", rel, "compiled cache file must not be shipped"))
    return ReleaseQualityReport(ok=not issues, issues=issues)


def scan_zip_for_cache_artifacts(zip_path: Path | str) -> ReleaseQualityReport:
    zip_path = Path(zip_path)
    issues: List[QualityIssue] = []
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if any(pattern in name for pattern in CACHE_PATTERNS):
                issues.append(QualityIssue("ZIP_CACHE_DIR", name, "cache directory path inside release zip"))
            if name.endswith(BINARY_CACHE_SUFFIXES):
                issues.append(QualityIssue("ZIP_CACHE_FILE", name, "compiled cache file inside release zip"))
    return ReleaseQualityReport(ok=not issues, issues=issues)


def scan_owned_files_for_banned_markers(
    root: Path | str,
    markers: Sequence[str] = ("TO" + "DO", "FIX" + "ME", "place" + "holder", "st" + "ub", "not " + "implemented"),
    exclude_dirs: Iterable[str] = DEFAULT_EXCLUDE_DIRS,
) -> ReleaseQualityReport:
    root = Path(root)
    exclude = set(exclude_dirs)
    pattern = re.compile("|".join(re.escape(m) for m in markers), re.IGNORECASE)
    issues: List[QualityIssue] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in OWNED_TEXT_SUFFIXES:
            continue
        if _is_excluded(path, root, exclude):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                issues.append(QualityIssue("BANNED_" + "MARKER", f"{path.relative_to(root).as_posix()}:{lineno}", line.strip()))
    return ReleaseQualityReport(ok=not issues, issues=issues)


def run_release_quality(root: Path | str, zip_path: Path | str | None = None) -> ReleaseQualityReport:
    reports = [
        scan_tree_for_cache_artifacts(root),
        scan_owned_files_for_banned_markers(root),
    ]
    if zip_path is not None:
        reports.append(scan_zip_for_cache_artifacts(zip_path))
    issues: List[QualityIssue] = []
    for report in reports:
        issues.extend(report.issues)
    return ReleaseQualityReport(ok=not issues, issues=issues)
