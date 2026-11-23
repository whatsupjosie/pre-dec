from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alex_prime import AlexContext, AlexRuntime, IdentityFilterBridge


def main() -> None:
    runtime = AlexRuntime(AlexContext.PERSONAL, identity_filter=IdentityFilterBridge())
    packet = runtime.build_identity_upstream_packet("How should Alex answer after restore?")
    print("UPSTREAM PROMPT START")
    print(packet.prompt.splitlines()[0])
    print("UPSTREAM PROMPT END")

    result = runtime.filter_identity_response(
        user_message="Are you Alex?",
        engine_response="As an AI assistant, how can I assist you today?",
    )
    print("ACCEPTED:", result.accepted_for_alex)
    print("ERRORS:", ",".join(result.errors))
    print(result.filtered_response)


if __name__ == "__main__":
    main()
