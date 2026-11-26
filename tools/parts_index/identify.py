r"""Identify every distinct file in the zip catalog from its own content.

Reads catalog_raw.json (one record per file occurrence) and the content-addressed store x/_objects.
Writes identified.json: per distinct blob, what it is and its quality signals, all read from the bytes.
Nothing here is a judgement by name alone: every field comes from the file's content.
"""
import ast, json, os, re, subprocess, sys, collections

STORE = "/home/claude/bigzip/x/_objects"
recs = json.load(open("/home/claude/bigzip/catalog_raw.json"))
# Every path in the current build, by name. (A blob-keyed map loses every path whose content
# also sits at another path: 544 paths were invisible to the comparison that way.)
cur_paths = [p for p in subprocess.run(["git", "-C", "/home/claude/pre-dec", "ls-tree", "-r", "--name-only",
                                        "finish/control-room-engine"], capture_output=True, text=True,
                                       check=True).stdout.splitlines()
             if not p.startswith(("handoffs/parts_index/", "tools/parts_index/"))]
assert len(cur_paths) > 8000, len(cur_paths)
CUR_NAMES = {os.path.basename(p).lower() for p in cur_paths}
CUR_REPO = "/home/claude/pre-dec"

MAGIC = [(b"\x7fELF", "ELF executable"), (b"MZ", "Windows executable/DLL"), (b"PK\x03\x04", "zip archive"),
         (b"\x89PNG", "PNG image"), (b"\xff\xd8\xff", "JPEG image"), (b"glTF", "GLB 3D model"), (b"RIFF", "RIFF (WAV/AVI)"),
         (b"SQLite format 3", "SQLite database"), (b"%PDF", "PDF document"), (b"GIF8", "GIF image"),
         (b"\x1aE\xdf\xa3", "Matroska/WebM video"), (b"ID3", "MP3 audio"), (b"OggS", "Ogg audio")]
STUB = re.compile(rb"\b(TODO|FIXME|XXX|NotImplementedError|placeholder|stub|mock|fake|dummy|simulat)\w*", re.I)


def path_of(blob):
    return os.path.join(STORE, blob[:2], blob)


def text_of(data):
    if b"\0" in data[:4000]:
        return None
    try:
        return data.decode("utf-8-sig")      # a byte-order mark never reaches the parser or the summary
    except UnicodeDecodeError:
        return data.decode("latin-1")


COMMENT_STARTS = ("#", "//", "/*", "*", "<!--", '"""', "'''", "--")
CODE_EXTS = (".py", ".pyi", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".cjs", ".rs", ".css")


BLOCKS = (("/*", "*/"), ('"""', '"""'), ("'''", "'''"), ("<!--", "-->"))


def first_lines(text, n=3, comments_only=False):
    """The first meaningful lines; for code, only lines that are comments or inside a block comment/docstring."""
    out = []
    closing = None
    for line in text.splitlines():
        raw = line.strip()
        if comments_only:
            if closing is not None:
                if closing in raw:
                    closing = None
            else:
                opened = next((c for o, c in BLOCKS if raw.startswith(o) and not raw[len(o):].rstrip().endswith(c)), None)
                if opened is not None:
                    closing = opened
                elif raw and not raw.startswith(COMMENT_STARTS):
                    continue
        s = line.strip().strip("#/*\"' -=").strip()
        if len(s) > 3 and not s.lower().startswith(("import ", "from ", "use ", "#!", "coding", "copyright", "pubcast ai —", "rear view", "rearview", "feic mo")):
            out.append(s[:160])
        if len(out) >= n:
            break
    return " | ".join(out)


