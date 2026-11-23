# PubCast AI Security Architecture
## Iteration Wallet + Oubliette Integration Plan

**Date:** May 4, 2026  
**Status:** Strategic Assessment & Hardening Blueprint  
**Scope:** Two complementary security systems for hostile-environment file handling and AI inference

---

## EXECUTIVE SUMMARY

You have the bones of two brilliant, complementary security systems:

### **Iteration Wallet** (File Vault System)
- **What it does:** Immutable file versioning with guaranteed restoration, zero-delete philosophy
- **Why it matters:** Files from untrusted sources get tracked at every mutation, can be restored to canonical states, immune to silent corruption
- **Current state:** Mature core (v6) with proper SQLite WAL, UUID tracking, backup copies, and filesystem watching
- **Key doctrine:** NO DELETING FROM THE VAULT. EVER. Archive, retire, hide, promote—never destroy.

### **Oubliette** (Execution Sandbox)
- **What it does:** Cross-platform resource-limited, network-isolated execution environment for untrusted code
- **Why it matters:** AI systems processing files need guardrails; Oubliette ensures unknown code can't escape, steal resources, or poison the system
- **Current state:** Sophisticated enforcement architecture (v2) with capability detection, multi-level enforcement, process isolation, audit logging
- **Key doctrine:** Assume hostile intent, prove safety before execution, log everything, isolate by default

### **The Gap We're Closing**
These two systems are designed to be **separated but orchestrated**:
1. **Intake Phase (Oubliette):** Untrusted files arrive → probed, hashed, classified in isolated execution
2. **Custody Phase (Iteration Wallet):** Safe-to-use versions → vaulted with complete lineage tracking
3. **Retrieval Phase (Both):** Files accessed only from vault, mutations logged, restoration guaranteed

---

## PART 1: CURRENT STATE ASSESSMENT

### Iteration Wallet Status: **7.5/10 - Strong Foundation, Needs Hardening**

**Strengths:**
- ✅ SQLite WAL mode with persistent connections (crash-safe)
- ✅ UUID-based file tracking (immune to hash collisions)
- ✅ Checksums recomputed at promotion (not inherited)
- ✅ Backup copy at add-time for reliable restoration
- ✅ Threading.Lock for DB safety
- ✅ Filesystem watcher with RESTORATION (not just detection)
- ✅ Staging garbage collection (30-day auto-purge)
- ✅ Event logging instead of silent failures

**Weaknesses:**
- ⚠️ No cryptographic integrity verification (SHA-256 only, no signing)
- ⚠️ Vault paths not encrypted on disk
- ⚠️ No tamper detection for vault metadata
- ⚠️ Limited to single machine (no distributed audit trail)
- ⚠️ Database itself not encrypted
- ⚠️ No permission model (vault accessible to any user on system)
- ⚠️ Lacks comprehensive audit logging for regulatory compliance
- ⚠️ UI/API incomplete in some versions

**Critical Issues Found in Codebase:**
1. Vault backup stored in plaintext alongside vault
2. No write-ahead logging for metadata changes
3. Removed files not cryptographically shredded (recoverable with forensics)
4. DB snapshots kept in `db_backups` without encryption

---

### Oubliette Status: **8.5/10 - Sophisticated, Needs Completion**

**Strengths:**
- ✅ Multi-level enforcement architecture (MAXIMUM → AUDIT_ONLY)
- ✅ Platform detection with graceful degradation (Windows/macOS/Linux)
- ✅ Resource limits (memory, processes, file size, CPU)
- ✅ Timeout enforcement
- ✅ Network control capability framework
- ✅ Process isolation patterns
- ✅ Audit logging and violation detection
- ✅ Result reporting with performance metrics

**Weaknesses:**
- ⚠️ Platform-specific implementations incomplete (Windows/macOS/Linux enforcement not fully coded)
- ⚠️ Network control framework defined but not implemented
- ⚠️ No persistent enforcement state (enforcement resets between runs)
- ⚠️ Missing file descriptor limits
- ⚠️ No GPU/TPU isolation (relevant for AI inference)
- ⚠️ Python audit hooks incomplete
- ⚠️ No signed execution recipes
- ⚠️ Lacks integration with Iteration Wallet

---

