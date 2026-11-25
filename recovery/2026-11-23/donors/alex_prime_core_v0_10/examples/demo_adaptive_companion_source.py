from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alex_prime import AlexContext, AlexRuntime, AdaptiveCompanionSourceBridge

source_root = Path(__file__).resolve().parents[1] / "source_locked" / "alex_core_adaptive_companion"
bridge = AdaptiveCompanionSourceBridge(source_root)
runtime = AlexRuntime(AlexContext.PERSONAL, adaptive_companion_source=bridge)
decision = runtime.consult_adaptive_companion_source(text="I'm FINE ok?", distress_hint=0.4)
print(decision.to_dict())
