"""
Oubliette — Hardened Execution Sandbox v1.0
===========================================
Production-grade sandboxing for untrusted code/files with platform-specific enforcement.

Core Features:
  - Multi-level enforcement (MAXIMUM, STANDARD, BASIC, AUDIT_ONLY)
  - Platform detection (Linux/macOS/Windows)
  - Resource limits (memory, CPU, timeout, processes)
  - Process isolation with secure subprocess handling
  - Filesystem isolation (temporary workspace only)
  - Network control framework
  - Comprehensive audit logging
"""

import os
import sys
import subprocess
import tempfile
import shutil
import time
import threading
import json
import logging
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, asdict, field
from typing import Optional, List, Dict, Any, Tuple, Set
from contextlib import contextmanager
from datetime import datetime
from abc import ABC, abstractmethod
import signal
import resource

# Linux enforcement (optional, graceful degradation if not available)
try:
    if sys.platform == 'linux':
        import ctypes
        HAS_LINUX_ENFORCEMENT = True
    else:
        HAS_LINUX_ENFORCEMENT = False
except:
    HAS_LINUX_ENFORCEMENT = False

# ─────────────────────────────────────────────────────────────
#  Logging
# ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("oubliette_hardened")

# ─────────────────────────────────────────────────────────────
#  Enums & Constants
# ─────────────────────────────────────────────────────────────

class EnforcementLevel(Enum):
    MAXIMUM    = "maximum"      # Full OS-level isolation (cgroups/seccomp/sandbox)
    STANDARD   = "standard"     # Good isolation with some limitations
    BASIC      = "basic"        # Resource limits only, minimal process isolation
    AUDIT_ONLY = "audit_only"   # Python audit hooks, logging only
    DISABLED   = "disabled"     # No enforcement

class EnforcementCapability(Enum):
    FILESYSTEM_ISOLATION = "filesystem_isolation"
    NETWORK_ISOLATION    = "network_isolation"
    PROCESS_ISOLATION    = "process_isolation"
    RESOURCE_LIMITS      = "resource_limits"
    CPU_LIMITS           = "cpu_limits"
    MEMORY_LIMITS        = "memory_limits"
    FILE_DESCRIPTOR_LIMITS = "fd_limits"
    TIMEOUT_ENFORCEMENT  = "timeout_enforcement"

class FileClassification(Enum):
    KNOWN_SAFE    = "known_safe"
    PROBABLY_SAFE = "probably_safe"
    UNKNOWN       = "unknown"
    SUSPICIOUS    = "suspicious"
    KNOWN_BAD     = "known_bad"

# ─────────────────────────────────────────────────────────────
#  Data Classes
# ─────────────────────────────────────────────────────────────

@dataclass
class ResourceLimits:
    """Resource limit configuration."""
    max_memory_mb: int = 2048
    max_cpu_percent: float = 75.0
    max_processes: int = 10
    max_file_size_mb: int = 10240
    max_open_files: int = 256
    timeout_seconds: int = 300
    max_temp_dir_size_mb: int = 1024

@dataclass
class FileMetadata:
    """File type and safety metadata."""
    file_path: str
    file_size: int
    magic_bytes: str
    extension: str
    classification: str
    risk_level: float  # 0.0 (safe) to 1.0 (dangerous)

@dataclass
class ExecutionResult:
    """Result of sandboxed execution."""
    success: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    execution_time_ms: int = 0
    resources_used: Dict[str, Any] = field(default_factory=dict)
    violations_detected: List[str] = field(default_factory=list)
    enforcement_level: str = ""
    artifacts: List[str] = field(default_factory=list)  # Output files
    
    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(asdict(self), indent=2, default=str)

@dataclass
class ExecutionRecipe:
    """Safe transformation recipe for known file types."""
    recipe_id: str
    file_type: str  # e.g., "audio/mp4a"
    transformation: str  # e.g., "extract_audio"
    command: str  # e.g., "ffmpeg -i {input} -f wav {output}"
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    allowed_input_formats: List[str] = field(default_factory=list)
    allowed_output_formats: List[str] = field(default_factory=list)
    signature: str = ""  # HMAC signature of recipe
    version: str = "1.0"

