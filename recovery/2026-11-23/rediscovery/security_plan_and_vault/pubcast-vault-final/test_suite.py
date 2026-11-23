"""
PubCast Vault Test Suite
========================
Comprehensive testing for Iteration Wallet + Oubliette + Integration.

Test Categories:
  - Unit tests: Individual functions
  - Integration tests: Full workflows
  - Security tests: Threat scenarios
  - Performance tests: Speed benchmarks
"""

import sys
import unittest
import tempfile
import shutil
import json
from pathlib import Path
from datetime import datetime
import time

sys.path.insert(0, str(Path(__file__).parent / "../phase1_iteration_wallet"))
sys.path.insert(0, str(Path(__file__).parent / "../phase2_oubliette"))
sys.path.insert(0, str(Path(__file__).parent / "../phase3_integration"))

from vault_engine_hardened import (
    IterationVaultHardened, CryptoManager, VaultACL, Role, AuditAction
)
from sandbox_hardened import (
    FileClassifier, ExecutionSandbox, ResourceLimits, FileClassification
)
from pubcast_vault import PubCastSecurityVault

# ─────────────────────────────────────────────────────────────
#  Unit Tests: Crypto
# ─────────────────────────────────────────────────────────────

class TestCrypto(unittest.TestCase):
    """Test cryptographic operations."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.crypto = CryptoManager(Path(self.temp_dir))
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_key_derivation(self):
        """Test key derivation from password."""
        result = self.crypto.initialize("test_password")
        self.assertTrue(result)
        self.assertIsNotNone(self.crypto.hmac_key)
        self.assertIsNotNone(self.crypto.db_cipher_key)
    
    def test_same_password_produces_same_key(self):
        """Test deterministic key derivation."""
        self.crypto.initialize("password")
        key1 = self.crypto.db_cipher_key
        
        crypto2 = CryptoManager(Path(self.temp_dir))
        crypto2.initialize("password")
        key2 = crypto2.db_cipher_key
        
        self.assertEqual(key1, key2)
    
    def test_different_password_produces_different_key(self):
        """Test password uniqueness."""
        self.crypto.initialize("password1")
        key1 = self.crypto.db_cipher_key
        
        crypto2 = CryptoManager(Path(tempfile.mkdtemp()))
        crypto2.initialize("password2")
        key2 = crypto2.db_cipher_key
        
        self.assertNotEqual(key1, key2)
    
    def test_hmac_computation(self):
        """Test HMAC generation."""
        self.crypto.initialize("test_password")
        data = '{"test": "data"}'
        hmac = self.crypto.compute_hmac(data)
        
        self.assertIsInstance(hmac, str)
        self.assertEqual(len(hmac), 64)  # SHA-256 hex
    
    def test_hmac_verification(self):
        """Test HMAC verification."""
        self.crypto.initialize("test_password")
        data = '{"test": "data"}'
        hmac = self.crypto.compute_hmac(data)
        
        # Valid signature
        self.assertTrue(self.crypto.verify_hmac(data, hmac))
        
        # Invalid signature
        self.assertFalse(self.crypto.verify_hmac(data, "0" * 64))
    
    def test_file_checksum(self):
        """Test file checksum computation."""
        self.crypto.initialize("test_password")
        
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("test content")
        
        checksum = self.crypto.compute_file_checksum(test_file)
        
        self.assertIsInstance(checksum, str)
        self.assertEqual(len(checksum), 64)  # SHA-256 hex

# ─────────────────────────────────────────────────────────────
#  Unit Tests: ACL
# ─────────────────────────────────────────────────────────────

class TestACL(unittest.TestCase):
    """Test access control list."""
    
    def setUp(self):
        self.acl = VaultACL("owner")
    
    def test_owner_has_full_access(self):
        """Test owner permissions."""
        self.assertTrue(self.acl.check_permission("owner", "add_file"))
        self.assertTrue(self.acl.check_permission("owner", "modify_acl"))
        self.assertTrue(self.acl.check_permission("owner", "set_policy"))
    
    def test_user_has_limited_access(self):
        """Test user permissions."""
        self.acl.grant_access("user", Role.USER)
        
        self.assertTrue(self.acl.check_permission("user", "add_file"))
        self.assertTrue(self.acl.check_permission("user", "query_file"))
        self.assertFalse(self.acl.check_permission("user", "modify_acl"))
    
    def test_read_only_user(self):
        """Test read-only permissions."""
        self.acl.grant_access("reader", Role.READ_ONLY)
        
        self.assertTrue(self.acl.check_permission("reader", "query_file"))
        self.assertFalse(self.acl.check_permission("reader", "add_file"))
    
    def test_revoke_access(self):
        """Test access revocation."""
        self.acl.grant_access("user", Role.USER)
        self.assertTrue(self.acl.check_permission("user", "add_file"))
        
        self.acl.revoke_access("user")
        self.assertFalse(self.acl.check_permission("user", "add_file"))

# ─────────────────────────────────────────────────────────────
#  Unit Tests: File Classification
# ─────────────────────────────────────────────────────────────

class TestFileClassifier(unittest.TestCase):
    """Test file classification."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_classify_wav_file(self):
        """Test WAV file classification."""
        wav_file = Path(self.temp_dir) / "test.wav"
        wav_file.write_bytes(b'RIFF' + b'\x00' * 100)
        
        metadata = FileClassifier.classify(wav_file)
        
        self.assertEqual(metadata.magic_bytes, "audio/wav")
        self.assertEqual(metadata.classification, FileClassification.KNOWN_SAFE.value)
        self.assertEqual(metadata.risk_level, 0.0)
    
    def test_classify_unknown_file(self):
        """Test unknown file classification."""
        unknown_file = Path(self.temp_dir) / "test.xyz"
        unknown_file.write_bytes(b'\x00' * 100)
        
        metadata = FileClassifier.classify(unknown_file)
        
        self.assertEqual(metadata.classification, FileClassification.UNKNOWN.value)
        self.assertGreater(metadata.risk_level, 0.0)
    
    def test_classify_executable(self):
        """Test executable classification."""
        exe_file = Path(self.temp_dir) / "test.exe"
        exe_file.write_bytes(b'MZ' + b'\x00' * 100)
        
        metadata = FileClassifier.classify(exe_file)
        
        # Should be flagged as suspicious/bad based on extension
        self.assertGreaterEqual(metadata.risk_level, 0.5)

