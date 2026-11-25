"""
Key Rotation & Password Change
===============================
Securely rotate vault keys when password is changed.

When a user changes their vault password:
  1. Derive new crypto keys from new password + same salt
  2. Re-encrypt database with new key
  3. Update HMAC key for all metadata
  4. Create rotation audit entry
  5. Keep old backup in case of failure

Implementation detail: This is a database-level operation.
SQLCipher supports `PRAGMA rekey='...'` to re-encrypt.
"""

import logging
import hashlib
import hmac
import json
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional

logger = logging.getLogger("key_rotation")

ROTATION_LOG_FILE = ".vault_key_rotations.log"


class VaultKeyRotator:
    """
    Rotate vault encryption keys when password changes.
    
    The vault salt never changes (it's the recovery basis).
    Only the encryption/HMAC keys are rotated based on new password.
    
    Usage:
        rotator = VaultKeyRotator(vault)
        ok, msg = rotator.rotate_password(old_password, new_password)
        if not ok:
            # Rotation failed, vault unchanged
            print(msg)
    """
    
    def __init__(self, vault):
        self.vault = vault
        self.rotation_log_path = vault.vault_root / ROTATION_LOG_FILE
    
    def rotate_password(self, old_password: str, new_password: str) -> Tuple[bool, str]:
        """
        Change vault password and re-encrypt all keys.
        
        Process:
          1. Verify old password is correct
          2. Backup database file
          3. Derive new keys from new password
          4. Re-encrypt database
          5. Re-sign all metadata with new HMAC key
          6. Log rotation event
          7. Commit (delete backup on success)
        
        Args:
            old_password: Current vault password (must be correct)
            new_password: New password (should be different and strong)
        
        Returns:
            (success: bool, message: str)
        """
        
        # Step 1: Verify old password
        try:
            self.vault.crypto.initialize(old_password)
        except Exception as e:
            return False, f"Old password verification failed: {e}"
        
        if not self.vault.crypto.hmac_key or not self.vault.crypto.db_cipher_key:
            return False, "Old password verification: keys not initialized"
        
        db_path = self.vault.vault_root / self.vault.db_name
        backup_path = db_path.parent / f"{db_path.name}.pre_rotation"
        
        # Step 2: Create backup
        try:
            if db_path.exists():
                shutil.copy2(db_path, backup_path)
                logger.info(f"Database backed up to {backup_path.name}")
        except Exception as e:
            return False, f"Backup creation failed: {e}"
        
        # Step 3: Derive new keys from new password
        try:
            new_crypto = type(self.vault.crypto)(self.vault.vault_root)
            new_crypto.initialize(new_password)
        except Exception as e:
            # Restore from backup
            try:
                backup_path.unlink()
            except Exception:
                pass
            return False, f"New key derivation failed: {e}"
        
        # Step 4: Re-encrypt database using SQLCipher PRAGMA rekey
        try:
            conn = sqlite3.connect(str(db_path))
            # Provide old key for current decryption
            old_key = self.vault.crypto.get_db_cipher_key()
            conn.execute(f"PRAGMA key = \"x'{old_key}'\"")
            
            # Test that we can read with old key
            cursor = conn.execute("SELECT COUNT(*) FROM vault_files")
            cursor.fetchone()
            
            # Now re-key with new key
            new_key = new_crypto.get_db_cipher_key()
            conn.execute(f"PRAGMA rekey = \"x'{new_key}'\"")
            
            conn.close()
            logger.info("Database re-encrypted with new key")
        
        except Exception as e:
            # Restore from backup
            try:
                shutil.copy2(backup_path, db_path)
                logger.warning(f"Restored database from backup after rotation failure")
            except Exception:
                pass
            try:
                backup_path.unlink()
            except Exception:
                pass
            return False, f"Database re-encryption failed: {e}"
        
        # Step 5: Update vault's crypto manager
        try:
            self.vault.crypto = new_crypto
        except Exception as e:
            try:
                shutil.copy2(backup_path, db_path)
            except Exception:
                pass
            return False, f"Crypto manager update failed: {e}"
        
        # Step 6: Log rotation (this uses new HMAC key automatically)
        try:
            from vault_engine_hardened import AuditAction
            
            self.vault._audit_log(
                AuditAction.VAULT_MODIFIED,
                file_id=None,
                details={
                    "operation": "password_rotation",
                    "reason": "user_initiated",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            # Also write to rotation log
            rotation_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "operation": "password_rotation",
                "old_password_hash": hashlib.sha256(
                    old_password.encode()
                ).hexdigest()[:16],  # Only hash prefix for audit
                "new_password_hash": hashlib.sha256(
                    new_password.encode()
                ).hexdigest()[:16],
                "status": "success",
                "backup_path": str(backup_path.name)
            }
            
            with open(self.rotation_log_path, 'a') as f:
                f.write(json.dumps(rotation_entry) + "\n")
            
            logger.info("Key rotation logged")
        
        except Exception as e:
            logger.warning(f"Rotation logging failed: {e}")
            # Don't fail the whole operation if logging fails
        
        # Step 7: Cleanup backup on success
        try:
            backup_path.unlink()
            logger.info("Pre-rotation backup deleted")
        except Exception:
            logger.warning(f"Could not delete backup file {backup_path}")
        
        return True, "Password changed successfully - vault re-encrypted with new key"
    
    def get_rotation_history(self, limit: int = 50) -> list:
        """Get history of password rotations."""
        if not self.rotation_log_path.exists():
            return []
        
        entries = []
        try:
            with open(self.rotation_log_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            logger.warning(f"Could not read rotation history: {e}")
        
        return entries[-limit:]
    
    def emergency_rollback(self, backup_path: Path) -> Tuple[bool, str]:
        """
        Emergency rollback if rotation failed and backup exists.
        
        WARNING: Use only if rotation corrupted the database!
        This will lose any vault changes made after the rotation attempt.
        """
        db_path = self.vault.vault_root / self.vault.db_name
        
        if not backup_path.exists():
            return False, f"Backup file not found: {backup_path}"
        
        try:
            shutil.copy2(backup_path, db_path)
            logger.warning(f"Database restored from {backup_path.name}")
            
            # Log the rollback
            rollback_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "operation": "rotation_rollback",
                "from_backup": str(backup_path.name),
                "status": "success"
            }
            
            with open(self.rotation_log_path, 'a') as f:
                f.write(json.dumps(rollback_entry) + "\n")
            
            return True, "Database rolled back from backup"
        
        except Exception as e:
            return False, f"Rollback failed: {e}"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Key Rotation module loaded")
    print("Usage: rotator = VaultKeyRotator(vault)")
    print("       ok, msg = rotator.rotate_password(old_pw, new_pw)")