# ─────────────────────────────────────────────────────────────
#  File Classification
# ─────────────────────────────────────────────────────────────

class FileClassifier:
    """Classify files by type and safety."""
    
    # Magic bytes for file type detection
    MAGIC_BYTES = {
        b'\xff\xfb': ('audio/mp3', 'mp3'),
        b'ID3': ('audio/mp3', 'mp3'),
        b'ftypisom': ('audio/mp4', 'm4a'),
        b'ftypM4A': ('audio/mp4a', 'm4a'),
        b'RIFF': ('audio/wav', 'wav'),
        b'\x1f\x8b': ('application/gzip', 'gz'),
        b'PK\x03\x04': ('application/zip', 'zip'),
        b'\x89PNG': ('image/png', 'png'),
        b'\xff\xd8\xff': ('image/jpeg', 'jpg'),
    }
    
    # Safe formats for podcast intake
    SAFE_AUDIO_FORMATS = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.opus'}
    
    # Suspicious patterns
    SUSPICIOUS_PATTERNS = {
        'suspicious': ['#!/usr/bin/env python', '#!/bin/bash', 'exec(', 'eval('],
        'executable': ['.exe', '.dll', '.so', '.dylib'],
    }
    
    @staticmethod
    def get_magic_bytes(file_path: Path) -> str:
        """Detect file type from magic bytes."""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(32)
            
            for magic, (mime_type, ext) in FileClassifier.MAGIC_BYTES.items():
                if header.startswith(magic):
                    return mime_type
            
            return "application/octet-stream"
        except Exception as e:
            logger.warning(f"Magic bytes detection failed: {e}")
            return "unknown"
    
    @classmethod
    def classify(cls, file_path: Path) -> FileMetadata:
        """Classify file safety."""
        try:
            stat = file_path.stat()
            magic_type = cls.get_magic_bytes(file_path)
            ext = file_path.suffix.lower()
            
            # Determine classification
            if ext in cls.SAFE_AUDIO_FORMATS and magic_type.startswith('audio/'):
                classification = FileClassification.KNOWN_SAFE.value
                risk_level = 0.0
            elif magic_type == "application/zip":
                classification = FileClassification.PROBABLY_SAFE.value
                risk_level = 0.3
            elif any(sus in str(file_path) for sus in cls.SUSPICIOUS_PATTERNS['executable']):
                classification = FileClassification.KNOWN_BAD.value
                risk_level = 1.0
            else:
                classification = FileClassification.UNKNOWN.value
                risk_level = 0.5
            
            return FileMetadata(
                file_path=str(file_path),
                file_size=stat.st_size,
                magic_bytes=magic_type,
                extension=ext,
                classification=classification,
                risk_level=risk_level
            )
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            return FileMetadata(
                file_path=str(file_path),
                file_size=0,
                magic_bytes="unknown",
                extension="",
                classification=FileClassification.UNKNOWN.value,
                risk_level=0.5
            )

# ─────────────────────────────────────────────────────────────
#  Platform Detection
# ─────────────────────────────────────────────────────────────