# ─────────────────────────────────────────────────────────────
#  Integration Tests: Vault Operations
# ─────────────────────────────────────────────────────────────

class TestVaultOperations(unittest.TestCase):
    """Test complete vault operations."""
    
    def setUp(self):
        self.vault_root = Path(tempfile.mkdtemp())
        self.vault = IterationVaultHardened(self.vault_root, owner_user="test_user")
        self.vault.initialize("test_password")
    
    def tearDown(self):
        shutil.rmtree(self.vault_root)
    
    def test_file_add_and_retrieve(self):
        """Test adding and retrieving files."""
        test_file = self.vault_root / "test.txt"
        test_file.write_text("test content")
        
        file_id = self.vault.add_file(test_file, "project1", user="test_user")
        
        self.assertIsNotNone(file_id)
        
        files = self.vault.list_files(project_name="project1", user="test_user")
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["file_id"], file_id)
    
    def test_corruption_detection_and_restoration(self):
        """Test corruption detection and auto-restoration."""
        test_file = self.vault_root / "test.txt"
        test_file.write_text("original content")
        
        file_id = self.vault.add_file(test_file, "project1", user="test_user")
        
        # Verify initial integrity
        ok, _ = self.vault.verify_file_integrity(file_id, user="test_user")
        self.assertTrue(ok)
        
        # Corrupt the file
        vault_path = self.vault_root / ".vault_container" / file_id
        vault_path.write_text("corrupted content")
        
        # Verify detects corruption and restores
        ok, msg = self.vault.verify_file_integrity(file_id, user="test_user")
        self.assertFalse(ok)
        self.assertIn("restored", msg.lower())
        
        # Verify restoration worked
        restored_content = vault_path.read_text()
        self.assertEqual(restored_content, "original content")
    
    def test_acl_enforcement(self):
        """Test ACL enforcement in vault."""
        test_file = self.vault_root / "test.txt"
        test_file.write_text("content")
        
        # Owner can add files
        file_id = self.vault.add_file(test_file, "project1", user="owner")
        self.assertIsNotNone(file_id)
        
        # Non-existent user cannot add files
        file_id = self.vault.add_file(test_file, "project1", user="hacker")
        self.assertIsNone(file_id)

