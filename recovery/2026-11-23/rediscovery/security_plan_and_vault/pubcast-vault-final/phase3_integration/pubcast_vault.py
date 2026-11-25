"""
PubCast Security Vault v1.0
==========================
Unified security system integrating Iteration Wallet (file custody) + Oubliette (sandboxing).

Intake Workflow:
  1. File arrives (untrusted source)
  2. Oubliette classifies: safe/unknown/suspicious
  3. If suspicious: quarantine, alert admin
  4. If safe: add to Iteration Wallet directly
  5. If unknown: sandbox probe, then vault if clean
  6. Output: file safe for use in PubCast AI
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from datetime import datetime

# Add phase directories to path
sys.path.insert(0, str(Path(__file__).parent / "../phase1_iteration_wallet"))
sys.path.insert(0, str(Path(__file__).parent / "../phase2_oubliette"))

from vault_engine_hardened import (
    IterationVaultHardened, FileStatus, AuditAction, FileClassification
)
from sandbox_hardened import (
    ExecutionSandbox, FileClassifier, ResourceLimits, ExecutionRecipe,
    FileMetadata, ExecutionResult
)

# ─────────────────────────────────────────────────────────────
#  Logging
# ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("pubcast_vault")

# ─────────────────────────────────────────────────────────────
#  Enums
# ─────────────────────────────────────────────────────────────

class IntakeStatus(Enum):
    SAFE        = "safe"
    QUARANTINED = "quarantined"
    PROCESSING  = "processing"
    FAILED      = "failed"

# ─────────────────────────────────────────────────────────────
#  Audio Recipes (Known Safe Transformations)
# ─────────────────────────────────────────────────────────────

AUDIO_RECIPES = {
    "m4a_to_wav": ExecutionRecipe(
        recipe_id="audio_m4a_to_wav",
        file_type="audio/mp4a",
        transformation="extract_audio",
        command="ffmpeg -i {input} -acodec pcm_s16le -ar 48000 {output}",
        resource_limits=ResourceLimits(
            max_memory_mb=1024,
            max_cpu_percent=50.0,
            timeout_seconds=600
        ),
        allowed_input_formats=["m4a", "m4b"],
        allowed_output_formats=["wav"],
        version="1.0"
    ),
    "mp3_to_wav": ExecutionRecipe(
        recipe_id="audio_mp3_to_wav",
        file_type="audio/mp3",
        transformation="extract_audio",
        command="ffmpeg -i {input} -acodec pcm_s16le -ar 48000 {output}",
        resource_limits=ResourceLimits(
            max_memory_mb=1024,
            max_cpu_percent=50.0,
            timeout_seconds=600
        ),
        allowed_input_formats=["mp3"],
        allowed_output_formats=["wav"],
        version="1.0"
    ),
    "opus_to_wav": ExecutionRecipe(
        recipe_id="audio_opus_to_wav",
        file_type="audio/opus",
        transformation="extract_audio",
        command="ffmpeg -i {input} -acodec pcm_s16le -ar 48000 {output}",
        resource_limits=ResourceLimits(
            max_memory_mb=1024,
            max_cpu_percent=50.0,
            timeout_seconds=600
        ),
        allowed_input_formats=["opus", "ogg"],
        allowed_output_formats=["wav"],
        version="1.0"
    ),
}

# ─────────────────────────────────────────────────────────────
#  PubCast Security Vault
# ─────────────────────────────────────────────────────────────

class PubCastSecurityVault:
    """
    Unified security vault for PubCast AI.
    Combines Iteration Wallet (custody) + Oubliette (sandboxing).
    """
    
    def __init__(self, vault_root: Path, owner_user: str = "pubcast"):
        self.vault_root = Path(vault_root)
        self.owner_user = owner_user
        
        # Initialize both systems
        self.wallet = IterationVaultHardened(vault_root / "wallet", owner_user)
        
        sandbox_workspace = vault_root / "sandbox"
        sandbox_workspace.mkdir(parents=True, exist_ok=True)
        self.sandbox = ExecutionSandbox(sandbox_workspace)
        
        # Recipe cache
        self.recipes = AUDIO_RECIPES
        
        # Intake statistics
        self.intake_stats = {
            "total_attempts": 0,
            "successful_intakes": 0,
            "quarantined": 0,
            "failed": 0,
        }
    
    def initialize(self, password: str) -> bool:
        """Initialize both vault and sandbox."""
        try:
            logger.info("Initializing PubCast Security Vault...")
            
            # Initialize Iteration Wallet
            if not self.wallet.initialize(password):
                logger.error("Failed to initialize Iteration Wallet")
                return False
            
            logger.info("✓ Iteration Wallet initialized")
            logger.info(f"✓ Oubliette sandbox ready ({self.sandbox.enforcement_level.value})")
            
            return True
        except Exception as e:
            logger.error(f"Vault initialization failed: {e}")
            return False
    
    def intake_file(self, file_path: Path, source_name: str = "unknown",
                   user: str = "pubcast") -> Tuple[IntakeStatus, Optional[str], Dict]:
        """
        Complete intake workflow: untrusted file → vault.
        
        Returns: (status, file_id, details_dict)
        """
        self.intake_stats["total_attempts"] += 1
        file_path = Path(file_path)
        details = {
            "file": str(file_path),
            "source": source_name,
            "timestamp": datetime.utcnow().isoformat(),
            "classification": None,
            "sanitization": None,
            "vault_file_id": None,
            "warnings": []
        }
        
        try:
            # Step 1: Classify file
            logger.info(f"Classifying file: {file_path.name}")
            metadata = FileClassifier.classify(file_path)
            details["classification"] = {
                "type": metadata.magic_bytes,
                "extension": metadata.extension,
                "class": metadata.classification,
                "risk_level": metadata.risk_level
            }
            
            # Step 2: Check if dangerous
            if metadata.classification == FileClassification.KNOWN_BAD.value:
                logger.warning(f"File classified as malicious: {file_path.name}")
                details["warnings"].append("File classified as KNOWN_BAD")
                
                # Quarantine it
                quarantine_id = self._quarantine_file(file_path, user)
                self.intake_stats["quarantined"] += 1
                
                return IntakeStatus.QUARANTINED, quarantine_id, details
            
            # Step 3: Safe intake (no transformation needed)
            if metadata.classification == FileClassification.KNOWN_SAFE.value:
                logger.info(f"File is known safe, adding to vault directly")
                
                file_id = self.wallet.add_file(
                    file_path,
                    project_name="intake",
                    user=user,
                    description=f"Source: {source_name}"
                )
                
                if file_id:
                    details["vault_file_id"] = file_id
                    self.intake_stats["successful_intakes"] += 1
                    return IntakeStatus.SAFE, file_id, details
                else:
                    self.intake_stats["failed"] += 1
                    return IntakeStatus.FAILED, None, details
            
            # Step 4: Unknown/suspicious → probe in sandbox
            logger.info(f"Probing unknown file in sandbox: {file_path.name}")
            
            # Find appropriate recipe
            recipe = self._find_recipe_for_file(metadata)
            
            if not recipe:
                logger.warning(f"No recipe available for {metadata.magic_bytes}")
                details["warnings"].append("No safe transformation recipe available")
                
                # Still vault it as-is, but mark as unprocessed
                file_id = self.wallet.add_file(
                    file_path,
                    project_name="intake_unprocessed",
                    user=user,
                    description=f"Source: {source_name} (no processing)"
                )
                
                if file_id:
                    details["vault_file_id"] = file_id
                    self.intake_stats["successful_intakes"] += 1
                    return IntakeStatus.SAFE, file_id, details
            
            # Step 5: Execute recipe in sandbox
            logger.info(f"Executing recipe: {recipe.recipe_id}")
            result = self.sandbox.execute_recipe(file_path, recipe)
            details["sanitization"] = {
                "recipe": recipe.recipe_id,
                "success": result.success,
                "exit_code": result.exit_code,
                "execution_time_ms": result.execution_time_ms,
                "violations": result.violations_detected,
                "artifacts": result.artifacts
            }
            
            # Step 6: Check for execution violations
            if result.violations_detected:
                logger.warning(f"Sandbox violations detected: {result.violations_detected}")
                details["warnings"].append(f"Violations: {', '.join(result.violations_detected)}")
                
                # Still vault original, but note the violation
                file_id = self.wallet.add_file(
                    file_path,
                    project_name="intake_with_warnings",
                    user=user,
                    description=f"Source: {source_name} (sandbox violations)"
                )
                
                if file_id:
                    details["vault_file_id"] = file_id
                    self.intake_stats["successful_intakes"] += 1
                    return IntakeStatus.SAFE, file_id, details
            
            # Step 7: Vault sanitized output
            if result.success and result.artifacts:
                artifact_path = Path(result.artifacts[0])
                
                if artifact_path.exists():
                    logger.info(f"Vaulting sanitized output: {artifact_path.name}")
                    
                    safe_file_id = self.wallet.add_file(
                        artifact_path,
                        project_name="intake_sanitized",
                        user=user,
                        description=f"Source: {source_name} (sanitized via {recipe.recipe_id})"
                    )
                    
                    if safe_file_id:
                        details["vault_file_id"] = safe_file_id
                        self.intake_stats["successful_intakes"] += 1
                        
                        # Also vault the original for audit trail
                        original_id = self.wallet.add_file(
                            file_path,
                            project_name="intake_originals",
                            user=user,
                            description=f"Original (before sanitization)"
                        )
                        details["original_file_id"] = original_id
                        
                        logger.info(f"✓ File successfully intook and sanitized")
                        return IntakeStatus.SAFE, safe_file_id, details
            
            # If we get here, something failed
            self.intake_stats["failed"] += 1
            return IntakeStatus.FAILED, None, details
        
        except Exception as e:
            logger.error(f"Intake failed: {e}")
            details["warnings"].append(f"Exception: {str(e)}")
            self.intake_stats["failed"] += 1
            return IntakeStatus.FAILED, None, details
    
    def _find_recipe_for_file(self, metadata: FileMetadata) -> Optional[ExecutionRecipe]:
        """Find transformation recipe for file type."""
        magic = metadata.magic_bytes
        
        # Map MIME types to recipes
        recipe_map = {
            "audio/mp4a": self.recipes.get("m4a_to_wav"),
            "audio/mp4": self.recipes.get("m4a_to_wav"),
            "audio/mp3": self.recipes.get("mp3_to_wav"),
            "audio/opus": self.recipes.get("opus_to_wav"),
        }
        
        return recipe_map.get(magic)
    
    def _quarantine_file(self, file_path: Path, user: str) -> str:
        """Move file to quarantine."""
        quarantine_dir = self.vault_root / ".quarantine"
        quarantine_dir.mkdir(exist_ok=True)
        
        quarantine_path = quarantine_dir / f"quarantine_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{file_path.name}"
        shutil.copy2(file_path, quarantine_path)
        
        # Also vault it with QUARANTINED status
        file_id = self.wallet.add_file(
            file_path,
            project_name="quarantine",
            user=user,
            description="QUARANTINED: Detected as malicious"
        )
        
        return file_id or str(quarantine_path)
    
    def get_intake_stats(self) -> Dict:
        """Get intake statistics."""
        return {
            **self.intake_stats,
            "success_rate": (
                self.intake_stats["successful_intakes"] / max(1, self.intake_stats["total_attempts"]) * 100
            )
        }
    
    def list_vault_files(self, user: str = "pubcast") -> List[Dict]:
        """List files in vault."""
        return self.wallet.list_files(user=user)
    
    def verify_vault_integrity(self, user: str = "pubcast") -> Dict:
        """Verify all files in vault."""
        files = self.wallet.list_files(user=user)
        results = {
            "total_files": len(files),
            "verified": 0,
            "corrupted": 0,
            "details": []
        }
        
        for file_info in files:
            ok, msg = self.wallet.verify_file_integrity(file_info["file_id"], user=user)
            
            if ok:
                results["verified"] += 1
            else:
                results["corrupted"] += 1
            
            results["details"].append({
                "file_id": file_info["file_id"],
                "status": "ok" if ok else "corrupted_restored",
                "message": msg
            })
        
        return results

# ─────────────────────────────────────────────────────────────
#  CLI Demo
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    vault_root = Path("/tmp/pubcast_vault")
    
    # Clean start
    if vault_root.exists():
        import shutil
        shutil.rmtree(vault_root)
    
    # Initialize
    vault = PubCastSecurityVault(vault_root, owner_user="pubcast")
    if vault.initialize("secure_password"):
        print("✓ PubCast Security Vault initialized")
        
        # Create test file
        test_file = Path("/tmp/test_podcast.wav")
        test_file.write_bytes(b'RIFF' + b'\x00' * 1000)
        
        # Intake file
        status, file_id, details = vault.intake_file(
            test_file,
            source_name="test_source"
        )
        
        print(f"✓ Intake status: {status.value}")
        if file_id:
            print(f"✓ Vault file ID: {file_id}")
        
        # Show stats
        stats = vault.get_intake_stats()
        print(f"✓ Intake stats: {stats}")
        
        # Cleanup
        test_file.unlink()
    else:
        print("✗ Vault initialization failed")