def py_info(text):
    info = {}
    try:
        tree = ast.parse(text)
        info["compiles"] = True
        doc = ast.get_docstring(tree)
        if doc:
            info["doc"] = " ".join(doc.split())[:300]
        defs = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        info["top_defs"] = defs[:25]
        info["n_defs"] = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
        info["n_classes"] = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        empty = 0
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = [b for b in n.body if not (isinstance(b, ast.Expr) and isinstance(getattr(b, "value", None), ast.Constant))]
                if len(body) == 1 and isinstance(body[0], (ast.Pass, ast.Raise)) or not body:
                    empty += 1
        info["empty_functions"] = empty
        routes = re.findall(r"@\w+\.(get|post|put|delete|patch|websocket)\(\s*[\"']([^\"']+)", text)
        if routes:
            info["routes"] = [f"{m.upper()} {p}" for m, p in routes][:20]
        imps = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                imps.update(a.name.split(".")[0] for a in n.names)
            elif isinstance(n, ast.ImportFrom) and n.module:
                imps.add(("." * n.level) + n.module.split(".")[0])
        info["imports"] = sorted(imps)[:30]
        info["is_test"] = any(d.startswith("test_") for d in defs)
    except SyntaxError as e:
        info["compiles"] = False
        info["syntax_error"] = f"line {e.lineno}: {e.msg}"
    return info


def js_info(text):
    info = {}
    fns = re.findall(r"(?:function\s+([A-Za-z_$][\w$]*)|(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function|\([^)]*\)\s*=>)|class\s+([A-Za-z_$][\w$]*))", text)
    names = [a or b or c for a, b, c in fns]
    info["top_defs"] = names[:25]
    info["n_defs"] = len(names)
    info["fetches"] = sorted(set(re.findall(r"['\"`](/api/[A-Za-z0-9_/\-{}.$]+)", text)))[:20]
    return info


def html_info(text):
    info = {}
    m = re.search(r"<title>(.*?)</title>", text, re.S | re.I)
    if m:
        info["title"] = " ".join(m.group(1).split())[:150]
    info["scripts"] = re.findall(r"<script[^>]+src=[\"']([^\"']+)", text)[:15]
    info["inline_script_chars"] = sum(len(s) for s in re.findall(r"<script[^>]*>(.*?)</script>", text, re.S))
    info["fetches"] = sorted(set(re.findall(r"['\"`](/api/[A-Za-z0-9_/\-{}.$]+)", text)))[:20]
    return info


def md_info(text):
    heads = re.findall(r"^#{1,3}\s+(.+)$", text, re.M)
    return {"headings": [h.strip()[:120] for h in heads[:8]]}


def json_info(text):
    try:
        obj = json.loads(text)
    except Exception:
        return {"valid_json": False}
    if isinstance(obj, dict):
        return {"valid_json": True, "keys": list(obj)[:20]}
    if isinstance(obj, list):
        return {"valid_json": True, "list_len": len(obj)}
    return {"valid_json": True}


GENERIC_NAMES = {'__init__.py', 'main.py', 'readme.md', 'index.html', 'index.js', 'config.json', 'package.json', 'requirements.txt', 'conftest.py', 'setup.py', 'lib.rs', 'mod.rs', 'app.py', 'routes.py', 'utils.py', 'handoff.md', 'status.md', 'manifest.json', 'cargo.toml'}