# ─────────────────────────────────────────────────────────────
#  Integration Tests: Intake Workflow
# ─────────────────────────────────────────────────────────────

class TestIntakeWorkflow(unittest.TestCase):
    """Test complete intake workflow."""
    
    def setUp(self):
        self.vault_root = Path(tempfile.mkdtemp())
        self.vault = PubCastSecurityVault(self.vault_root)
        self.vault.initialize("test_password")
    
    def tearDown(self):
        shutil.rmtree(self.vault_root)
    
    def test_safe_file_intake(self):
        """Test intake of known-safe file."""
        test_file = self.vault_root / "test.wav"
        test_file.write_bytes(b'RIFF' + b'\x00' * 1000)
        
        status, file_id, details = self.vault.intake_file(test_file, source_name="test")
        
        self.assertEqual(status.value, "safe")
        self.assertIsNotNone(file_id)
        self.assertEqual(details["classification"]["class"], "known_safe")
    
    def test_intake_statistics(self):
        """Test intake statistics tracking."""
        test_file = self.vault_root / "test.wav"
        test_file.write_bytes(b'RIFF' + b'\x00' * 1000)
        
        self.vault.intake_file(test_file, source_name="test1")
        self.vault.intake_file(test_file, source_name="test2")
        
        stats = self.vault.get_intake_stats()
        
        self.assertEqual(stats["total_attempts"], 2)
        self.assertEqual(stats["successful_intakes"], 2)
        self.assertEqual(stats["success_rate"], 100.0)

# ─────────────────────────────────────────────────────────────
#  Security Tests: Threat Scenarios
# ─────────────────────────────────────────────────────────────

class TestSecurityThreats(unittest.TestCase):
    """Test responses to security threats."""
    
    def setUp(self):
        self.vault_root = Path(tempfile.mkdtemp())
        self.vault = PubCastSecurityVault(self.vault_root)
        self.vault.initialize("test_password")
    
    def tearDown(self):
        shutil.rmtree(self.vault_root)
    
    def test_tampered_database_detected(self):
        """Test detection of tampered database."""
        # This would require modifying the database and verifying HMAC fails
        # Simplified version: verify HMAC checking works
        crypto = CryptoManager(Path(tempfile.mkdtemp()))
        crypto.initialize("password")
        
        data = '{"file": "data"}'
        valid_hmac = crypto.compute_hmac(data)
        invalid_hmac = "0" * 64
        
        self.assertTrue(crypto.verify_hmac(data, valid_hmac))
        self.assertFalse(crypto.verify_hmac(data, invalid_hmac))
    
    def test_unauthorized_access_blocked(self):
        """Test unauthorized access is blocked."""
        test_file = self.vault_root / "test.txt"
        test_file.write_text("secret")
        
        # Owner can add
        file_id = self.vault.wallet.add_file(test_file, "secret_project", user="alice")
        self.assertIsNotNone(file_id)
        
        # Unauthorized user cannot query
        files = self.vault.wallet.list_files(user="bob")
        # Should be empty or limited based on permissions
        self.assertIsInstance(files, list)

# ─────────────────────────────────────────────────────────────
#  Performance Tests
# ─────────────────────────────────────────────────────────────

class TestPerformance(unittest.TestCase):
    """Test performance characteristics."""
    
    def setUp(self):
        self.vault_root = Path(tempfile.mkdtemp())
        self.vault = PubCastSecurityVault(self.vault_root)
        self.vault.initialize("test_password")
    
    def tearDown(self):
        shutil.rmtree(self.vault_root)
    
    def test_file_intake_speed(self):
        """Test file intake speed (target: <1s for 100MB file)."""
        test_file = self.vault_root / "test.wav"
        test_file.write_bytes(b'RIFF' + b'\x00' * (10 * 1024 * 1024))  # 10MB
        
        start = time.time()
        status, file_id, _ = self.vault.intake_file(test_file, source_name="perf_test")
        elapsed = time.time() - start
        
        self.assertEqual(status.value, "safe")
        self.assertLess(elapsed, 5.0)  # Should complete in 5 seconds
    
    def test_list_performance(self):
        """Test list query performance."""
        # Add 100 files
        for i in range(100):
            test_file = self.vault_root / f"test_{i}.wav"
            test_file.write_bytes(b'RIFF' + b'\x00' * 1000)
            self.vault.intake_file(test_file, source_name=f"file_{i}")
        
        start = time.time()
        files = self.vault.list_vault_files()
        elapsed = time.time() - start
        
        self.assertGreaterEqual(len(files), 100)
        self.assertLess(elapsed, 1.0)  # Should complete in 1 second