## PART 2: SECURITY THREAT MODEL FOR PUBCAST AI

### Threats We're Defending Against

#### **A. Untrusted File Intake (Highest Priority)**
- **Threat:** Attacker uploads malicious podcast files, transcripts, or scripts
- **Attack vectors:** 
  - Embedded code execution (e.g., polyglot files, zip bombs)
  - Buffer overflows in format parsers
  - Serialization gadgets (pickle, pickle-equivalent formats)
  - Zip slip attacks (path traversal)
- **Iteration Wallet role:** Isolate intake, hash immediately, track every copy
- **Oubliette role:** Parse/transform only in sandbox, never in live system

#### **B. AI Model Exploitation (High Priority)**
- **Threat:** LLM/transcription/synthesis processes compromise system security
- **Attack vectors:**
  - Prompt injection via file metadata
  - Memory disclosure via inference sidechannels
  - Model poisoning via training data corruption
  - Output poisoning (malicious transcripts written back)
- **Iteration Wallet role:** All AI outputs versioned, mutations tracked
- **Oubliette role:** AI processes run isolated with resource limits, no network access

#### **C. Silent Corruption (Critical)**
- **Threat:** Files mutated by system crashes, process bugs, or adversaries without detection
- **Attack vectors:**
  - Bit flips from memory errors
  - Partial writes from interrupted transactions
  - External modifications via privileged processes
  - Ransomware or data-wiping malware
- **Iteration Wallet role:** Checksum mismatch detected, original restored automatically
- **Oubliette role:** Mutations only allowed in sandboxed processes

#### **D. Supply Chain (Medium Priority)**
- **Threat:** Dependencies or system libraries contain malicious code
- **Attack vectors:**
  - Compromised pip packages
  - System library vulnerabilities
  - Codec/FFmpeg exploits
- **Iteration Wallet role:** Dependency versions pinned, audit trail of what versions were used
- **Oubliette role:** Codecs loaded only in isolated processes

#### **E. Insider/Elevated Privilege (Medium Priority)**
- **Threat:** Malicious admin or compromised process with elevated privileges
- **Attack vectors:**
  - Direct vault file modification
  - Database corruption
  - Audit log tampering
- **Iteration Wallet role:** Vault stored immutably, audit logs on separate storage
- **Oubliette role:** Enforcement runs at higher privilege, can't be downgraded by lower processes

---

## PART 3: ARCHITECTURAL SEPARATION STRATEGY

### System 1: **Iteration Wallet** (The Vault)
**Purpose:** File custody and restoration guarantee  
**Principle:** Non-destructive, auditable, immutable lineage

**Responsibilities:**
- Ingest files → vault immediately with backup copy
- Track every state change in SQLite with timestamps
- Detect mutations via periodic checksum validation
- Restore files to canonical versions on corruption detection
- Maintain complete audit trail of who accessed what when
- Archive, retire, supersede old versions without deletion
- Provide query interface for "show me all files matching criteria"

**Isolation Boundary:**
- Separate database file from vault storage
- Separate backup directory from live vault
- Separate audit logs from metadata
- All paths use UUIDs internally, human names optional for search

**Never Touches:**
- File parsing/interpretation (leaves to Oubliette)
- Execution of file contents (leaves to Oubliette)
- Network operations
- External service integration

---

### System 2: **Oubliette** (The Sandbox)
**Purpose:** Safe execution and inspection of untrusted code/files  
**Principle:** Assume hostile, prove safe, audit everything

**Responsibilities:**
- Detect file type/format with multiple heuristics (magic bytes, extension, content scan)
- Classify trust level (known safe, probably safe, unknown, suspicious, known bad)
- Run format parsers/transformers only in isolated subprocess
- Enforce resource limits during execution (timeout, memory, CPU)
- Prevent network access unless explicitly allowed
- Block filesystem access outside sandbox
- Generate execution report: success, resource use, artifacts created
- Approve artifacts for promotion to Iteration Wallet

**Isolation Boundary:**
- Separate process with restricted capabilities
- Temporary workspace (deleted after execution)
- No persistent state outside audit logs
- All subprocess execution goes through enforcer

**Never Touches:**
- Vault operations directly (delegates to Iteration Wallet API)
- System-level security policies (leaves to OS)
- Persistent data storage (delegates to Iteration Wallet)
- User-facing interfaces (separate concern)

