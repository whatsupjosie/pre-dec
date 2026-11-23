from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alex_prime import SourceContractRegistry

registry = SourceContractRegistry()
print([v.to_dict() for v in registry.validate_action("epete", "speak directly to user", user_visible=True)])
print([v.to_dict() for v in registry.validate_action("distributed_engine", "sacrifice audio to preserve 4K face")])
