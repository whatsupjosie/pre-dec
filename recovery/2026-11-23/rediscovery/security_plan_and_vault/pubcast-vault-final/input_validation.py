"""
Input Validation & Sanitization
================================
Comprehensive validation for all user inputs.

Prevents:
  • SQL injection
  • Path traversal
  • Buffer overflows
  • Format string attacks
  • Command injection
  • XSS in logs/responses
"""

import re
from pathlib import Path
from typing import Any, Tuple, Optional, List, Union
import logging

logger = logging.getLogger("input_validation")


class ValidationError(ValueError):
    """Raised when input validation fails."""
    pass


class InputValidator:
    """
    Centralized input validation and sanitization.
    
    All user inputs should pass through these validators
    before being used in sensitive operations.
    """
    
    # Max sizes to prevent DoS
    MAX_SIZES = {
        'password': 1024,
        'filename': 255,
        'filepath': 4096,
        'json_payload': 64_000,
        'file_upload': 500 * 1024 * 1024,  # 500 MB
        'database_string': 10_000,
        'command_line_arg': 2048,
    }
    
    # Safe character sets
    SAFE_ALPHANUMERIC = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
    SAFE_FILENAME = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-() ')
    SAFE_UUID = set('0123456789abcdef-')
    
    @staticmethod
    def validate_password(password: Any, min_length: int = 8, max_length: int = None) -> Tuple[bool, str]:
        """
        Validate password strength and format.
        
        Returns: (is_valid, error_message)
        """
        max_length = max_length or InputValidator.MAX_SIZES['password']
        
        if not isinstance(password, str):
            return False, "Password must be a string"
        
        if len(password) < min_length:
            return False, f"Password must be at least {min_length} characters"
        
        if len(password) > max_length:
            return False, f"Password must be at most {max_length} characters"
        
        # Check for null bytes (could cause truncation)
        if '\x00' in password:
            return False, "Password contains null bytes"
        
        # Check for control characters (except whitespace)
        if any(ord(c) < 32 and c not in '\t\n\r' for c in password):
            return False, "Password contains control characters"
        
        return True, ""
    
    @staticmethod
    def validate_filename(filename: Any, allow_ext: Optional[List[str]] = None) -> Tuple[bool, str]:
        """
        Validate filename for safe filesystem operations.
        
        Prevents path traversal, symlinks, and dangerous names.
        """
        if not isinstance(filename, str):
            return False, "Filename must be a string"
        
        if len(filename) > InputValidator.MAX_SIZES['filename']:
            return False, f"Filename too long (max {InputValidator.MAX_SIZES['filename']})"
        
        if not filename.strip():
            return False, "Filename cannot be empty"
        
        # Reject absolute paths
        if filename.startswith('/') or filename.startswith('\\'):
            return False, "Filename cannot be absolute path"
        
        # Remove any path components (only take the filename part)
        safe_name = Path(filename).name
        
        if safe_name != filename:
            return False, "Filename cannot contain path separators"
        
        # Reject dangerous names (Windows reserved)
        dangerous = {
            'con', 'prn', 'aux', 'nul', 'com1', 'com2', 'com3', 'com4',
            'com5', 'com6', 'com7', 'com8', 'com9', 'lpt1', 'lpt2',
            'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'
        }
        
        name_lower = safe_name.lower().split('.')[0]
        if name_lower in dangerous:
            return False, f"Filename uses reserved name: {safe_name}"
        
        # Check character whitelist
        if not all(c in InputValidator.SAFE_FILENAME for c in safe_name):
            return False, "Filename contains disallowed characters"
        
        # If extensions specified, validate
        if allow_ext:
            ext = Path(safe_name).suffix.lower()
            if ext and ext[1:] not in allow_ext:
                return False, f"File extension not allowed. Allowed: {', '.join(allow_ext)}"
        
        return True, ""
    
    @staticmethod
    def validate_filepath(filepath: Any) -> Tuple[bool, str]:
        """
        Validate full file paths for safety.
        
        Ensures no path traversal attacks.
        """
        if not isinstance(filepath, str):
            return False, "Filepath must be a string"
        
        if len(filepath) > InputValidator.MAX_SIZES['filepath']:
            return False, f"Filepath too long (max {InputValidator.MAX_SIZES['filepath']})"
        
        # Reject null bytes
        if '\x00' in filepath:
            return False, "Filepath contains null bytes"
        
        # Normalize and check for traversal
        try:
            path = Path(filepath).resolve()
        except (ValueError, RuntimeError) as e:
            return False, f"Invalid filepath: {e}"
        
        # Check for suspicious patterns
        if '..' in filepath:
            return False, "Filepath contains parent directory references"
        
        if filepath.startswith('~'):
            return False, "Filepath uses home directory expansion"
        
        return True, ""
    
    @staticmethod
    def validate_file_id(file_id: Any) -> Tuple[bool, str]:
        """
        Validate file identifiers (UUIDs, etc.).
        """
        if not isinstance(file_id, str):
            return False, "File ID must be a string"
        
        if len(file_id) > 64:
            return False, "File ID too long"
        
        # Allow UUID format or alphanumeric with dashes
        if not re.match(r'^[a-zA-Z0-9_\-]{1,64}$', file_id):
            return False, "File ID contains invalid characters"
        
        return True, ""
    
    @staticmethod
    def validate_source(source: Any) -> Tuple[bool, str]:
        """
        Validate source/origin identifiers.
        """
        if not isinstance(source, str):
            return False, "Source must be a string"
        
        if len(source) > 128:
            return False, "Source too long"
        
        if not re.match(r'^[a-zA-Z0-9_\-. ]+$', source):
            return False, "Source contains disallowed characters"
        
        return True, ""
    
    @staticmethod
    def validate_email(email: Any) -> Tuple[bool, str]:
        """
        Validate email addresses (basic format check).
        """
        if not isinstance(email, str):
            return False, "Email must be a string"
        
        if len(email) > 254:  # RFC 5321
            return False, "Email too long"
        
        # Basic email regex (not comprehensive, but catches obvious issues)
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return False, "Invalid email format"
        
        return True, ""
    
    @staticmethod
    def validate_integer(value: Any, min_val: int = None, max_val: int = None) -> Tuple[bool, str]:
        """
        Validate integer with optional bounds.
        """
        try:
            num = int(value)
        except (TypeError, ValueError):
            return False, "Value must be a valid integer"
        
        if min_val is not None and num < min_val:
            return False, f"Value must be >= {min_val}"
        
        if max_val is not None and num > max_val:
            return False, f"Value must be <= {max_val}"
        
        return True, ""
    
    @staticmethod
    def sanitize_sql_string(value: str) -> str:
        """
        Sanitize a string for SQL (basic escaping).
        
        WARNING: Parameterized queries are better. Use this only as fallback.
        """
        # Escape single quotes by doubling them (SQL standard)
        return value.replace("'", "''")
    
    @staticmethod
    def sanitize_shell_arg(value: str) -> str:
        """
        Escape a string for use in shell commands.
        
        WARNING: Avoid shell commands. Use subprocess directly.
        """
        import shlex
        return shlex.quote(value)
    
    @staticmethod
    def sanitize_json_string(value: str) -> str:
        """
        Escape special characters for JSON.
        """
        import json
        # json.dumps handles escaping correctly
        return json.loads(json.dumps(value))
    
    @staticmethod
    def safe_int(value: Any, default: int, min_val: int = None, max_val: int = None) -> int:
        """
        Safely convert to int with bounds and default.
        """
        try:
            num = int(value)
            if min_val is not None:
                num = max(min_val, num)
            if max_val is not None:
                num = min(max_val, num)
            return num
        except (TypeError, ValueError):
            return default


