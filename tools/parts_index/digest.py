"""Print a reading digest of stored zip contents: where, size, docstring, every class/def with its first doc line.
Usage: python -I digest.py PREFIX [PREFIX...]   (fingerprint prefixes, or name=NAME to take every version of a name)"""
import ast, csv, glob, json, re, sys
csv.field_size_limit(10**9)
C = json.load(open("/home/claude/bigzip/engine_candidates.json"))
want = []
for a in sys.argv[1:]:
    if a.startswith("name="):
        want += [r for r in C if r["name"] == a[5:]]
    else:
        want += [r for r in C if r["fingerprint"].startswith(a)]
for r in want:
    fp = r["fingerprint"]
    t = open(glob.glob(f"/home/claude/bigzip/x/_objects/{fp[:2]}/{fp}")[0], encoding="utf-8-sig", errors="replace").read()
    loc = r["location"].split(" >> ")
    print(f"\n##### {r['name']} [{fp[:8]}] {len(t.splitlines())} lines | {loc[0][-70:]} >> {loc[-1][-110:]}")
    print("   status:", r["status"][:230])
    if r["name"].endswith((".py", ".pyi")):
        try:
            m = ast.parse(t)
        except SyntaxError as e:
            print("   SYNTAX ERROR", e); continue
        print("   doc:", " ".join((ast.get_docstring(m) or "").split())[:500])
        for n in ast.walk(m):
            if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                d = " ".join((ast.get_docstring(n) or "").split())[:100]
                body = [s for s in n.body if not (isinstance(s, ast.Expr) and isinstance(getattr(s, "value", None), ast.Constant))]
                empty = all(isinstance(s, (ast.Pass, ast.Raise)) for s in body) if body else True
                print(f"   L{n.lineno} {'C' if isinstance(n, ast.ClassDef) else 'f'} {n.name}{' [EMPTY]' if empty and not isinstance(n, ast.ClassDef) else ''} {d}")
        routes = re.findall(r"@\w+\.(get|post|put|delete|websocket|patch)\(\s*['\"]([^'\"]+)", t)
        if routes: print("   routes:", ", ".join(f"{m.upper()} {p}" for m, p in routes)[:600])
    else:
        heads = re.findall(r"^\s*(?://[/!]|#|/\*\*?)\s?(.*)$", t, re.M)[:12]
        print("   comments:", " | ".join(h.strip()[:90] for h in heads if h.strip())[:900])
        defs = re.findall(r"^\s*(?:pub\s+)?(?:async\s+)?(?:fn|struct|enum|impl|trait|function|class)\s+([A-Za-z_$][\w$]*)", t, re.M)
        print("   defs:", ", ".join(defs[:60]))
        api = sorted(set(re.findall(r"['\"`](/(?:api|ws)/[A-Za-z0-9_/\-{}.$]+)", t)))
        if api: print("   api:", ", ".join(api[:30]))