---

## PART 4: INTEGRATION ARCHITECTURE

### Data Flow: Untrusted File → Safe Vault

```
┌─────────────────────────────────────────────────────────────────┐
│ INTAKE PHASE (Oubliette)                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. File Arrives                                                │
│     ↓                                                           │
│  2. Quick Hash + Magic Bytes Detection                          │
│     ↓                                                           │
│  3. Classification (Known Safe / Unknown / Suspicious)          │
│     ↓                                                           │
│  4. If Safe → Quick Intake                                      │
│     If Unknown → Sandboxed Probe                                │
│     If Suspicious → Quarantine + Alert                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ SANITIZATION PHASE (Oubliette → Iteration Wallet)              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Copy to Temporary Workspace                                │
│     ↓                                                           │
│  2. Run Format Parser in Isolated Process                      │
│     (with resource limits, timeout, no network)                │
│     ↓                                                           │
│  3. Collect Artifacts (parsed content, metadata, logs)         │
│     ↓                                                           │
│  4. Verify No Violations (timeouts, resource overruns, etc)    │
│     ↓                                                           │
│  5. Checksum Artifacts                                          │
│     ↓                                                           │
│  6. Generate Execution Report                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ CUSTODY PHASE (Iteration Wallet)                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Original File → Vault + Backup Copy                        │
│     (UUID, timestamp, source metadata)                         │
│     ↓                                                           │
│  2. Sanitized File → Vault + Backup Copy                       │
│     (UUID, linked to original, safe flag, conversion log)      │
│     ↓                                                           │
│  3. Execution Report → Vault + Audit Log                       │
│     (signed timestamp, enforcement level, violations)          │
│     ↓                                                           │
│  4. DB Record Created                                           │
│     (complete provenance chain)                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                           ↓
          ✅ File Safe for Use in PubCast AI
```

---

## PART 5: COMPLETE HARDENING PLAN

### Phase 1: Iteration Wallet Hardening (2-3 weeks)

#### **1.1 Database & Storage Encryption**
- [ ] Implement SQLCipher for Iteration Wallet database
  - Encrypt metadata (paths, checksums, audit trail)
  - Preserve no plaintext secrets in DB file
  - Key derivation from master password + salt
- [ ] Encrypt vault file backups
  - Use AES-256-GCM
  - Separate key from main Iteration Wallet password
  - Backup key stored in secure location (ideally separate disk)
- [ ] Encrypt removed files staging area
  - Files in `.vault_staging` encrypted before disk write
  - Cryptographic shredding on purge (overwrite 3x before deletion)

#### **1.2 Cryptographic Integrity Verification**
- [ ] Implement HMAC-SHA256 for metadata
  - Sign all database records with HMAC key
  - Detect tampering by mismatched HMAC on read
- [ ] Implement Merkle tree for vault contents
  - Hash chain from root hash down to individual files
  - Corruption in any file detected at query time
- [ ] Signed checksum reports
  - Audit trail digitally signed
  - Timestamp server verification (optional, for high security)

#### **1.3 Permission & Access Control**
- [ ] Implement vault-level ACL
  - Owner, allowed users, read-only vs read-write
  - Project-level permissions
  - API token authentication for programmatic access
- [ ] Separate admin vs user operations
  - Admin: create vault, set retention, archive projects
  - User: add files, promote versions, query vault
  - Audit admin changes with extra logging
- [ ] Filesystem ACL enforcement
  - Vault directory mode 700 (user only)
  - Database file mode 600
  - Backup directory hidden, restricted read

#### **1.4 Comprehensive Audit Logging**
- [ ] Structured audit log (JSON format)
  - Every file operation logged: add, access, promote, archive
  - Who (user/token), what (operation), when (timestamp), result (success/fail)
- [ ] Immutable audit log storage
  - Append-only file, never overwritten
  - Hash chaining for tamper detection
- [ ] Audit log rotation & archival
  - Rotate daily, sign, compress
  - Archive to separate storage (cloud, external disk)
- [ ] Query audit logs
  - Search by user, file, date range, operation type

