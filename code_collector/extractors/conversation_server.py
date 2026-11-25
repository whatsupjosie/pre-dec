"""
extractors/conversation_server.py
══════════════════════════════════
Subprocess wrapper for the conversation extractor.
Called by session_endpoints.js via execFile.

Reads JSON payload from stdin.
Writes JSON summary to stdout.
Writes errors to stderr.

INPUT (from session_endpoints.js):
{
  "session_id":   str,
  "platform":     str,
  "source_url":   str,
  "source_title": str,
  "turns": [
    { "role": "user"|"assistant", "content": str, "ts": float }
  ]
}

OUTPUT (to session_endpoints.js):
{
  "session_id":    str,
  "platform":      str,
  "source_url":    str,
  "context":       str,   ← the formatted context block text
  "files_touched": list,
  "decisions":     list,
  "breaks":        list,
  "builds":        list,
  "next_steps":    list,
  "turn_count":    int
}

Rear View Foresight LLC — Feic Mo Chroí
"""

import json
import sys
import os

# Resolve script location robustly — works even if symlinked or run from
# a different working directory. __file__ may be relative on some platforms
# so we resolve it to an absolute path first.
_SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_DIR not in sys.path:
    sys.path.insert(0, _PROJECT_DIR)

from extractors.conversation import ConversationExtractor, ConversationTurn

# Hard cap on JSON output size — prevents OOM in the Node process that
# reads this via execFile stdout buffer.
_MAX_OUTPUT_BYTES = 512 * 1024  # 512KB


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
    except Exception as e:
        print(json.dumps({"error": f"bad input: {e}"}), file=sys.stderr)
        sys.exit(1)

    session_id   = payload.get("session_id", "unknown")
    platform     = payload.get("platform", "claude")
    source_url   = payload.get("source_url", "")
    source_title = payload.get("source_title", "Claude")
    raw_turns    = payload.get("turns", [])

    extractor = ConversationExtractor(
        session_id   = session_id,
        source_url   = source_url,
        source_title = source_title,
        platform     = platform,
    )
    extractor.ingest_raw(raw_turns)

    summary = extractor.summarize()
    context_block = summary.to_context_block()

    result = {
        "session_id":    summary.session_id,
        "platform":      summary.platform,
        "source_url":    summary.source_url,
        "context":       context_block["content"],
        "files_touched": summary.files_touched,
        "decisions":     summary.decisions,
        "breaks":        summary.breaks,
        "builds":        summary.builds,
        "next_steps":    summary.next_steps,
        "turn_count":    summary.turn_count,
    }

    output = json.dumps(result)
    if len(output) > _MAX_OUTPUT_BYTES:
        # Truncate context to fit — prefer losing some context to crashing Node
        result["context"] = result["context"][:10_000] + "\n[context truncated — session too large]"
        result["decisions"] = result["decisions"][:5]
        result["builds"]    = result["builds"][:5]
        result["breaks"]    = result["breaks"][:5]
        output = json.dumps(result)
    print(output)


if __name__ == "__main__":
    main()
