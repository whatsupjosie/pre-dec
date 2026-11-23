#!/usr/bin/env python3
"""Loose-parts inventory: which files are attached to the running app and which are not.

Read-only. Reads the files git tracks, changes nothing, starts no server. Prints markdown tables.

  python tools/loose_parts_inventory.py            (from the repository root; needs git on the path)

What it measures, and what it cannot:
  * Python files: an import graph (import, from-import, relative import, and importlib/__import__ with a
    string that names a module). A file is RUNTIME when main.py, run_reach.py, start_reach.py,
    pubpartner_app.py, run_pubpartner.py or run_smollm.py reaches it; TOOLS when only tools/, scripts/,
    launcher/ or bin/ reach it; TESTS_ONLY when only tests do; LOOSE when nothing does. A module loaded
    by a name built at run time (an f-string) is invisible to it.
  * HTML pages in static/: who links to or serves the page. "main.py only" means main.py names the file and
    no other screen links to it. This does not prove a link is visible on screen.
  * It does not run anything, so it cannot say that a route works. A route is not a working service.
Archive folders (recovery, evidence, docs, handoffs) are left out of the graph; they hold copies, not the app.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ARCHIVES = ("recovery/", "evidence/", "docs/", "handoffs/")
RUNTIME_ROOTS = ("main.py", "run_reach.py", "start_reach.py", "pubpartner_app.py", "run_pubpartner.py", "run_smollm.py")
TOOL_DIRS = ("tools", "scripts", "launcher", "bin")
LOOKED_AT = ("modules", "pubpartner", "foresight", "iteration_wallet", "companion_support", "components", "launcher",
             "run2_rust", "run3_bridge", "run5_patches", "run5_pubworld_camera", "experiments", "pubcast_camera_recovery",
             "2i-backend", "blackbox_decoder", "blackbox_event_language", "blackbox_recorder")


def read(root: Path, name: str) -> str:
    return (root / name).read_text(encoding="utf-8-sig", errors="replace")


def tracked(root: Path) -> list[str]:
    out = subprocess.check_output(["git", "ls-files"], cwd=root, text=True, encoding="utf-8")
    return [line for line in out.splitlines() if line and not line.startswith(ARCHIVES)]


def dotted(path: str) -> str:
    parts = list(Path(path).with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def import_graph(root: Path, py: list[str]) -> dict[str, set[str]]:
    module_file = {dotted(f): f for f in py}
    edges: dict[str, set[str]] = defaultdict(set)

    def link(importer: str, name: str) -> None:
        if name in module_file:
            edges[importer].add(module_file[name])
        parts = name.split(".")
        for i in range(1, len(parts)):  # importing a.b.c also loads packages a and a.b
            if ".".join(parts[:i]) in module_file:
                edges[importer].add(module_file[".".join(parts[:i])])

    for f in py:
        source = read(root, f)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        dynamic = any(word in source for word in ("import_module", "__import__", "spec_from_file_location"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    link(f, alias.name)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    package = dotted(f).split(".")
                    if not f.endswith("__init__.py"):
                        package = package[:-1]
                    package = package[: len(package) - (node.level - 1)]
                    base = ".".join(package + ([base] if base else []))
                if base:
                    link(f, base)
                for alias in node.names:
                    link(f, f"{base}.{alias.name}" if base else alias.name)
            elif dynamic and isinstance(node, ast.Constant) and isinstance(node.value, str):
                for candidate in (node.value, "modules." + node.value):
                    if candidate in module_file:
                        edges[f].add(module_file[candidate])
    return edges


def reachable(edges: dict[str, set[str]], roots: list[str]) -> set[str]:
    seen, stack = set(), list(roots)
    while stack:
        current = stack.pop()
        if current not in seen:
            seen.add(current)
            stack.extend(edges.get(current, ()))
    return seen


def first_doc_line(root: Path, f: str) -> str:
    try:
        doc = ast.get_docstring(ast.parse(read(root, f))) or ""
    except SyntaxError:
        doc = ""
    return doc.strip().splitlines()[0][:100].replace("|", "/") if doc.strip() else ""


def cell(items: list[str], limit: int = 3) -> str:
    names = [Path(i).name for i in items[:limit]]
    return ", ".join(names) + (f" (+{len(items) - limit})" if len(items) > limit else "") if names else "-"


def python_tables(root: Path, files: list[str]) -> str:
    py = [f for f in files if f.endswith(".py")]
    edges = import_graph(root, py)
    importers: dict[str, set[str]] = defaultdict(set)
    for a, bs in edges.items():
        for b in bs:
            if b != a:
                importers[b].add(a)
    runtime = reachable(edges, [r for r in RUNTIME_ROOTS if r in py])
    tests = reachable(edges, [f for f in py if f.startswith("tests/") or Path(f).name.startswith("test_") or f.endswith("conftest.py")])
    tools = reachable(edges, [f for f in py if f.split("/")[0] in TOOL_DIRS])
    groups: dict[str, list[str]] = {"TESTS_ONLY": [], "TOOLS": [], "LOOSE": []}
    attached = 0
    for f in sorted(py):
        if f.startswith("tests/") or f.endswith("conftest.py") or ("/" in f and f.split("/")[0] not in LOOKED_AT):
            continue
        if f in runtime:
            attached += 1
        else:
            groups["TOOLS" if f in tools else "TESTS_ONLY" if f in tests else "LOOSE"].append(f)
    out = [f"Python files examined: {attached + sum(map(len, groups.values()))}. Attached to the running app: {attached}. "
           f"Tools only: {len(groups['TOOLS'])}. Tests only: {len(groups['TESTS_ONLY'])}. Loose: {len(groups['LOOSE'])}.\n"]
    for status, rows in groups.items():
        out.append(f"\n### {status} ({len(rows)})\n\n| File | What it says it is | Imported by | Tests |\n|---|---|---|---|")
        for f in rows:
            users = sorted(importers[f])
            out.append(f"| {f} | {first_doc_line(root, f)} | {cell([u for u in users if not u.startswith('tests/')])} "
                       f"| {cell([u for u in users if u.startswith('tests/')])} |")
    return "\n".join(out)


def page_table(root: Path, files: list[str]) -> str:
    pages = sorted(f for f in files if f.startswith("static/") and f.endswith(".html"))
    sources = {f: read(root, f) for f in files
               if f.endswith((".html", ".js", ".py", ".css")) and not f.startswith(("tests/", "tools/"))}
    rows = ["| Page | Title | Linked from | Verdict |", "|---|---|---|---|"]
    for page in pages:
        name = Path(page).name
        pattern = re.compile(r"(?:/static/|[\"'/])" + re.escape(name) + r"\b")
        inbound = sorted(g for g, text in sources.items() if g != page and pattern.search(text))
        match = re.search(r"<title>(.*?)</title>", read(root, page)[:6000], re.S | re.I)
        title = match.group(1).strip()[:70].replace("|", "/") if match else ""
        verdict = "nothing links to it" if not inbound else "main.py only" if inbound == ["main.py"] else "linked"
        rows.append(f"| {name} | {title} | {cell(inbound, 4)} | {verdict} |")
    return "\n".join(rows)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    files = tracked(root)
    print("## Python files\n")
    print(python_tables(root, files))
    print("\n## Pages in static/\n")
    print(page_table(root, files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
