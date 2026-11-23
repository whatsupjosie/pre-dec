from __future__ import annotations

import json
from pprint import pprint

from cre_eq import Baseline, ObservationPacket
from peq import PEQSystem, TruthAssessment, TruthStatus


def main() -> None:
    system = PEQSystem()
    packet = ObservationPacket(
        subject_id="owner",
        is_primary_user=True,
        text="OH GREAT!!! That's EXACTLY what I needed. I can't believe we finally fixed it.",
        recent_text=[
            "This bug has been driving me crazy.",
            "If this works, I'm going to lose my mind.",
        ],
        typing={"typing_wpm": 84.0, "typo_rate": 0.03},
        audio={"speech_rate_wpm": 181.0, "laughter_signal": 0.28},
        baseline=Baseline(
            typing_wpm=51.0,
            typo_rate=0.04,
            capitalization_ratio=0.01,
            avg_message_words=22.0,
        ),
        context={
            "interaction_goal": "support the user while working",
            "situation": "build just succeeded after repeated failures",
        },
    )
    truth = TruthAssessment(
        status=TruthStatus.SUPPORTED,
        proposition="The positive outcome is genuine rather than blocked.",
        reliability=0.96,
        source_summary="Outcome context is consistent with the user's positive report.",
    )
    result = system.assess(packet, truth_assessment=truth, stakes=0.35)

    print("PEQ STATE")
    print(result.state.formal_determination)
    print("\nExplanation:")
    print(result.state.explanation)
    print("\nTop candidates:")
    pprint([c.to_dict() for c in result.state.candidates[:3]] if hasattr(result.state.candidates[0], "to_dict") else result.state.to_dict()["candidates"][:3])

    print("\nPEQ RESPONSE")
    print(result.response.recommended_response)
    print(f"Modulation: {result.response.modulation.value}")
    print(f"Intensity: {result.response.intensity:.2f}")
    print(result.response.explanation)

    print("\nAUDIT")
    print(json.dumps(result.audit, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
