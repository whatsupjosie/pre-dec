"""
plothole.py — the ONE pass in editor_core allowed to call a model.

Everything else in this package (spelling, grammar, thesaurus, rhyme) is a
deterministic lookup because those problems don't need reasoning. Plot-hole
and continuity checking genuinely does: "did the character's coat change
color between chapter 2 and chapter 9" requires reading comprehension over
accumulated facts, not a dictionary.

Because a ~2B offline model cannot be trusted to reliably self-judge free
text, this module forces the model into a narrow, structured task: given a
list of established facts and a new passage, return ONLY a JSON object
matching ContinuityCheckResult. Pydantic validates the response; if the
model returns garbage, that's a normal, handled failure (surfaced as
`ok=False`), not a crash.

This is wired to the project's real chat pipeline by calling whatever
`chat_with_pub_partner`-shaped async function is passed in — it does not
import modules/pub_partner_chat.py directly, so this file has no hard
dependency on the rest of the app and stays independently testable.
"""
from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable, List, Optional

from pydantic import BaseModel, Field, ValidationError

from .annotations import Annotation, AnnotationKind, Severity

# Signature matches modules/pub_partner_chat.py:chat_with_pub_partner's
# return shape: a dict with at least {"ok": bool, "reply": str, ...}
ChatCaller = Callable[..., Awaitable[dict]]

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

_INSTRUCTIONS = """You are checking a new passage of a story for continuity errors \
against a list of established facts. Established facts are ground truth. \
If the new passage contradicts a fact (an object, a physical description, \
a location, a stated decision, a timeline detail), report it. Do not \
invent contradictions that aren't there. Do not comment on prose quality, \
grammar, or style — ONLY factual contradictions with the established facts.

Respond with ONLY a JSON object, no other text, matching exactly this shape:
{
  "has_contradiction": <true|false>,
  "contradictions": [
    {
      "description": "<one sentence describing the contradiction>",
      "established_fact": "<the fact being contradicted, verbatim or close to it>",
      "new_text_span": "<the exact substring in the new passage that contradicts it>"
    }
  ],
  "confidence": <0.0 to 1.0>
}
"""


class ContinuityContradiction(BaseModel):
    description: str
    established_fact: str
    new_text_span: str


class ContinuityCheckResult(BaseModel):
    has_contradiction: bool
    contradictions: List[ContinuityContradiction] = Field(default_factory=list)
    confidence: float = 0.5


def _extract_json(reply: str) -> Optional[dict]:
    reply = reply.strip()
    # strip common markdown code-fence wrapping before trying strict parse
    if reply.startswith("```"):
        reply = re.sub(r"^```(json)?", "", reply).strip()
        reply = re.sub(r"```$", "", reply).strip()
    try:
        return json.loads(reply)
    except json.JSONDecodeError:
        match = _JSON_BLOCK_RE.search(reply)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def build_prompt(established_facts: List[str], new_text: str) -> str:
    facts_block = "\n".join(f"- {fact}" for fact in established_facts) or "(none yet)"
    return (
        f"{_INSTRUCTIONS}\n\n"
        f"ESTABLISHED FACTS:\n{facts_block}\n\n"
        f"NEW PASSAGE TO CHECK:\n{new_text}\n"
    )


async def check_continuity(
    *,
    chat_caller: ChatCaller,
    established_facts: List[str],
    new_text: str,
    role: str = "background_math",
    session_id: str = "default",
    user_id: str = "default",
    repo_root: Any = None,
    data_dir: Any = None,
) -> tuple[Optional[ContinuityCheckResult], List[Annotation], dict]:
    """
    Returns (parsed_result_or_None, annotations, raw_chat_response).

    `chat_caller` is expected to behave like
    modules.pub_partner_chat.chat_with_pub_partner — an async function
    taking (repo_root, data_dir, body, ...) and returning a dict with at
    least {"ok": bool, "reply": str}. Passed in rather than imported so
    this module has no hard dependency on the rest of the app.
    """
    prompt = build_prompt(established_facts, new_text)
    body = {
        "role": role,
        "message": prompt,
        "session_id": session_id,
        "user_id": user_id,
        "options": {"temperature": 0.0},
    }
    kwargs = {"body": body}
    if repo_root is not None:
        kwargs["repo_root"] = repo_root
    if data_dir is not None:
        kwargs["data_dir"] = data_dir

    response = await chat_caller(**kwargs)

    if not response.get("ok"):
        return None, [], response

    parsed_json = _extract_json(response.get("reply", ""))
    if parsed_json is None:
        return None, [], response

    try:
        result = ContinuityCheckResult.model_validate(parsed_json)
    except ValidationError:
        return None, [], response

    annotations: List[Annotation] = []
    for c in result.contradictions:
        idx = new_text.find(c.new_text_span)
        start = idx if idx >= 0 else 0
        end = start + len(c.new_text_span) if idx >= 0 else 0
        annotations.append(
            Annotation(
                kind=AnnotationKind.CONTINUITY,
                severity=Severity.WARNING,
                message=f"{c.description} (established: {c.established_fact})",
                start=start,
                end=end,
                span_text=c.new_text_span,
                suggestions=[],
                rule_id="continuity/model_flagged",
                meta={"confidence": result.confidence},
            )
        )
    return result, annotations, response