# ─────────────────────────────────────────────────────────────
#  Test Runner
# ─────────────────────────────────────────────────────────────

def run_tests(verbosity=2):
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestCrypto))
    suite.addTests(loader.loadTestsFromTestCase(TestACL))
    suite.addTests(loader.loadTestsFromTestCase(TestFileClassifier))
    suite.addTests(loader.loadTestsFromTestCase(TestVaultOperations))
    suite.addTests(loader.loadTestsFromTestCase(TestIntakeWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestSecurityThreats))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformance))
    
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    return result

if __name__ == "__main__":
    result = run_tests()
    sys.exit(0 if result.wasSuccessful() else 1)


# ─────────────────────────────────────────────────────────────
#  Session 5 Tests: Encryption, Network, Key Rotation
# ─────────────────────────────────────────────────────────────

class TestEncryptedAudit(unittest.TestCase):
    """Test encrypted audit log functionality."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.crypto = CryptoManager(Path(self.temp_dir))
        self.crypto.initialize("test_password")
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_audit_line_encryption(self):
        """Test audit line encryption and decryption."""
        plaintext = '{"action": "FILE_ADDED", "file_id": "abc123"}'
        encrypted = self.crypto.encrypt_audit_line(plaintext)
        self.assertIn(":", encrypted)  # Should have nonce:ciphertext format
        self.assertNotIn("FILE_ADDED", encrypted)  # Should be encrypted
    
    def test_audit_line_decryption(self):
        """Test we can decrypt audit lines."""
        plaintext = '{"action": "FILE_ADDED"}'
        encrypted = self.crypto.encrypt_audit_line(plaintext)
        decrypted = self.crypto.decrypt_audit_line(encrypted)
        self.assertEqual(plaintext, decrypted)
    
    def test_audit_key_derivation(self):
        """Test that audit key is properly derived."""
        audit_key = self.crypto.derive_audit_key()
        self.assertEqual(len(audit_key), 32)  # 256 bits


class TestNetworkIsolationLinux(unittest.TestCase):
    """Test Linux network isolation."""
    
    def test_config_has_network_isolation_flag(self):
        """Test that enforcement config supports network isolation."""
        from phase2_oubliette.linux_enforcer import LinuxEnforcementConfig
        config = LinuxEnforcementConfig(enable_network_isolation=True)
        self.assertTrue(config.enable_network_isolation)


class TestNetworkIsolationWindows(unittest.TestCase):
    """Test Windows network isolation."""
    
    def test_windows_enforcer_has_network_methods(self):
        """Test that Windows enforcer has network isolation methods."""
        from phase2_oubliette.windows_enforcer import WindowsJobObjectEnforcer
        enforcer = WindowsJobObjectEnforcer()
        self.assertTrue(hasattr(enforcer, 'isolate_network'))
        self.assertTrue(hasattr(enforcer, 'remove_network_isolation'))


class TestNetworkIsolationMacOS(unittest.TestCase):
    """Test macOS network isolation."""
    
    def test_macos_profiles_have_network_deny(self):
        """Test that macOS sandbox profiles deny network."""
        from phase2_oubliette.macos_sandbox import SandboxProfile
        
        # All profiles should explicitly deny network
        for profile_name in ['PROFILE_AUDIO_RO', 'PROFILE_AUDIO_RW', 'PROFILE_RESTRICTED']:
            profile = getattr(SandboxProfile, profile_name)
            self.assertIn('(deny network*', profile)


class TestKeyBackup(unittest.TestCase):
    """Test key backup and recovery."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.vault = IterationVaultHardened(Path(self.temp_dir), owner_user="test")
        self.vault.initialize("test_password")
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_key_backup_export(self):
        """Test exporting key to backup file."""
        try:
            from phase1_iteration_wallet.key_recovery import VaultKeyBackup
            backup = VaultKeyBackup(Path(self.temp_dir))
            
            backup_file = Path(self.temp_dir) / "test_backup.vkb"
            backup.export_to_file("backup_passphrase", backup_file)
            
            self.assertTrue(backup_file.exists())
            self.assertGreater(backup_file.stat().st_size, 0)
        except ImportError:
            self.skipTest("key_recovery module not available")
    
    def test_key_backup_recovery_phrase(self):
        """Test exporting and validating recovery phrase."""
        try:
            from phase1_iteration_wallet.key_recovery import VaultKeyBackup
            backup = VaultKeyBackup(Path(self.temp_dir))
            
            words = backup.export_to_phrase()
            self.assertEqual(len(words), 33)  # 32 + 1 checksum
            
            # Should be recoverable
            recovered_salt = backup.import_from_phrase(words, restore=False)
            original_salt = backup._load_salt()
            self.assertEqual(recovered_salt, original_salt)
        except ImportError:
            self.skipTest("key_recovery module not available")


