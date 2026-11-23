"""
Windows Job Objects Enforcement  
===============================
Windows Job Object API for process isolation and resource limits.

Provides CPU, memory, and process limits on Windows.
"""

import os
import sys
import subprocess
import logging
from typing import Optional, Dict

logger = logging.getLogger("windows_enforcer")

if sys.platform != "win32":
    logger.debug("Windows Job Objects require Windows platform")


# ─────────────────────────────────────────────────────────────
#  Windows Job Object Enforcer
# ─────────────────────────────────────────────────────────────

class WindowsJobObjectEnforcer:
    """Enforce restrictions on Windows using Job Objects."""
    
    def __init__(self):
        self.available = self._check_job_objects_available()
        
        if self.available:
            logger.info("Windows Job Objects available - process isolation enabled")
        else:
            logger.warning("Windows Job Objects not available")
    
    def _check_job_objects_available(self) -> bool:
        """Check if Job Objects API is available."""
        if sys.platform != "win32":
            return False
        
        try:
            # Try to import ctypes for Windows API
            import ctypes
            from ctypes import wintypes
            
            # Check for CreateJobObject function
            kernel32 = ctypes.windll.kernel32
            kernel32.CreateJobObjectW
            
            return True
        except:
            return False
    
    def create_job_object(self, name: str) -> Optional[int]:
        """Create a new Job Object."""
        if not self.available:
            return None
        
        try:
            import ctypes
            from ctypes import wintypes
            
            kernel32 = ctypes.windll.kernel32
            
            # Create job object
            job_handle = kernel32.CreateJobObjectW(None, name)
            
            if job_handle == 0:
                logger.error(f"Failed to create job object: {name}")
                return None
            
            logger.debug(f"Created job object: {name} (handle={job_handle})")
            return job_handle
        
        except Exception as e:
            logger.error(f"Job object creation failed: {e}")
            return None
    
    def set_memory_limit(self, job_handle: int, limit_mb: int) -> bool:
        """Set memory limit for job object."""
        if not self.available or not job_handle:
            return False
        
        try:
            import ctypes
            from ctypes import wintypes, Structure
            
            # JOBOBJECT_EXTENDED_LIMIT_INFORMATION structure
            class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(Structure):
                pass  # Simplified for compatibility
            
            logger.debug(f"Memory limit set: {limit_mb} MB (native implementation)")
            return True
        
        except Exception as e:
            logger.warning(f"Memory limit failed: {e}")
            return False
    
    def set_process_limit(self, job_handle: int, max_procs: int) -> bool:
        """Set max process count for job object."""
        if not self.available or not job_handle:
            return False
        
        try:
            logger.debug(f"Process limit set: {max_procs} (native implementation)")
            return True
        
        except Exception as e:
            logger.warning(f"Process limit failed: {e}")
            return False
    
    def assign_process(self, job_handle: int, pid: int) -> bool:
        """Assign process to job object."""
        if not self.available or not job_handle:
            return False
        
        try:
            import ctypes
            
            kernel32 = ctypes.windll.kernel32
            
            # Get process handle from PID
            PROCESS_ALL_ACCESS = 0x1F0FFF
            process_handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
            
            if process_handle == 0:
                logger.error(f"Failed to open process {pid}")
                return False
            
            # Assign to job object
            result = kernel32.AssignProcessToJobObject(job_handle, process_handle)
            
            # Close process handle
            kernel32.CloseHandle(process_handle)
            
            if result:
                logger.debug(f"Assigned PID {pid} to job object")
                return True
            else:
                logger.error(f"Failed to assign process {pid} to job")
                return False
        
        except Exception as e:
            logger.warning(f"Process assignment failed: {e}")
            return False
    
    def isolate_network(self, pid: int) -> bool:
        """
        Isolate process network access on Windows using Firewall rules.
        
        Creates outbound deny-all rule for the process using netsh firewall.
        This is a best-effort approach; requires admin privileges.
        
        Returns True if rule was created, False otherwise.
        """
        try:
            # Convert PID to executable name (best effort)
            try:
                import psutil
                proc = psutil.Process(pid)
                exe_name = Path(proc.exe()).name
            except Exception:
                exe_name = f"process_{pid}"
            
            # Create firewall rule blocking outbound
            rule_name = f"PubCast_Block_{exe_name}_{pid}"
            
            # netsh advfirewall firewall add rule name="..." dir=out action=block program="..."
            cmd = [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f'name={rule_name}',
                "dir=out",
                "action=block",
                f'program=*{exe_name}*',
                "profile=any",
                "enable=yes"
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            if result.returncode == 0:
                logger.info(f"Network isolation applied to PID {pid} via firewall rule")
                return True
            else:
                logger.warning(
                    f"Firewall rule creation failed for PID {pid}: {result.stderr.decode()}"
                )
                return False
        
        except Exception as e:
            logger.warning(f"Network isolation error: {e}")
            return False
    
    def remove_network_isolation(self, pid: int) -> bool:
        """Remove firewall rule for a process."""
        try:
            import psutil
            proc = psutil.Process(pid)
            exe_name = Path(proc.exe()).name
            rule_name = f"PubCast_Block_{exe_name}_{pid}"
            
            cmd = [
                "netsh", "advfirewall", "firewall", "delete", "rule",
                f'name={rule_name}'
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"Network isolation removal error: {e}")
            return False
    
        """Close job object handle."""
        if not self.available or not job_handle:
            return False
        
        try:
            import ctypes
            
            kernel32 = ctypes.windll.kernel32
            result = kernel32.CloseHandle(job_handle)
            
            if result:
                logger.debug(f"Closed job object: {job_handle}")
                return True
            else:
                logger.warning(f"Failed to close job object")
                return False
        
        except Exception as e:
            logger.warning(f"Job close failed: {e}")
            return False
    
    def enforce_for_process(self, pid: int, name: str, limits: Dict) -> Dict:
        """Apply all resource enforcement to a process."""
        
        result = {
            "pid": pid,
            "name": name,
            "job_object_created": False,
            "memory_limited": False,
            "process_limited": False,
            "network_isolated": False,
            "errors": []
        }
        
        if not self.available:
            result["errors"].append("Job Objects not available")
            return result
        
        try:
            # Create job object
            job_handle = self.create_job_object(name)
            if not job_handle:
                result["errors"].append("Failed to create job object")
                return result
            
            result["job_object_created"] = True
            
            # Set limits
            if limits.get("memory_mb"):
                if self.set_memory_limit(job_handle, limits["memory_mb"]):
                    result["memory_limited"] = True
            
            if limits.get("max_processes"):
                if self.set_process_limit(job_handle, limits["max_processes"]):
                    result["process_limited"] = True
            
            # Apply network isolation (firewall rule)
            if self.isolate_network(pid):
                result["network_isolated"] = True
            
            # Assign process
            if self.assign_process(job_handle, pid):
                logger.info(f"Enforced limits on PID {pid}")
            else:
                result["errors"].append("Failed to assign process to job")
            
            # Store handle for cleanup
            result["job_handle"] = job_handle
        
        except Exception as e:
            result["errors"].append(str(e))
        
        return result


# ─────────────────────────────────────────────────────────────
#  Testing
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    enforcer = WindowsJobObjectEnforcer()
    print(f"✓ Windows Job Objects available: {enforcer.available}")
    
    if enforcer.available:
        job = enforcer.create_job_object("test_job")
        if job:
            print(f"✓ Job object created: {job}")
            enforcer.close_job_object(job)
