# PubCast Vault — Complete Usage Guide

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements_all.txt

# 2. Create vault
python pubcast_vault_cli.py init ~/my_vault
# Enter password when prompted

# 3. Intake a file
python pubcast_vault_cli.py intake podcast.wav --source=uploaded

# 4. Verify vault
python pubcast_vault_cli.py verify

# 5. List files
python pubcast_vault_cli.py list
```

## Command Reference

### Initialize Vault
```bash
python pubcast_vault_cli.py init <vault_path>
```
Creates encrypted vault at specified path. Password required.

### Intake File
```bash
python pubcast_vault_cli.py intake <file_path> [--source=SOURCE]
```
- Classifies file (safe/suspicious/malicious)
- Sandboxes if needed
- Vaults with backup
- Returns file_id for use in AI pipeline

### List Files
```bash
python pubcast_vault_cli.py list [--project=PROJECT]
```
Show all vaulted files with metadata.

### Verify Integrity
```bash
python pubcast_vault_cli.py verify
```
Check vault for corruption. Auto-restores from backup if needed.

### Get Statistics
```bash
python pubcast_vault_cli.py stats
```
Show intake metrics and vault health.

## Python API Usage

### Basic Usage
```python
from pathlib import Path
from phase3_integration.pubcast_vault import PubCastSecurityVault

# Initialize
vault = PubCastSecurityVault(Path("/tmp/vault"))
vault.initialize("my_password")

# Intake file
file_id = vault.intake_file("/path/to/podcast.wav", source="uploaded")
print(f"File vaulted: {file_id}")

# List files
files = vault.list_vault_files(user="admin")
for f in files:
    print(f"{f['file_id']}: {f['original_filename']}")

# Verify
ok, msg = vault.verify_vault_integrity(user="admin")
print(f"Vault healthy: {ok}")
```

### With Background Integrity Checking
```python
from phase1_iteration_wallet.integrity_checker import (
    add_background_checking_to_vault
)

vault = PubCastSecurityVault(Path("/tmp/vault"))
vault.initialize("password")

# Enable background monitoring
vault = add_background_checking_to_vault(vault)

# Check integrity stats
stats = vault.get_integrity_stats()
print(f"Files checked: {stats['total_checks']}")
print(f"Restored: {stats['files_restored']}")
```

### With REST API
```python
from pubcast_vault_api import PubCastVaultAPI

vault = PubCastSecurityVault(Path("/tmp/vault"))
vault.initialize("password")

# Start API server
api = PubCastVaultAPI(vault, port=5000)
api.run(debug=False)

# Then from shell:
# curl http://localhost:5000/health
# curl -X POST http://localhost:5000/api/v1/files/intake \
#   -H "Authorization: Bearer TOKEN" \
#   -F "file=@podcast.wav"
```

## Architecture

### Phase 1: Iteration Wallet
Handles file custody, encryption, and restoration.
- **vault_engine_hardened.py** - Core vault with encryption & HMAC
- **integrity_checker.py** - Background monitoring

### Phase 2: Oubliette
Handles unsafe file inspection and sandboxing.
- **sandbox_hardened.py** - Core sandboxing with file classification
- **linux_enforcer.py** - Linux cgroups + seccomp
- **macos_sandbox.py** - macOS App Sandbox profiles
- **windows_enforcer.py** - Windows Job Objects

### Phase 3: Integration
Orchestrates Wallet + Oubliette for complete workflow.
- **pubcast_vault.py** - Main orchestrator
- **pubcast_vault_cli.py** - Command-line interface
- **pubcast_vault_api.py** - REST API server

## Security Features

### Encryption
- SQLCipher encrypted database (AES-256)
- Master password → derived keys via PBKDF2
- HMAC-SHA256 on all metadata

### Integrity
- Checksums on every file (SHA-256)
- Backup copy at intake
- Automatic corruption detection
- Automatic restoration from backup

### Isolation
- File processing in isolated subprocess
- Linux: cgroups v2 + seccomp
- macOS: App Sandbox profiles
- Windows: Job Objects

### Audit
- Immutable append-only audit log
- HMAC signed audit entries
- Complete user action tracking
- File access logging

### Access Control
- Role-based permissions (OWNER/ADMIN/USER/READ_ONLY)
- Per-user access tracking
- Audit trail on permission changes

## Configuration

### Resource Limits (Linux)
```python
from phase2_oubliette.linux_enforcer import LinuxResourceLimits