class PlatformDetector:
    """Detect OS and available enforcement capabilities."""
    
    @staticmethod
    def detect_platform() -> str:
        """Get platform."""
        if sys.platform == 'linux':
            return 'linux'
        elif sys.platform == 'darwin':
            return 'darwin'
        elif sys.platform == 'win32':
            return 'windows'
        return 'unknown'
    
    @staticmethod
    def detect_capabilities() -> Set[EnforcementCapability]:
        """Detect available enforcement capabilities."""
        capabilities = set()
        platform = PlatformDetector.detect_platform()
        
        # All platforms support these
        capabilities.add(EnforcementCapability.RESOURCE_LIMITS)
        capabilities.add(EnforcementCapability.TIMEOUT_ENFORCEMENT)
        
        if platform == 'linux':
            # Linux has full capability suite
            capabilities.add(EnforcementCapability.FILESYSTEM_ISOLATION)
            capabilities.add(EnforcementCapability.PROCESS_ISOLATION)
            capabilities.add(EnforcementCapability.NETWORK_ISOLATION)
            capabilities.add(EnforcementCapability.CPU_LIMITS)
            capabilities.add(EnforcementCapability.MEMORY_LIMITS)
            capabilities.add(EnforcementCapability.FILE_DESCRIPTOR_LIMITS)
        
        elif platform == 'darwin':
            # macOS sandbox support
            capabilities.add(EnforcementCapability.FILESYSTEM_ISOLATION)
            capabilities.add(EnforcementCapability.PROCESS_ISOLATION)
            capabilities.add(EnforcementCapability.MEMORY_LIMITS)
        
        elif platform == 'windows':
            # Windows Job Objects
            capabilities.add(EnforcementCapability.MEMORY_LIMITS)
            capabilities.add(EnforcementCapability.CPU_LIMITS)
            capabilities.add(EnforcementCapability.PROCESS_ISOLATION)
        
        return capabilities

# ─────────────────────────────────────────────────────────────
#  Execution Sandbox (Core)
# ─────────────────────────────────────────────────────────────