#### **1.5 Corruption Detection & Recovery**
- [ ] Continuous integrity checking
  - Background task: periodically verify checksums
  - Periodic DB integrity check (PRAGMA integrity_check)
  - Report mismatches immediately
- [ ] Automatic restoration workflow
  - Checksum mismatch detected → compare to backup copy
  - Restore from backup, log incident, alert admin
  - Preserve corrupted file for forensics
- [ ] DB snapshot versioning
  - Keep rolling 10 snapshots (as current code does)
  - Add verification: checksum of snapshot itself
  - Enable restore-to-point-in-time if needed

#### **1.6 Testing & Validation**
- [ ] Unit tests for all new crypto functions
  - HMAC verification, encryption/decryption, Merkle tree operations
- [ ] Integration tests
  - Vault creation, file add, checksum mismatch → recovery, permission enforcement
- [ ] Stress tests
  - 10K files, concurrent operations, crash during transaction
- [ ] Security tests
  - Tampered database → rejected
  - Corrupted backup → detected
  - Unauthorized user → denied with audit log

---

### Phase 2: Oubliette Completion & Hardening (2-3 weeks)

#### **2.1 Platform-Specific Enforcement Completion**

**Linux (cgroups v2 + seccomp):**
- [ ] Implement memory limit enforcement via cgroup
- [ ] Implement CPU limit enforcement via cgroup
- [ ] Implement network isolation via netns (network namespace)
- [ ] Implement filesystem isolation via mount namespace
- [ ] Implement process isolation via pidns + uts namespace
- [ ] Implement seccomp rules to block dangerous syscalls

**macOS (sandbox profile):**
- [ ] Generate sandbox profile for temporary workspace
- [ ] Allow read-only access to system libraries
- [ ] Deny network access by default
- [ ] Deny access to /Users outside temp workspace
- [ ] Enable file access audit
- [ ] Use `sandbox-exec` to enforce

**Windows (Job Objects + AppContainer):**
- [ ] Create Job Object with resource limits
- [ ] Set memory limit via JobObject API
- [ ] Set CPU time limit
- [ ] Create restricted token (low integrity)
- [ ] Use AppContainer for filesystem isolation
- [ ] Implement network restriction via WinFW rules

#### **2.2 Execution Recipes & Safe Transformations**
- [ ] Build recipe system for known file types
  - Recipe = approved transformation (e.g., WAV extraction from M4A)
  - Recipe includes: parser command, resource limits, timeout, allowed output formats
  - Recipes signed, versioned, auditable
- [ ] Implement common podcast audio recipes
  - M4A → WAV (via ffmpeg in sandbox)
  - MP3 → WAV
  - Opus → WAV
  - WAV metadata extraction (hash, bitrate, channels, length)
- [ ] Implement safety checks
  - Format detection (magic bytes, not extension)
  - Bitrate sanity check (reject >320kbps audio as suspicious)
  - Duration sanity check (reject >48hr as suspicious)
  - Reject files with embedded scripts, code, executables

