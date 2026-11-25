from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parent
PROFILES_DIR = ROOT / "profiles"
DATA_DIR = ROOT / "data"
STATIC_DIR = ROOT / "static"
MEMORY_PATH = DATA_DIR / "memory.jsonl"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_layout() -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    if not MEMORY_PATH.exists():
        MEMORY_PATH.write_text("", encoding="utf-8")


def load_profiles() -> Dict[str, Dict[str, Any]]:
    profiles: Dict[str, Dict[str, Any]] = {}
    for path in PROFILES_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            profile_id = str(data.get("id") or path.stem).strip().lower()
            data["id"] = profile_id
            profiles[profile_id] = data
        except Exception:
            continue
    return profiles


def read_memories(profile: str = "", query: str = "", limit: int = 8) -> List[Dict[str, Any]]:
    if not MEMORY_PATH.exists():
        return []
    terms = tokenize(query)
    rows: List[Dict[str, Any]] = []
    for line in MEMORY_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if profile and str(item.get("profile", "")).lower() != profile.lower():
            continue
        score = int(item.get("importance", 1))
        haystack = " ".join(
            [
                str(item.get("content", "")),
                " ".join(str(tag) for tag in item.get("tags", [])),
                str(item.get("kind", "")),
            ]
        ).lower()
        if terms:
            score += sum(3 for term in terms if term in haystack)
            if not any(term in haystack for term in terms):
                continue
        item["_score"] = score
        rows.append(item)
    rows.sort(key=lambda row: (row.get("_score", 0), row.get("created_at", "")), reverse=True)
    return rows[:limit]


def append_memory(item: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(item)
    item.setdefault("created_at", utc_now())
    item.setdefault("importance", 5)
    item.setdefault("kind", "note")
    item.setdefault("tags", [])
    item.setdefault("source", "manual")
    with MEMORY_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    return item


def tokenize(text: str) -> List[str]:
    return [part.lower() for part in re.findall(r"[A-Za-z0-9_']{3,}", text or "")]


def build_upstream_packet(profile: Dict[str, Any], message: str, source: str = "external_llm") -> Dict[str, Any]:
    memories = read_memories(profile=profile["id"], query=message, limit=6)
    memory_lines = "\n".join(
        f"- ({m.get('kind', 'note')}, importance {m.get('importance', 5)}) {m.get('content', '')}"
        for m in memories
    ) or "- No relevant local memories found."
    boundaries = "\n".join(f"- {line}" for line in profile.get("boundaries", []))
    prompt = f"""You are an upstream knowledge engine. You are not {profile.get('display_name')}.

The local portable identity filter will read your answer afterward and translate it through {profile.get('display_name')}.

User message:
{message}

Relevant local context for usefulness:
{memory_lines}

Rules:
{boundaries}

Answer the user's request clearly and honestly. Do not pretend to be the local identity filter."""
    return {
        "profile": profile["id"],
        "source": source,
        "prompt": prompt,
        "memories": memories,
    }


def fallback_filter(profile: Dict[str, Any], user_message: str, engine_response: str, memories: List[Dict[str, Any]]) -> str:
    display = profile.get("display_name", profile["id"])
    memory_hint = ""
    if memories:
        memory_hint = "\n\nWhat I am carrying with this:\n" + "\n".join(
            f"- {m.get('content', '')}" for m in memories[:3]
        )
    return (
        f"{display} read the engine answer and is carrying it back through the local filter.\n\n"
        f"{engine_response.strip()}"
        f"{memory_hint}\n\n"
        f"Note: this was framed locally without a rewrite model, so the facts are preserved but the voice is light."
    ).strip()


def ollama_filter(profile: Dict[str, Any], user_message: str, engine_response: str, memories: List[Dict[str, Any]]) -> str:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    model = str(profile.get("local_filter_model") or os.environ.get("OLLAMA_MODEL") or "ministral-pubcast:3b")
    memory_lines = "\n".join(f"- {m.get('content', '')}" for m in memories[:6]) or "- No relevant memories."
    boundaries = "\n".join(f"- {line}" for line in profile.get("boundaries", []))
    prompt = f"""You are the local {profile.get('display_name')} identity filter.

Your job is to read a raw upstream LLM answer and return the version that should reach the user.

Voice:
{json.dumps(profile.get('voice', {}), ensure_ascii=False)}

Boundaries:
{boundaries}

Relevant memory:
{memory_lines}

User message:
{user_message}

Raw upstream answer:
{engine_response}

Return only the filtered answer. Preserve facts. Do not invent memories. If the raw answer is wrong or uncertain, say so gently."""
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": os.environ.get("OLLAMA_KEEP_ALIVE", "1h"),
        "options": {
            "num_ctx": int(os.environ.get("OLLAMA_NUM_CTX", "2048")),
            "num_predict": int(os.environ.get("IDENTITY_FILTER_NUM_PREDICT", "220")),
            "temperature": float(os.environ.get("IDENTITY_FILTER_TEMPERATURE", "0.45")),
        },
    }
    request = urllib.request.Request(
        f"{host}/api/generate",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=float(os.environ.get("OLLAMA_TIMEOUT", "180"))) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return str(payload.get("response", "")).strip()