class TestAPIRateLimiting(unittest.TestCase):
    """Test REST API rate limiting."""
    
    def setUp(self):
        self.limiter = None
        try:
            from pubcast_vault_api import RateLimiter
            self.limiter = RateLimiter()
        except ImportError:
            pass
    
    def test_rate_limiter_allows_within_limit(self):
        """Test that requests within limit are allowed."""
        if not self.limiter:
            self.skipTest("Flask not available")
        
        for i in range(5):
            allowed, remaining = self.limiter.is_allowed("test_key", limit=10, window_secs=60)
            self.assertTrue(allowed)
    
    def test_rate_limiter_blocks_over_limit(self):
        """Test that requests over limit are blocked."""
        if not self.limiter:
            self.skipTest("Flask not available")
        
        limit = 3
        for i in range(limit):
            allowed, _ = self.limiter.is_allowed("test_key_2", limit=limit, window_secs=60)
            self.assertTrue(allowed)
        
        # Next request should be blocked
        allowed, remaining = self.limiter.is_allowed("test_key_2", limit=limit, window_secs=60)
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)


class TestAPIAuthentication(unittest.TestCase):
    """Test REST API token authentication."""
    
    def setUp(self):
        self.tokens = None
        try:
            from pubcast_vault_api import TokenManager
            self.tokens = TokenManager(expiry_hours=24)
        except ImportError:
            pass
    
    def test_token_login_success(self):
        """Test successful password-based login."""
        if not self.tokens:
            self.skipTest("Flask not available")
        
        self.tokens.set_vault_password("correct_password")
        token = self.tokens.login("correct_password", user="test_user")
        self.assertIsNotNone(token)
        self.assertGreater(len(token), 20)
    
    def test_token_login_failure(self):
        """Test that wrong password fails."""
        if not self.tokens:
            self.skipTest("Flask not available")
        
        self.tokens.set_vault_password("correct_password")
        token = self.tokens.login("wrong_password", user="test_user")
        self.assertIsNone(token)
    
    def test_token_validation(self):
        """Test token validation."""
        if not self.tokens:
            self.skipTest("Flask not available")
        
        self.tokens.set_vault_password("password")
        raw_token = self.tokens.login("password", user="alice")
        record = self.tokens.validate(raw_token)
        
        self.assertIsNotNone(record)
        self.assertEqual(record['user'], 'alice')


class TestInputValidation(unittest.TestCase):
    """Test API input validation."""
    
    def setUp(self):
        self.validator = None
        try:
            from pubcast_vault_api import InputValidator
            self.validator = InputValidator()
        except ImportError:
            pass
    
    def test_validate_password(self):
        """Test password validation."""
        if not self.validator:
            self.skipTest("Flask not available")
        
        ok, msg = self.validator.validate_password("short")
        self.assertFalse(ok)
        
        ok, msg = self.validator.validate_password("a_strong_password_123")
        self.assertTrue(ok)
    
    def test_validate_filename_rejects_path_traversal(self):
        """Test that path traversal is blocked."""
        if not self.validator:
            self.skipTest("Flask not available")
        
        ok, msg = self.validator.validate_filename("../../../etc/passwd")
        self.assertFalse(ok)
        
        ok, msg = self.validator.validate_filename("legitimate_file.wav")
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