#### **2.3 AI-Specific Hardening**
- [ ] Resource limits for transcription
  - Memory cap (GPU memory separate from system)
  - CPU cap (don't starve other processes)
  - Timeout (don't let inference hang forever)
- [ ] Model isolation
  - Each model run in separate process
  - Model files verified before load (hash check, signature)
  - Output files quarantined until scanned
- [ ] Prompt injection detection
  - Scan file metadata for suspicious patterns
  - Limit metadata field lengths
  - Encode suspicious characters in metadata

#### **2.4 Persistent Enforcement State & Recovery**
- [ ] Implement Oubliette enforcement log
  - Every execution attempt logged
  - Violations recorded (timeout, memory overrun, network attempt, etc)
  - Success/failure with exit code
- [ ] Implement enforcement cache
  - "I've seen this file before" → reuse enforcement result
  - Cache entry = hash + execution recipe + result + timestamp
  - If newer version of recipe → re-execute
- [ ] Implement enforcement recovery
  - Incomplete execution detected → cleanup + log
  - Stale temp directories cleaned up on startup
  - Orphaned processes killed

#### **2.5 Network Control Implementation**
- [ ] Implement allow-list for network access
  - By default: no network access
  - Optional: allow DNS to specific resolvers
  - Optional: allow HTTPS to specific domains
  - No UDP by default (reduce attack surface)
- [ ] Implement network timeout
  - Connection timeout
  - Request timeout
  - Total network time budget
- [ ] Implement network audit logging
  - Log all network attempt (blocked or allowed)
  - Log source/dest IP, port, protocol
  - Log certificate info (for HTTPS)

#### **2.6 Testing & Validation**
- [ ] Platform-specific enforcement tests
  - Memory limit test: allocate >limit, verify kill
  - CPU limit test: busy-wait, verify cgroup throttle
  - Filesystem isolation test: try access /etc, verify denied
  - Network isolation test: try connect to 8.8.8.8, verify blocked
- [ ] Malware simulation
  - Benign: simple script, should succeed
  - Malicious: fork bomb, should fail with limit exceeded
  - Malicious: network access, should fail with network denied
  - Malicious: write to /tmp, should fail with filesystem denied
- [ ] Performance tests
  - Verify enforcement overhead is <10%
  - Verify startup time is <1s

---

### Phase 3: Integration & Orchestration (1-2 weeks)

#### **3.1 Unified API Layer**
```python
# Pseudo-API for how these talk together

class PubCastSecurityVault:
    def __init__(self, wallet: IterationWallet, oubliette: Oubliette):
        self.wallet = wallet
        self.oubliette = oubliette
    
    def intake_file(self, file_path: str, source_name: str):
        """
        Complete intake: untrusted file → vault
        1. Oubliette probe & classify
        2. Oubliette sanitize if needed
        3. Iteration Wallet custody
        """
        # Detection phase
        classification = self.oubliette.classify_file(file_path)
        
        if classification.trust_level == TrustLevel.SUSPICIOUS:
            # Quarantine, don't process
            return self.wallet.quarantine_file(file_path, "suspicious")
        
        # Intake phase
        self.wallet.add_file(file_path, source_name)
        
        # Sanitization phase (if needed)
        if classification.needs_transform:
            recipe = self.oubliette.find_recipe(classification.format)
            enforcement_result = self.oubliette.execute_recipe(
                file_path, recipe
            )
            if enforcement_result.success:
                sanitized = enforcement_result.artifacts[0]
                safe_file = self.wallet.add_file(
                    sanitized, 
                    source_name + "_sanitized",
                    parent_file_id=original_file_id
                )
                return safe_file
        
        return self.wallet.get_file(original_file_id)
```

#### **3.2 Configuration & Policy**
- [ ] Unified configuration file
  - Vault location, encryption key location
  - Enforcement level (MAXIMUM, STANDARD, BASIC, AUDIT_ONLY)
  - Resource limits per file type
  - Safe file types (auto-intake without sandboxing)
  - Suspicious patterns (trigger quarantine)
  - Retention policy (how long to keep removed files)
- [ ] Policy templates
  - Conservative: everything sandboxed, slow but safe
  - Balanced: known formats trusted, unknown sandboxed
  - Fast: only suspicious formats sandboxed

#### **3.3 User Interfaces**
- [ ] CLI tool for operations
  - `pubcast-vault add <file>` → intake
  - `pubcast-vault list [--removed]` → show files
  - `pubcast-vault restore <file_id>` → get specific version
  - `pubcast-vault audit [--recent] [--user=X]` → show audit trail
  - `pubcast-vault stats` → vault health
- [ ] Web dashboard
  - File browser (tree view of vault)
  - Audit log viewer with search
  - Statistics (file count, vault size, failed intakes, etc)
  - Settings (encryption, retention, enforcement level)
  - Status (enforcement capability detection, performance)
- [ ] Programmatic API
  - REST or gRPC endpoints
  - Authenticate with tokens
  - Integration with PubCast AI backend

#### **3.4 Monitoring & Alerting**
- [ ] Health checks
  - Vault database integrity
  - Enforcement capability available
  - Disk space for vault + backups
  - Audit log appending working
- [ ] Alerting rules
  - Checksum mismatch detected
  - Enforcement violation (timeout, memory, network)
  - Failed file add (permissions, disk full)
  - Suspicious file intake
  - Admin operation performed
- [ ] Metrics export
  - Prometheus format (or similar)
  - File count, vault size, operation latency
  - Enforcement execution time, violations
  - Audit log size

---

### Phase 4: Documentation & Deployment (1 week)

#### **4.1 Architecture Documentation**
- [ ] Threat model document (expanding this plan)
- [ ] Security guarantees document
  - What violations do we detect?
  - What do we guarantee vs. best-effort?
  - What are the limits? (forensic recovery of deleted files, etc)
- [ ] Operational runbook
  - Installation & setup
  - Key backup & recovery
  - Disaster recovery procedures
  - Performance tuning

#### **4.2 Code Documentation**
- [ ] API documentation (auto-generated from docstrings)
- [ ] Architecture guides (module responsibilities)
- [ ] Security guidelines (do's and don'ts when extending)

#### **4.3 Deployment**
- [ ] Docker image with hardened Python + dependencies
- [ ] Installation script (creates directories, sets permissions)
- [ ] Backup strategy for keys
- [ ] Update mechanism (signed updates only)

---

## PART 6: IMPLEMENTATION PRIORITY & DEPENDENCIES

### Critical Path (Start Here)

```
Week 1: Iteration Wallet Foundation
  ├─ 1.1 Database encryption (SQLCipher)
  ├─ 1.3 ACL & access control
  └─ 1.4 Audit logging infrastructure

Week 2: Oubliette Core Execution
  ├─ 2.1 Platform-specific enforcement (Linux first, then macOS/Windows)
  ├─ 2.2 Recipe system & audio transforms
  └─ 2.4 Enforcement log

Week 3: Integration
  ├─ 3.1 Unified API layer (intake_file)
  ├─ 3.2 Configuration & policy
  └─ 3.3 CLI tool (basic version)

Week 4: Testing & Hardening
  ├─ 1.2, 1.5, 1.6 (Iteration Wallet crypto & testing)
  ├─ 2.3, 2.5, 2.6 (Oubliette AI & network hardening)
  └─ Security testing suite

Week 5: Polish & Docs
  ├─ 3.4 Monitoring
  ├─ 4.1, 4.2 Documentation
  └─ 4.3 Deployment
```

### Non-Blocking (Parallel Work)

- Web dashboard (UI can iterate while backend hardens)
- Metrics & monitoring (add later, non-critical for v1)
- macOS/Windows enforcement (Linux sufficient for initial deployment, others follow)

---

## PART 7: KEY ARCHITECTURAL DECISIONS

### Decision 1: Separation of Concerns
**Why:** Iteration Wallet only stores and tracks files. Oubliette only executes and inspects. Neither trusts the other's input implicitly.

**Consequence:** If Iteration Wallet gets compromised, Oubliette is unaffected. If Oubliette returns bad data, Iteration Wallet catches it at checksum verification.

### Decision 2: Non-Destructive by Law
**Why:** Zero-delete doctrine. Every file state is recoverable.

**Consequence:** Backup copies grow vault size, but guarantees restoration. Staging garbage collection keeps overhead bounded.

### Decision 3: Immutable Audit Trail
**Why:** Security = accountability. Every operation logged and signed.

**Consequence:** Audit logs can be queried, but never modified. Admin tools exist, but leave traces. Insider threat detected post-facto.

### Decision 4: Capability-Based Enforcement
**Why:** Different systems have different isolation capabilities. Linux has cgroups, Windows has Job Objects, macOS has sandbox profiles.

**Consequence:** Code detects capabilities at runtime, uses best available. Graceful degradation. Always something working, even on restricted systems.

### Decision 5: Signed Recipes, Not Blind Execution
**Why:** Recipe = tested, approved transformation. Owner signs recipes. Prevents supply-chain attacks on codec updates.

**Consequence:** Adding new recipes requires review. Slower than auto-execute, but safer.

---

## PART 8: TESTING STRATEGY

### Unit Tests (Phase 1-2)
- Vault add/remove/restore operations
- Checksum computation & verification
- HMAC signing & verification
- Encryption/decryption
- Oubliette resource limit enforcement
- Platform-specific syscall restriction

### Integration Tests (Phase 3)
- Intake workflow: file in → vault out
- Corruption detection: modify vault file → detected
- Recovery: restore from backup → successful
- Multi-user: different users see own vault
- Concurrent: multiple processes adding files safely

### Security Tests (Phase 4)
- **Privilege Escalation:** Can low-privilege user modify vault? (No)
- **Tampering:** Can attacker modify vault file + corresponding DB record? (No—HMAC fails)
- **Forensics:** Can deleted file be recovered? (Yes, from backup until purged)
- **Escape:** Can sandboxed process break out? (No—enforcer kills it)
- **Poisoning:** Can AI output backdoor system? (No—output goes through intake workflow again)

### Performance Tests
- Intake speed: target <1s for typical podcast file (100MB)
- Query speed: list 100K files in <100ms
- Enforcement overhead: <10% CPU increase
- Backup copy speed: <2x file size copy time

---

## PART 9: SUCCESS CRITERIA

### At End of Phase 1 (Iteration Wallet)
- [ ] Database encrypted (zero plaintext secrets on disk)
- [ ] All file operations audited and immutable
- [ ] Corruption detection working (checksum mismatch → restore)
- [ ] ACL enforced (users can't see each other's files)
- [ ] 100+ test cases passing
- [ ] 0 security issues in code review

### At End of Phase 2 (Oubliette)
- [ ] Linux enforcement fully working (cgroups, seccomp)
- [ ] Audio recipes working (M4A/MP3 → WAV safely)
- [ ] Malware simulation tests passing
- [ ] Network isolation working
- [ ] 100+ test cases passing
- [ ] 0 security issues in code review

### At End of Phase 3 (Integration)
- [ ] Full intake workflow working
- [ ] CLI tool complete & usable
- [ ] API documented & tested
- [ ] Configuration system complete
- [ ] No broken integration points

### At End of Phase 4 (Deployment)
- [ ] Installation guide step-by-step tested
- [ ] Backup/recovery tested
- [ ] Monitoring alerts working
- [ ] Documentation complete
- [ ] Ready for staging deployment

---

## PART 10: LINGERING QUESTIONS & UNKNOWNS

### Architecture
1. Should Iteration Wallet keys be stored in the vault database or externally?
   - **Current guidance:** External (separate backup disk, password manager)
2. Should Oubliette recipes be vaulted by Iteration Wallet?
   - **Current guidance:** Yes, recipes are data too. Sign + version them
3. If Iteration Wallet detects corruption, should it auto-restore or alert admin?
   - **Current guidance:** Log + restore, but notify admin immediately

### Operations
4. How frequently should integrity checks run in the background?
   - **Current guidance:** Hourly for live vault, daily for archives
5. How long to keep audit logs?
   - **Current guidance:** 7 years (legal compliance for media companies)
6. What happens if backup disk runs out of space?
   - **Current guidance:** Alert admin, pause new intakes, don't lose data

### Threat Model
7. What if an admin maliciously deletes backup copies?
   - **Current guidance:** Detect via audit log, integrity fails, restore from archive
8. What if GPU/TPU is compromised during AI inference?
   - **Current guidance:** Oubliette can't isolate hardware directly, but output quarantined + re-scanned

---

## NEXT STEPS

1. **Read & Review:** You (the user) review this plan. Point out gaps, disagree with priorities, flag concerns.
2. **Code Sprint:** I start Phase 1 (Iteration Wallet hardening) this week.
3. **Weekly Syncs:** Every Monday, you see the running code. Test it, break it, demand changes.
4. **Iterate:** Feedback loop drives the implementation.

---

## FILES TO MINE FROM THIS HANDOFF

These files contain code, ideas, and warnings worth preserving:

### Iteration Wallet Lineage
- `IterationWallet_v3_8.zip/IW_Final_3sol/commit_guard.py` — interesting transaction guard logic
- `IterationWallet_v3_8.zip/IW_Final_3sol/diagnostics.py` — health check ideas
- `IterationWallet-Source/core/comparison_engine.py` — file comparison ideas
- `IterationWallet-Source/core/usb_protection.py` — external media protection ideas

### Oubliette Lineage
- `Oubliette v2.0 Architecture Enhancement.txt` — design thinking
- All three `oubliette_*.py` files across versions — enforcement patterns

### Integration Reference
- `oublette integration system(3).zip/PUBCAST_SYSTEM_AUDIT.md` — integration attempt notes

---

**End of Plan**

This is your blueprint. Let's build something beautiful and unbreakable.
