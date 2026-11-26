r"""Identify every distinct file in the zip catalog from its own content.

Reads catalog_raw.json (one record per file occurrence) and the content-addressed store x/_objects.
Writes identified.json: per distinct blob, what it is and its quality signals, all read from the bytes.
Nothing here is a judgement by name alone: every field comes from the file's content.
"""
import ast, json, os, re, subprocess, sys, collections

STORE = "/home/claude/bigzip/x/_objects"
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




def identify(data, ext):
    ent = {}
    kind = next((k for m, k in MAGIC if data.startswith(m)), None)
    if ext == ".pyc":
        kind = "compiled Python bytecode (.pyc)"
    text = None if kind else text_of(data)
    if kind:
        ent["kind"] = kind
    elif text is None:
        ent["kind"] = "binary (unrecognized)"
    else:
        ent["lines"] = text.count("\n") + 1
        ent["stub_markers"] = len(STUB.findall(text.encode("utf-8", "ignore")))
        ent["summary"] = first_lines(text, comments_only=ext in CODE_EXTS)
        if ext in (".py", ".pyi"):
            ent["kind"] = "Python"; ent.update(py_info(text))
        elif ext in (".js", ".mjs", ".ts", ".tsx", ".jsx", ".cjs"):
            ent["kind"] = "JavaScript/TypeScript"; ent.update(js_info(text))
        elif ext in (".html", ".htm"):
            ent["kind"] = "HTML page"; ent.update(html_info(text))
        elif ext in (".md", ".txt", ".rst"):
            ent["kind"] = "document"; ent.update(md_info(text))
        elif ext == ".json":
            ent["kind"] = "JSON data"; ent.update(json_info(text))
        elif ext == ".rs":
            ent["kind"] = "Rust"
            ent["top_defs"] = re.findall(r"^\s*(?:pub\s+)?(?:fn|struct|enum|impl|trait|mod)\s+([A-Za-z_][\w]*)", text, re.M)[:25]
        else:
            ent["kind"] = f"text ({ext})"
    return ent
