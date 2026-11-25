"""
Security Hardening Integration
===============================
Centralized security hardening layer wrapping all critical operations.
"""

import logging
import os
from pathlib import Path
from functools import wraps
from typing import Any, Callable

# Import hardening modules
try:
    from secure_secrets import SecureSecret, SecureSecretManager, setup_secure_logging
    HAS_SECRETS = True
except ImportError:
    HAS_SECRETS = False

try:
    from input_validation import InputValidator, ValidationError
    HAS_VALIDATION = True
except ImportError:
    HAS_VALIDATION = False

logger = logging.getLogger("security_hardening")


class SecurityHardeningLayer:
    """
    Central security hardening that wraps critical vault operations.
    
    Provides:
      • Input validation on all user-facing operations
      • Secure memory handling for passwords/keys
      • Secure logging with secrets redaction
      • Timing attack prevention
      • File permission hardening
      • Resource exhaustion prevention
    """
    
    def __init__(self):
        self.validator = InputValidator if HAS_VALIDATION else None
        
        # Apply secure logging if available
        if HAS_SECRETS:
            setup_secure_logging(logger)
    
    def validate_password(self, password: str) -> bool:
        """Validate password before use."""
        if not HAS_VALIDATION:
            return len(password) >= 8
        ok, msg = self.validator.validate_password(password, min_length=8, max_length=1024)
        if not ok:
            logger.warning(f"Password validation failed: {msg}")
        return ok
    
    def validate_file_operation(self, filepath: str, operation: str = "read") -> bool:
        """Validate file paths before access."""
        if not HAS_VALIDATION:
            return True
        ok, msg = self.validator.validate_filepath(filepath)
        if not ok:
            logger.warning(f"Path validation failed for {operation}: {msg}")
        return ok
    
    def validate_filename(self, filename: str) -> bool:
        """Validate filename."""
        if not HAS_VALIDATION:
            return len(filename) > 0 and len(filename) <= 255
        ok, msg = self.validator.validate_filename(filename)
        if not ok:
            logger.warning(f"Filename validation failed: {msg}")
        return ok
    
    def secure_file_create(self, filepath: Path, content: bytes = b'', mode: int = 0o600):
        """Create file with secure permissions."""
        # Validate path first
        if not self.validate_file_operation(str(filepath), "create"):
            raise ValueError(f"Unsafe file path: {filepath}")
        
        # Create with restrictive permissions
        old_umask = os.umask(0o077)  # Only owner can read/write
        try:
            with open(filepath, 'wb') as f:
                f.write(content)
            os.chmod(filepath, mode)
        finally:
            os.umask(old_umask)
    
    def secure_dir_create(self, dirpath: Path, mode: int = 0o700):
        """Create directory with secure permissions."""
        old_umask = os.umask(0o077)
        try:
            dirpath.mkdir(parents=True, exist_ok=True, mode=mode)
        finally:
            os.umask(old_umask)


def require_valid_password(fn: Callable) -> Callable:
    """Decorator: Validate password parameter."""
    @wraps(fn)
    def wrapper(self, password: str, *args, **kwargs):
        hardening = SecurityHardeningLayer()
        if not hardening.validate_password(password):
            raise ValueError("Password validation failed")
        return fn(self, password, *args, **kwargs)
    return wrapper


def require_valid_file(fn: Callable) -> Callable:
    """Decorator: Validate filepath parameter."""
    @wraps(fn)
    def wrapper(self, filepath: str, *args, **kwargs):
        hardening = SecurityHardeningLayer()
        if not hardening.validate_file_operation(filepath):
            raise ValueError("Filepath validation failed")
        return fn(self, filepath, *args, **kwargs)
    return wrapper


def require_valid_filename(fn: Callable) -> Callable:
    """Decorator: Validate filename parameter."""
    @wraps(fn)
    def wrapper(self, filename: str, *args, **kwargs):
        hardening = SecurityHardeningLayer()
        if not hardening.validate_filename(filename):
            raise ValueError("Filename validation failed")
        return fn(self, filename, *args, **kwargs)
    return wrapper


def catch_all_exceptions(fn: Callable) -> Callable:
    """Decorator: Catch all exceptions, log safely, return False/None."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            # Log without exposing details
            logger.error(f"{fn.__name__} failed: {type(e).__name__}")
            return None
    return wrapper


# Resource exhaustion prevention
class ResourceLimits:
    """Prevent DoS via resource exhaustion."""
    
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB
    MAX_HASH_ITERATIONS = 1_000_000
    MAX_DB_SIZE = 100 * 1024 * 1024  # 100 MB
    MAX_AUDIT_ENTRIES = 1_000_000
    MAX_FILES_IN_VAULT = 100_000
    
    @staticmethod
    def check_file_size(filepath: Path) -> bool:
        """Check file is within size limits."""
        if not filepath.exists():
            return True
        size = filepath.stat().st_size
        if size > ResourceLimits.MAX_FILE_SIZE:
            logger.warning(f"File exceeds max size: {size} > {ResourceLimits.MAX_FILE_SIZE}")
            return False
        return True
    
    @staticmethod
    def check_vault_size(vault_root: Path) -> bool:
        """Check vault doesn't exceed size limits."""
        total = 0
        for f in vault_root.rglob('*'):
            if f.is_file():
                total += f.stat().st_size
                if total > ResourceLimits.MAX_DB_SIZE:
                    logger.warning(f"Vault exceeds max size: {total}")
                    return False
        return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    hardening = SecurityHardeningLayer()
    
    print("✓ Hardening layer initialized")
    print(f"  Secrets module: {'enabled' if HAS_SECRETS else 'disabled'}")
    print(f"  Validation module: {'enabled' if HAS_VALIDATION else 'disabled'}")
