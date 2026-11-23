from __future__ import annotations

import json
from pprint import pprint

from cre_eq import Baseline, CriticalReasoningEngine, ObservationPacket, TestResult, TestSpec


def main() -> None:
    engine = CriticalReasoningEngine()
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
        context={"interaction_goal": "support the user while working"},
    )

    first = engine.assess(packet)
    print("FORMAL DETERMINATION")
    print(first.formal_determination)
    print(f"Status: {first.status.value}")
    print(f"Confidence: {first.confidence:.0%}")
    print("\nINTERPRETIVE ASSESSMENT")
    print(first.interpretive_assessment)
    print("\nRESPONSE APPRAISAL")
    pprint(first.response_appraisal)

    spec = TestSpec(
        test_id="demo_context",
        name="outcome confirmation",
        purpose="distinguish excitement from frustration",
        assumption_ids=["A1", "A2"],
        expected_if={
            "excitement": "positive outcome confirmed",
            "frustration": "negative or blocked outcome confirmed",
        },
        procedure="Confirm whether the task actually succeeded.",
    )
    observed = TestResult(
        test_id="demo_context",
        result="positive outcome confirmed",
        observation="User confirms the build passed.",
        supports=["excitement"],
        weakens=["frustration"],
        materiality=0.85,
    )
    final = engine.assess(packet, extra_tests=[(spec, observed)])
    print("\nAFTER DISCRIMINATING TEST")
    print(final.formal_determination)
    print(f"Status: {final.status.value}")
    print(f"Confidence: {final.confidence:.0%}")

    print("\nAUDIT TRACE")
    print(json.dumps(final.trace.to_dict(), indent=2, default=str))


if __name__ == "__main__":
    main()