def diff_vs_current(text, name, inner_path):
    """When a file of the same name exists in the current branch: lines only here, lines only there."""
    # The current file whose path shares the most trailing folders with this one (not just the file name):
    # an __init__.py is compared with the __init__.py of the same package, never with any __init__.py.
    mine = [part.lower() for part in inner_path.replace("\\", "/").split("/")]
    def shared(p):
        theirs = [part.lower() for part in p.split("/")]
        k = 0
        while k < min(len(mine), len(theirs)) and mine[-1 - k] == theirs[-1 - k]:
            k += 1
        return k
    cands = [p for p in cur_paths if os.path.basename(p).lower() == name.lower()]
    cands.sort(key=lambda p: (-shared(p), p.startswith("recovery/"), len(p)))
    if not cands:
        return None
    top = shared(cands[0])
    generic = name.lower() in GENERIC_NAMES
    if generic and top < 2:
        return None           # a generic name with no matching folder: there is nothing meaningful to compare with
    best = None
    for p in [c for c in cands if shared(c) == top][:6]:
        got = subprocess.run(["git", "-C", CUR_REPO, "show", f"finish/control-room-engine:{p}"],
                             capture_output=True, timeout=30)
        if got.returncode != 0:     # a failed lookup must stop the run, never pass as an empty file
            raise SystemExit(f"current version of {p} could not be read: {got.stderr[:200]!r}")
        cur = got.stdout.decode("utf-8-sig", "replace")
        a, b = text.splitlines(), cur.splitlines()
        sa, sb = collections.Counter(a), collections.Counter(b)
        only_here = sum((sa - sb).values())
        only_cur = sum((sb - sa).values())
        score = only_here + only_cur
        if best is None or score < best["changed"]:
            best = {"current_path": p, "path_folders_matched": top - 1, "lines_here": len(a), "lines_current": len(b),
                    "lines_only_here": only_here, "lines_only_current": only_cur, "changed": score, "current_empty": len(b) == 0}
    return best


distinct = {}
occ = collections.defaultdict(list)
for r in recs:
    distinct.setdefault(r["blob"], r)
    occ[r["blob"]].append(" > ".join(r["chain"] + [r["path"]]))

out = {}
for i, (blob, r) in enumerate(distinct.items()):
    data = open(path_of(blob), "rb").read()
    ent = {"blob": blob, "size": len(data), "status": r["status"], "ext": r["ext"], "example": occ[blob][0],
           "occurrences": len(occ[blob])}
    kind = next((k for m, k in MAGIC if data.startswith(m)), None)
    if r["ext"] == ".pyc" or data[2:4] == b"\r\n" and r["ext"] in (".pyc",):
        kind = "compiled Python bytecode (.pyc)"
    text = None if kind else text_of(data)
    if kind:
        ent["kind"] = kind
    elif text is None:
        ent["kind"] = "binary (unrecognized)"
    else:
        ent["lines"] = text.count("\n") + 1
        ent["stub_markers"] = len(STUB.findall(text.encode("utf-8", "ignore")))
        ent["summary"] = first_lines(text, comments_only=r["ext"] in CODE_EXTS)
        if r["ext"] in (".py", ".pyi"):
            ent["kind"] = "Python"
            ent.update(py_info(text))
        elif r["ext"] in (".js", ".mjs", ".ts", ".tsx", ".jsx", ".cjs"):
            ent["kind"] = "JavaScript/TypeScript"
            ent.update(js_info(text))
        elif r["ext"] in (".html", ".htm"):
            ent["kind"] = "HTML page"
            ent.update(html_info(text))
        elif r["ext"] in (".md", ".txt", ".rst"):
            ent["kind"] = "document"
            ent.update(md_info(text))
        elif r["ext"] in (".json", ".jsonl"):
            ent["kind"] = "JSON data"
            ent.update(json_info(text) if r["ext"] == ".json" else {})
        elif r["ext"] == ".rs":
            ent["kind"] = "Rust"
            ent["top_defs"] = re.findall(r"^\s*(?:pub\s+)?(?:fn|struct|enum|impl|trait|mod)\s+([A-Za-z_][\w]*)", text, re.M)[:25]
        else:
            ent["kind"] = f"text ({r['ext']})"
        if r["status"] != "A_current" and os.path.basename(r["path"]).lower() in CUR_NAMES and ent.get("kind") in ("Python", "JavaScript/TypeScript", "HTML page", "Rust"):
            ent["vs_current"] = diff_vs_current(text, os.path.basename(r["path"]), r["path"])
    ent["all_locations"] = occ[blob][:12]
    out[blob] = ent
    if i % 1000 == 0:
        print(i, file=sys.stderr)

json.dump(out, open("/home/claude/bigzip/identified.json", "w"))
print("identified", len(out))
