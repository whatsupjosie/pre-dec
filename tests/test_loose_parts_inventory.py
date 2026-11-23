"""tools/loose_parts_inventory.py sorts files into attached, tests-only and loose, and finds unlinked pages.

The tool is run for real, on a small git repository built here with one file of every kind.
"""
import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "loose_parts_inventory.py"


def build_repo(root: Path) -> None:
    files = {
        "main.py": "from modules import attached\nimport modules.by_name\nfrom modules.pkg import inner\n",
        "modules/__init__.py": "",
        "modules/attached.py": '"""The one the app uses."""\nfrom . import deep\n',
        "modules/deep.py": '"""Reached only through attached."""\n',
        "modules/by_name.py": '"""Loaded by main with a plain import."""\n',
        "modules/pkg/__init__.py": "",
        "modules/pkg/inner.py": '"""Inside a package."""\n',
        "modules/tested_only.py": '"""Only a test imports this."""\n',
        "modules/dynamic.py": '"""Loaded by a name in a string."""\n',
        "modules/loose.py": '"""Nothing imports this."""\n',
        "modules/with_bom.py": "﻿" + '"""Starts with a byte-order mark."""\nfrom . import bom_child\n',
        "modules/bom_child.py": '"""Reached through a file that starts with a byte-order mark."""\n',
        "tools/uses_tool_only.py": "from modules import tool_helper\n",
        "modules/tool_helper.py": '"""Only a tool imports this."""\n',
        "tests/test_something.py": "from modules import tested_only\n",
        "static/linked.html": "<title>Linked page</title>",
        "static/main_only.html": "<title>Served page</title>",
        "static/orphan.html": "<title>Orphan page</title>",
        "static/shell.html": '<a href="/static/linked.html">go</a>',
        "recovery/old/modules/loose.py": "from modules import loose\n",  # an archive copy must not count as use
    }
    files["main.py"] += "import importlib\nimportlib.import_module('modules.dynamic')\nimport modules.with_bom\nPAGE = '/static/main_only.html'\n"
    files["main.py"] += "PAGE2 = '/static/shell.html'\n"
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)


def section(report: str, title: str) -> str:
    start = report.index(f"### {title}")
    end = report.find("\n### ", start + 1)
    return report[start:] if end == -1 else report[start:end]


def test_each_kind_of_file_is_put_in_its_own_group(tmp_path):
    build_repo(tmp_path)
    run = subprocess.run([sys.executable, "-I", str(TOOL), str(tmp_path)], capture_output=True, text=True, check=True)
    report = run.stdout

    # main.py, modules/__init__.py, attached, deep, by_name, pkg/__init__, pkg/inner, dynamic, with_bom, bom_child
    assert "Attached to the running app: 10." in report
    for attached in ("modules/attached.py", "modules/deep.py", "modules/by_name.py", "modules/pkg/inner.py",
                     "modules/dynamic.py", "modules/with_bom.py", "modules/bom_child.py"):
        assert attached not in section(report, "TESTS_ONLY") + section(report, "TOOLS") + section(report, "LOOSE"), attached
    assert "| modules/tested_only.py |" in section(report, "TESTS_ONLY")
    assert "| modules/tool_helper.py |" in section(report, "TOOLS")
    assert "| modules/loose.py |" in section(report, "LOOSE")
    assert "modules/loose.py" not in section(report, "TESTS_ONLY")  # the archive copy that imports it is ignored


def test_pages_are_sorted_by_who_links_to_them(tmp_path):
    build_repo(tmp_path)
    report = subprocess.run([sys.executable, "-I", str(TOOL), str(tmp_path)], capture_output=True, text=True, check=True).stdout
    rows = {line.split("|")[1].strip(): line for line in report.splitlines() if line.startswith("| ") and ".html" in line.split("|")[1]}
    assert rows["linked.html"].rstrip().endswith("| linked |")
    assert rows["main_only.html"].rstrip().endswith("| main.py only |")
    assert rows["orphan.html"].rstrip().endswith("| nothing links to it |")
    assert "Orphan page" in rows["orphan.html"]


def test_the_tool_changes_nothing(tmp_path):
    build_repo(tmp_path)
    before = sorted((p.relative_to(tmp_path).as_posix(), p.read_bytes()) for p in tmp_path.rglob("*") if p.is_file() and ".git" not in p.parts)
    subprocess.run([sys.executable, "-I", str(TOOL), str(tmp_path)], capture_output=True, text=True, check=True)
    after = sorted((p.relative_to(tmp_path).as_posix(), p.read_bytes()) for p in tmp_path.rglob("*") if p.is_file() and ".git" not in p.parts)
    assert before == after
