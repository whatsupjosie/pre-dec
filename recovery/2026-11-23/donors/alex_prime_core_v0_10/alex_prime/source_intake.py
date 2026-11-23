from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from .serialization import to_jsonable


class SourceIntakeError(Exception):
    """Raised when uploaded source intake cannot be completed safely."""


@dataclass(frozen=True)
class SourceSymbol:
    name: str
    kind: str
    methods: List[str] = field(default_factory=list)
    line: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return to_jsonable(self)


@dataclass(frozen=True)
class SourceRiskMarker:
    line: int
    category: str
    text: str

    def to_dict(self) -> Dict[str, Any]:
        return to_jsonable(self)


@dataclass(frozen=True)
class SourceFileRecord:
    path: str
    sha256: str
    size_bytes: int
    line_count: int
    imports: List[str]
    symbols: List[SourceSymbol]
    risk_markers: List[SourceRiskMarker]
    parse_ok: bool = True
    parse_error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return to_jsonable(self)


@dataclass(frozen=True)
class SourceInventory:
    source_root: str
    records: List[SourceFileRecord]

    def to_dict(self) -> Dict[str, Any]:
        return to_jsonable(self)

    def by_filename(self, filename: str) -> SourceFileRecord:
        for record in self.records:
            if Path(record.path).name == filename:
                return record
        raise KeyError(filename)

    def records_with_risks(self) -> List[SourceFileRecord]:
        return [record for record in self.records if record.risk_markers]


class SourceInventoryBuilder:
    """Parse uploaded Python sources into a reproducible source inventory.

    This is not a replacement for code review. It is the intake gate that proves
    the files were actually read, hashed, parsed, and classified before any
    integration layer relies on them.
    """

    RISK_PATTERNS: Sequence[tuple[str, re.Pattern[str]]] = (
        ("unfinished_marker", re.compile(r"\b(" + "T" + "ODO" + r"|FIX" + "ME" + r"|not " + "implemented" + r")\b", re.IGNORECASE)),
        ("incomplete_runtime_claim", re.compile(r"\b(simulate|simulation mode|fake|" + "place" + "holder" + r")\b", re.IGNORECASE)),
        ("empty_pass_body", re.compile(r"^\s*pass\s*(#.*)?$", re.IGNORECASE)),
    )

    def build(self, source_root: Path | str) -> SourceInventory:
        root = Path(source_root).expanduser().resolve()
        if not root.exists():
            raise SourceIntakeError(f"source root does not exist: {root}")
        records = [self.read_file(path, root) for path in sorted(root.rglob("*.py"))]
        return SourceInventory(source_root=str(root), records=records)

    def read_file(self, path: Path | str, root: Path | None = None) -> SourceFileRecord:
        file_path = Path(path).expanduser().resolve()
        if not file_path.exists():
            raise SourceIntakeError(f"source file does not exist: {file_path}")
        data = file_path.read_bytes()
        text = data.decode("utf-8")
        relative = str(file_path if root is None else file_path.relative_to(root))
        risk_markers = self._risk_markers(text)
        try:
            tree = ast.parse(text)
            imports = self._imports(tree)
            symbols = self._symbols(tree)
            return SourceFileRecord(
                path=relative,
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data),
                line_count=max(1, text.count("\n") + 1),
                imports=imports,
                symbols=symbols,
                risk_markers=risk_markers,
            )
        except SyntaxError as exc:
            return SourceFileRecord(
                path=relative,
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data),
                line_count=max(1, text.count("\n") + 1),
                imports=[],
                symbols=[],
                risk_markers=risk_markers,
                parse_ok=False,
                parse_error=f"{exc.msg} at line {exc.lineno}",
            )

    def write_inventory(self, inventory: SourceInventory, output_path: Path | str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(inventory.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    def _risk_markers(self, text: str) -> List[SourceRiskMarker]:
        markers: List[SourceRiskMarker] = []
        for idx, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            for category, pattern in self.RISK_PATTERNS:
                if pattern.search(line):
                    markers.append(SourceRiskMarker(line=idx, category=category, text=stripped[:180]))
                    break
        return markers

    def _imports(self, tree: ast.AST) -> List[str]:
        imports: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imports.append(f"{module} import {','.join(alias.name for alias in node.names)}")
        return sorted(dict.fromkeys(imports))

    def _symbols(self, tree: ast.AST) -> List[SourceSymbol]:
        symbols: List[SourceSymbol] = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                methods = [
                    item.name
                    for item in node.body
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                symbols.append(SourceSymbol(name=node.name, kind="class", methods=methods, line=node.lineno))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(SourceSymbol(name=node.name, kind="function", line=node.lineno))
        return symbols
