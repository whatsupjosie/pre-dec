"""
PubCast Vault Complete Test Suite
==================================
Unit, integration, security, and performance tests.
Run with: python test_suite_complete.py
"""

import sys
import unittest
import tempfile
import shutil
import json
from pathlib import Path
from datetime import datetime
import time
import os

# Add phase paths
sys.path.insert(0, str(Path(__file__).parent / "phase1_iteration_wallet"))
sys.path.insert(0, str(Path(__file__).parent / "phase2_oubliette"))
sys.path.insert(0, str(Path(__file__).parent / "phase3_integration"))

try:
    from vault_engine_hardened import (
        IterationVaultHardened, CryptoManager, VaultACL, Role, AuditAction
    )
    from sandbox_hardened import (
        FileClassifier, ExecutionSandbox, ResourceLimits, FileClassification
    )
    from pubcast_vault import PubCastSecurityVault
    from integrity_checker import BackgroundIntegrityChecker, FilesystemWatcher
    from linux_enforcer import LinuxResourceEnforcer, LinuxResourceLimits
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
#  Crypto Tests
# ─────────────────────────────────────────────────────────────

class TestCryptography(unittest.TestCase):
    """Test cryptographic operations."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.crypto = CryptoManager(Path(self.temp_dir))
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_key_derivation(self):
        """Test key derivation from password."""
        result = self.crypto.initialize("test_password_123")
        self.assertTrue(result)
        self.assertIsNotNone(self.crypto.hmac_key)
        self.assertIsNotNone(self.crypto.db_cipher_key)
    
    def test_deterministic_keys(self):
        """Test same password produces same keys."""
        self.crypto.initialize("password")
        key1 = self.crypto.db_cipher_key
        
        crypto2 = CryptoManager(Path(tempfile.mkdtemp()))
        crypto2.initialize("password")
        key2 = crypto2.db_cipher_key
        
        self.assertEqual(key1, key2)
    
    def test_unique_keys(self):
        """Test different passwords produce different keys."""
        self.crypto.initialize("password1")
        key1 = self.crypto.db_cipher_key
        
        crypto2 = CryptoManager(Path(tempfile.mkdtemp()))
        crypto2.initialize("password2")
        key2 = crypto2.db_cipher_key
        
        self.assertNotEqual(key1, key2)
    
    def test_hmac_verification(self):
        """Test HMAC signing and verification."""
        self.crypto.initialize("password")
        data = '{"test": "data"}'
        
        hmac_value = self.crypto.sign_data(data)
        self.assertIsNotNone(hmac_value)
        
        verified = self.crypto.verify_hmac(data, hmac_value)
        self.assertTrue(verified)


# ─────────────────────────────────────────────────────────────
#  File Classification Tests
# ─────────────────────────────────────────────────────────────

class TestFileClassification(unittest.TestCase):
    """Test file type detection and safety classification."""
    
    def setUp(self):
        self.classifier = FileClassifier()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_classify_wav_safe(self):
        """Test WAV file classification."""
        wav_path = Path(self.temp_dir) / "test.wav"
        # Write minimal WAV header
        with open(wav_path, 'wb') as f:
            f.write(b'RIFF' + b'\x00' * 4 + b'WAVE')
        
        result = self.classifier.classify(str(wav_path))
        self.assertEqual(result.safety, "SAFE")
        self.assertEqual(result.file_type, "audio")
    
    def test_classify_text_suspicious(self):
        """Test text file classification."""
        txt_path = Path(self.temp_dir) / "test.txt"
        with open(txt_path, 'w') as f:
            f.write("This is a text file")
        
        result = self.classifier.classify(str(txt_path))
        # Text files might be SUSPICIOUS
        self.assertIn(result.safety, ["SAFE", "SUSPICIOUS"])


# ─────────────────────────────────────────────────────────────
#  Vault Integration Tests
# ─────────────────────────────────────────────────────────────

class TestVaultIntegration(unittest.TestCase):
    """Test complete vault workflows."""
    
    def setUp(self):
        self.vault_dir = Path(tempfile.mkdtemp())
        self.vault = PubCastSecurityVault(self.vault_dir)
        self.vault.initialize("test_password_123")
    
    def tearDown(self):
        shutil.rmtree(self.vault_dir)
    
    def test_vault_initialization(self):
        """Test vault setup."""
        self.assertTrue((self.vault_dir / ".vault_db").exists())
    
    def test_file_intake_workflow(self):
        """Test complete file intake."""
        # Create test file
        test_file = Path(self.vault_dir) / "test.wav"
        with open(test_file, 'wb') as f:
            f.write(b'RIFF' + b'\x00' * 4 + b'WAVE' + b'\x00' * 100)
        
        # Intake file
        file_id = self.vault.intake_file(str(test_file), source="test")
        
        self.assertIsNotNone(file_id)
        self.assertNotEqual(file_id, "")
    
    def test_vault_integrity_verification(self):
        """Test vault integrity checking."""
        ok, msg = self.vault.verify_vault_integrity(user="test_user")
        # Should be OK on fresh vault
        self.assertTrue(ok or "empty" in msg.lower())


# ─────────────────────────────────────────────────────────────
#  Background Checking Tests
# ─────────────────────────────────────────────────────────────

class TestBackgroundChecking(unittest.TestCase):
    """Test background integrity monitoring."""
    
    def setUp(self):
        self.vault_dir = Path(tempfile.mkdtemp())
        self.vault = PubCastSecurityVault(self.vault_dir)
        self.vault.initialize("password123")
        self.checker = BackgroundIntegrityChecker(self.vault, check_interval_hours=1)
    
    def tearDown(self):
        self.checker.stop()
        shutil.rmtree(self.vault_dir)
    
    def test_checker_initialization(self):
        """Test integrity checker setup."""
        self.assertFalse(self.checker.running)
        self.assertEqual(len(self.checker.check_history), 0)
    
    def test_checker_start_stop(self):
        """Test starting and stopping checker."""
        self.checker.start()
        self.assertTrue(self.checker.running)
        
        self.checker.stop()
        time.sleep(0.5)
        self.assertFalse(self.checker.running)
    
    def test_statistics_generation(self):
        """Test stat generation."""
        stats = self.checker.get_statistics()
        
        self.assertIn("total_checks", stats)
        self.assertIn("success_rate", stats)
        self.assertIn("running", stats)


# ─────────────────────────────────────────────────────────────
#  Platform Enforcement Tests
# ─────────────────────────────────────────────────────────────

class TestLinuxEnforcement(unittest.TestCase):
    """Test Linux resource enforcement."""
    
    @unittest.skipUnless(sys.platform == "linux", "Linux only")
    def test_linux_enforcer_init(self):
        """Test Linux enforcer initialization."""
        limits = LinuxResourceLimits(memory_mb=256, cpu_cores=0.5)
        enforcer = LinuxResourceEnforcer(limits)
        
        self.assertIsNotNone(enforcer.cgroups)
        self.assertIsNotNone(enforcer.seccomp)
        self.assertEqual(enforcer.limits.memory_mb, 256)


# ─────────────────────────────────────────────────────────────
#  Performance Tests
# ─────────────────────────────────────────────────────────────

class TestPerformance(unittest.TestCase):
    """Test performance characteristics."""
    
    def setUp(self):
        self.vault_dir = Path(tempfile.mkdtemp())
        self.vault = PubCastSecurityVault(self.vault_dir)
        self.vault.initialize("password123")
    
    def tearDown(self):
        shutil.rmtree(self.vault_dir)
    
    def test_intake_speed(self):
        """Test file intake speed."""
        # Create test file
        test_file = Path(self.vault_dir) / "test.wav"
        with open(test_file, 'wb') as f:
            f.write(b'RIFF' + b'\x00' * 4 + b'WAVE' + b'\x00' * 10000)
        
        # Time intake
        start = time.time()
        file_id = self.vault.intake_file(str(test_file), source="test")
        elapsed = time.time() - start
        
        # Should be reasonably fast
        self.assertLess(elapsed, 5.0, f"Intake too slow: {elapsed}s")
    
    def test_list_speed(self):
        """Test file listing speed."""
        start = time.time()
        files = self.vault.list_vault_files(user="test_user")
        elapsed = time.time() - start
        
        # Should be fast
        self.assertLess(elapsed, 1.0, f"Listing too slow: {elapsed}s")


# ─────────────────────────────────────────────────────────────
#  Test Runners
# ─────────────────────────────────────────────────────────────

def run_all_tests(verbosity=2):
    """Run entire test suite."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestCryptography))
    suite.addTests(loader.loadTestsFromTestCase(TestFileClassification))
    suite.addTests(loader.loadTestsFromTestCase(TestVaultIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestBackgroundChecking))
    suite.addTests(loader.loadTestsFromTestCase(TestLinuxEnforcement))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformance))
    
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    return result


def print_summary(result):
    """Print test summary."""
    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("PubCast Vault Test Suite")
    print("=" * 70)
    
    result = run_all_tests(verbosity=2)
    success = print_summary(result)
    
    sys.exit(0 if success else 1)