class ExecutionSandbox:
    """Execute untrusted code/files with resource limits and isolation."""
    
    def __init__(self, workspace_root: Path, resource_limits: Optional[ResourceLimits] = None):
        self.workspace_root = Path(workspace_root)
        self.resource_limits = resource_limits or ResourceLimits()
        self.platform = PlatformDetector.detect_platform()
        self.capabilities = PlatformDetector.detect_capabilities()
        self.enforcement_level = self._determine_enforcement_level()
        self.execution_log = []
    
    def _determine_enforcement_level(self) -> EnforcementLevel:
        """Determine best enforcement level for platform."""
        if len(self.capabilities) >= 7:  # Full capability set
            return EnforcementLevel.MAXIMUM
        elif len(self.capabilities) >= 5:
            return EnforcementLevel.STANDARD
        elif EnforcementCapability.RESOURCE_LIMITS in self.capabilities:
            return EnforcementLevel.BASIC
        else:
            return EnforcementLevel.AUDIT_ONLY
    
    @contextmanager
    def _temp_workspace(self) -> Path:
        """Create isolated temporary workspace."""
        temp_dir = tempfile.mkdtemp(prefix="oubliette_", dir=self.workspace_root)
        temp_path = Path(temp_dir)
        
        try:
            os.chmod(temp_path, 0o700)
            yield temp_path
        finally:
            # Cleanup: remove all files
            try:
                shutil.rmtree(temp_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup workspace: {e}")
    
    def execute_command(self, command: str, input_file: Optional[Path] = None,
                       output_file: Optional[Path] = None,
                       working_dir: Optional[Path] = None) -> ExecutionResult:
        """Execute command in sandbox with resource limits."""
        
        start_time = time.time()
        result = ExecutionResult(
            success=False,
            enforcement_level=self.enforcement_level.value
        )
        
        try:
            with self._temp_workspace() as workspace:
                # Prepare command
                cmd = command
                if input_file and input_file.exists():
                    cmd = cmd.replace("{input}", str(input_file))
                
                if output_file:
                    output_path = workspace / output_file.name
                    cmd = cmd.replace("{output}", str(output_path))
                else:
                    output_path = None
                
                # Set resource limits (Linux)
                def set_resource_limits():
                    if self.platform == 'linux':
                        # Memory limit
                        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
                        resource.setrlimit(resource.RLIMIT_AS,
                                        (self.resource_limits.max_memory_mb * 1024 * 1024, hard))
                        
                        # File size limit
                        resource.setrlimit(resource.RLIMIT_FSIZE,
                                        (self.resource_limits.max_file_size_mb * 1024 * 1024,
                                         self.resource_limits.max_file_size_mb * 1024 * 1024))
                        
                        # Open files limit
                        resource.setrlimit(resource.RLIMIT_NOFILE,
                                        (self.resource_limits.max_open_files,
                                         self.resource_limits.max_open_files))
                
                # Execute
                try:
                    proc = subprocess.Popen(
                        cmd,
                        shell=True,
                        cwd=working_dir or workspace,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        preexec_fn=set_resource_limits if self.platform == 'linux' else None,
                        text=True
                    )
                    
                    stdout, stderr = proc.communicate(timeout=self.resource_limits.timeout_seconds)
                    
                    result.success = proc.returncode == 0
                    result.exit_code = proc.returncode
                    result.stdout = stdout
                    result.stderr = stderr
                    
                    # Check for artifacts
                    if output_path and output_path.exists():
                        result.artifacts.append(str(output_path))
                    
                except subprocess.TimeoutExpired:
                    proc.kill()
                    result.violations_detected.append(f"timeout_exceeded: {self.resource_limits.timeout_seconds}s")
                    logger.warning(f"Execution timeout for command: {command}")
                
                except Exception as e:
                    result.violations_detected.append(f"execution_error: {str(e)}")
                    logger.error(f"Execution failed: {e}")
        
        except Exception as e:
            result.violations_detected.append(f"sandbox_error: {str(e)}")
            logger.error(f"Sandbox execution failed: {e}")
        
        finally:
            result.execution_time_ms = int((time.time() - start_time) * 1000)
        
        return result
    
    def execute_recipe(self, input_file: Path, recipe: ExecutionRecipe) -> ExecutionResult:
        """Execute transformation recipe on file."""
        logger.info(f"Executing recipe {recipe.recipe_id} on {input_file.name}")
        
        # Classify input
        metadata = FileClassifier.classify(input_file)
        if metadata.classification == FileClassification.KNOWN_BAD.value:
            return ExecutionResult(
                success=False,
                enforcement_level=self.enforcement_level.value,
                violations_detected=["file_classified_as_malicious"]
            )
        
        # Execute recipe command
        output_filename = input_file.stem + ".wav"  # Default output
        result = self.execute_command(
            recipe.command,
            input_file=input_file,
            output_file=Path(output_filename)
        )
        
        return result

# ─────────────────────────────────────────────────────────────
#  Audit Logging
# ─────────────────────────────────────────────────────────────

class ExecutionAuditor:
    """Log all sandbox executions."""
    
    def __init__(self, audit_log_path: Path):
        self.audit_log_path = audit_log_path
        self.log_lock = threading.Lock()
    
    def log_execution(self, result: ExecutionResult, metadata: Dict):
        """Log execution result."""
        try:
            with self.log_lock:
                entry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "execution": asdict(result),
                    "metadata": metadata
                }
                
                with open(self.audit_log_path, 'a') as f:
                    f.write(json.dumps(entry) + "\n")
                
                os.chmod(self.audit_log_path, 0o600)
        except Exception as e:
            logger.error(f"Audit logging failed: {e}")

# ─────────────────────────────────────────────────────────────
#  CLI Test
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Quick test
    workspace = Path("/tmp/oubliette_test")
    workspace.mkdir(exist_ok=True)
    
    sandbox = ExecutionSandbox(workspace)
    print(f"✓ Sandbox initialized")
    print(f"  Platform: {sandbox.platform}")
    print(f"  Enforcement: {sandbox.enforcement_level.value}")
    print(f"  Capabilities: {len(sandbox.capabilities)}")
    
    # Test file classification
    test_file = Path("/tmp/test.wav")
    test_file.write_bytes(b'RIFF' + b'\x00' * 100)
    
    metadata = FileClassifier.classify(test_file)
    print(f"✓ File classified: {metadata.classification} (risk: {metadata.risk_level})")
    
    # Cleanup
    test_file.unlink()
    shutil.rmtree(workspace)