limits = LinuxResourceLimits(
    memory_mb=512,          # RAM limit
    cpu_cores=1.0,          # CPU cores
    timeout_seconds=60,     # Execution timeout
    max_processes=10,       # Process count
    max_file_size_mb=1024,  # File size limit
    allow_network=False     # Network access
)
```

### Threat Levels
1. **MAXIMUM** - Everything encrypted, sandboxed, and signed. Best security, ~20% overhead.
2. **BALANCED** - Known formats trusted, unknown sandboxed. Good security, ~5% overhead. Recommended.
3. **FAST** - Only malicious formats sandboxed. Weakest security. Internal only.

## Monitoring

### Integrity Stats
```bash
python pubcast_vault_cli.py stats
```
Shows:
- Total files vaulted
- Intake success rate
- Files quarantined
- Corruption detection stats

### Audit Logs
```python
vault.audit_engine.query_logs(
    user="admin",
    action="FILE_INTAKE",
    limit=100
)
```

### Live Monitoring
```python
# Start background checker
vault = add_background_checking_to_vault(vault)

# Get stats periodically
while True:
    stats = vault.get_integrity_stats()
    violations = vault.get_watcher_violations()
    
    print(f"Health: {stats['success_rate']:.1f}%")
    if violations:
        print(f"⚠️  {len(violations)} file modifications detected")
    
    time.sleep(60)
```

## Troubleshooting

### Database Locked
- Multiple processes accessing same vault
- Solution: Use different vault directories or add queue

### HMAC Verification Failed
- Database tampered with
- Solution: Restore from backup.db

### Encryption Key Lost
- Vault inaccessible forever
- Prevention: Back up key separately

### File Corrupted
- Automatic restoration triggers
- Check audit log for when corruption occurred
- Verify backup copy exists

## Performance Benchmarks

These should be the targets:

| Operation | Target | Notes |
|-----------|--------|-------|
| Intake file | <1s | Classify + sandbox + vault |
| List 1000 files | <100ms | Query with ACL check |
| Verify integrity | <10s | For 1000 files |
| Background check | <30s | Per 100 files hourly |

## Deployment

### Development
```bash
python pubcast_vault_cli.py init /tmp/vault
python test_suite_complete.py
```

### Staging
```bash
# Run with background checks
python -c "
from pathlib import Path
from phase3_integration.pubcast_vault import PubCastSecurityVault
from phase1_iteration_wallet.integrity_checker import add_background_checking_to_vault

vault = PubCastSecurityVault(Path('/vault'))
vault.initialize('prod_password')
vault = add_background_checking_to_vault(vault)
"
```

### Production
1. Deploy with systemd service
2. Enable background integrity checking
3. Ship audit logs to central store
4. Monitor for violations
5. Daily backup of vault directory
6. Weekly full system test

## API Examples

### Using curl
```bash
# Health check
curl http://localhost:5000/health

# Initialize vault
curl -X POST http://localhost:5000/api/v1/vault/init \
  -H "Content-Type: application/json" \
  -d '{"password": "secret", "vault_path": "/vault"}'

# Intake file
curl -X POST http://localhost:5000/api/v1/files/intake \
  -H "Authorization: Bearer TOKEN" \
  -F "file=@podcast.wav" \
  -F "source=uploaded"

# List files
curl http://localhost:5000/api/v1/files \
  -H "Authorization: Bearer TOKEN"

# Verify vault
curl -X POST http://localhost:5000/api/v1/vault/verify \
  -H "Authorization: Bearer TOKEN"
```

### Using Python
```python
import requests
import json

BASE_URL = "http://localhost:5000"

# Initialize
resp = requests.post(
    f"{BASE_URL}/api/v1/vault/init",
    json={"password": "secret", "vault_path": "/vault"}
)
print(resp.json())

# Intake
with open("podcast.wav", "rb") as f:
    files = {"file": f}
    data = {"source": "uploaded"}
    resp = requests.post(
        f"{BASE_URL}/api/v1/files/intake",
        files=files,
        data=data,
        headers={"Authorization": "Bearer TOKEN"}
    )
    print(resp.json())
```

## Support & Documentation

### Key Files
- **PUBCAST_SECURITY_ARCHITECTURE_PLAN.md** - Complete threat model and design
- **README.md** - Project overview
- **SESSION_1_HANDOFF.md** - Phase 1-3 completion status
- **test_suite_complete.py** - Test examples

### Architecture Deep Dive
Each module has inline documentation. Start with:
1. vault_engine_hardened.py - Encryption architecture
2. sandbox_hardened.py - Isolation framework
3. pubcast_vault.py - Integration workflow

---

**Status:** Session 3 Complete - Production Ready  
**Next:** Deployment and performance optimization