def filter_response(profile: Dict[str, Any], user_message: str, engine_response: str, source: str) -> Dict[str, Any]:
    memories = read_memories(profile=profile["id"], query=user_message + "\n" + engine_response, limit=6)
    used_model = False
    error = ""
    try:
        filtered = ollama_filter(profile, user_message, engine_response, memories)
        used_model = bool(filtered)
        if not filtered:
            filtered = fallback_filter(profile, user_message, engine_response, memories)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        error = str(exc)
        filtered = fallback_filter(profile, user_message, engine_response, memories)

    stored = append_memory(
        {
            "profile": profile["id"],
            "kind": "conversation_trace",
            "importance": 4,
            "tags": ["filtered_response", source],
            "content": f"User asked: {user_message[:240]} | Engine answered: {engine_response[:360]}",
            "source": f"filter:{source}",
        }
    )
    return {
        "profile": profile["id"],
        "used_local_model": used_model,
        "error": error,
        "filtered_response": filtered,
        "stored_memory": stored,
    }


class Handler(SimpleHTTPRequestHandler):
    server_version = "PortableIdentityFilter/0.1"

    def translate_path(self, path: str) -> str:
        if path == "/" or path.startswith("/static/"):
            rel = "index.html" if path == "/" else path.removeprefix("/static/")
            return str(STATIC_DIR / rel)
        return str(STATIC_DIR / "index.html")

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8765")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:
        if self.path.startswith("/api/"):
            self.handle_api_get()
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path.startswith("/api/"):
            self.handle_api_post()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def write_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def get_profile(self, profile_id: str) -> Dict[str, Any]:
        profiles = load_profiles()
        profile = profiles.get((profile_id or "alex").lower())
        if not profile:
            raise KeyError(profile_id)
        return profile

    def handle_api_get(self) -> None:
        profiles = load_profiles()
        if self.path == "/api/health":
            self.write_json({"ok": True, "time": utc_now(), "profiles": sorted(profiles)})
            return
        if self.path == "/api/profiles":
            self.write_json({"profiles": list(profiles.values())})
            return
        if self.path.startswith("/api/memory"):
            profile = ""
            query = ""
            if "?" in self.path:
                _, params = self.path.split("?", 1)
                for pair in params.split("&"):
                    key, _, value = pair.partition("=")
                    value = urllib.parse.unquote_plus(value)
                    if key == "profile":
                        profile = value
                    elif key == "q":
                        query = value
            self.write_json({"memories": read_memories(profile=profile, query=query, limit=25)})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def handle_api_post(self) -> None:
        try:
            payload = self.read_json()
            if self.path == "/api/filter/request":
                profile = self.get_profile(str(payload.get("profile", "alex")))
                self.write_json(
                    build_upstream_packet(
                        profile,
                        str(payload.get("message", "")),
                        str(payload.get("source", "external_llm")),
                    )
                )
                return
            if self.path == "/api/filter/response":
                profile = self.get_profile(str(payload.get("profile", "alex")))
                self.write_json(
                    filter_response(
                        profile,
                        str(payload.get("message", "")),
                        str(payload.get("engine_response", "")),
                        str(payload.get("source", "external_llm")),
                    )
                )
                return
            if self.path == "/api/memory":
                item = append_memory(payload)
                self.write_json({"stored": item})
                return
        except KeyError as exc:
            self.write_json({"error": f"Unknown profile: {exc}"}, status=404)
            return
        except Exception as exc:
            self.write_json({"error": str(exc)}, status=500)
            return
        self.send_error(HTTPStatus.NOT_FOUND)


def main() -> None:
    parser = argparse.ArgumentParser(description="Portable Identity Filter")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    args = parser.parse_args()
    ensure_layout()
    os.chdir(STATIC_DIR)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Portable Identity Filter running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

