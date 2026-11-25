from __future__ import annotations

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alex_prime import AlexContext, AlexRuntime, UserSignal


if __name__ == "__main__":
    runtime = AlexRuntime(AlexContext.PERSONAL)
    decision = runtime.assess_personal_support(
        UserSignal(text="everything is broken and I can't think", task_context="coding")
    )
    print(decision.to_dict())
