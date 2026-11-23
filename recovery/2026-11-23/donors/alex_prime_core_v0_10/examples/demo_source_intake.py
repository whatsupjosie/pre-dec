from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alex_prime import SourceInventoryBuilder, SourceContractRegistry

root = Path(__file__).resolve().parents[1] / "source_locked" / "uploaded_pubcast_sources"
inventory = SourceInventoryBuilder().build(root)
print({"files_read": len(inventory.records), "files_with_risk_markers": len(inventory.records_with_risks())})
registry = SourceContractRegistry()
print(registry.get("epete").to_dict())