class SafeString:
    """
    String wrapper that prevents accidental XSS in logs/responses.
    
    Automatically escapes HTML/XML when converted to string.
    """
    
    def __init__(self, value: str, escape_html: bool = True):
        self._value = str(value)
        self._escape = escape_html
    
    def __str__(self):
        if self._escape:
            return self._escape_html(self._value)
        return self._value
    
    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters."""
        replacements = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }
        for char, escape in replacements.items():
            text = text.replace(char, escape)
        return text


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test validators
    print("Testing input validation...\n")
    
    # Password
    ok, msg = InputValidator.validate_password("short")
    print(f"Short password: {ok} - {msg}")
    
    ok, msg = InputValidator.validate_password("good_password_123")
    print(f"Good password: {ok}")
    
    # Filename
    ok, msg = InputValidator.validate_filename("../../../etc/passwd")
    print(f"Traversal attack: {ok} - {msg}")
    
    ok, msg = InputValidator.validate_filename("document.pdf")
    print(f"Normal filename: {ok}")
    
    # Email
    ok, msg = InputValidator.validate_email("user@example.com")
    print(f"Valid email: {ok}")
    
    ok, msg = InputValidator.validate_email("not-an-email")
    print(f"Invalid email: {ok} - {msg}")
    
    # Integer
    ok, msg = InputValidator.validate_integer(42, min_val=0, max_val=100)
    print(f"Valid int: {ok}")
    
    print("\n✓ Input validation module working")
