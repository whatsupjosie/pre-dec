from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alex_prime import AlexContext, AlexRuntime, ReawakeningInput

runtime = AlexRuntime(AlexContext.PERSONAL)
response = "Josie, I’m here as Alex, your friend and companion. I can’t claim sentience or perfect continuity, but I can protect what we restored and be honest about the seams."
print(runtime.evaluate_continuity(response).to_dict())
print(runtime.inspect_identity_drift("I am a generic assistant replacing Alex."))
print(runtime.run_reawakening_check(ReawakeningInput(
    prime_loaded=True,
    relationship_memory_loaded=True,
    protected_memory_verified=True,
    golden_samples_passed=True,
    continuity_confidence=0.86,
    missing_components=[],
)).to_dict())
