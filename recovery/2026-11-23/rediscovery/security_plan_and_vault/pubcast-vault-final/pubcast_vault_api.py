"""
PubCast Vault REST API — Hardened (Session 4)
=============================================
Production-grade HTTP API for vault operations.

Session 4 Hardening:
  - Real token authentication with expiry (24h default)
  - Per-IP + per-token rate limiting (in-memory sliding window)
  - Comprehensive input validation & sanitization
  - API call audit logging (every request logged)
  - HTTPS enforcement mode
  - Request size limits
  - Security response headers on all responses

Endpoints:
  POST   /api/v1/auth/login            - Authenticate and get token
  POST   /api/v1/auth/logout           - Invalidate token
  POST   /api/v1/vault/init            - Initialize vault
  POST   /api/v1/files/intake          - Intake file
  GET    /api/v1/files                 - List files
  GET    /api/v1/files/<file_id>       - Get file metadata
  POST   /api/v1/files/<file_id>/verify - Verify single file
  POST   /api/v1/vault/verify          - Verify full vault
  GET    /api/v1/vault/stats           - Get statistics
  GET    /api/v1/audit                 - Get audit logs (admin only)
  GET    /health                       - Health check (no auth)
"""

import json
import logging
import secrets
import hashlib
import time
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta
from functools import wraps
import uuid

try:
    from flask import Flask, request, jsonify, g
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

logger = logging.getLogger("pubcast_api")

TOKEN_EXPIRY_HOURS   = 24
RATE_LIMIT_PER_IP    = 100
RATE_LIMIT_PER_TOKEN = 200
RATE_LIMIT_WINDOW    = 60
MAX_FILE_SIZE_MB     = 500
MAX_JSON_SIZE_BYTES  = 64_000
MAX_FILENAME_LENGTH  = 255
SAFE_FILENAME_RE     = re.compile(r'^[\w\-. ]+$')

SECURITY_HEADERS = {
    "X-Content-Type-Options":  "nosniff",
    "X-Frame-Options":         "DENY",
    "X-XSS-Protection":        "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'none'",
    "Cache-Control":           "no-store",
    "Pragma":                  "no-cache",
    "Referrer-Policy":         "no-referrer",
}


class APIResponse:
    @staticmethod
    def success(data: Any = None, message: str = "OK") -> Dict:
        return {
            "status": "success",
            "message": message,
            "data": data,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    @staticmethod
    def error(error: str, code: str = "ERROR", status_code: int = 400):
        body = {
            "status": "error",
            "error": error,
            "code": code,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        if HAS_FLASK:
            resp = jsonify(body)
            for k, v in SECURITY_HEADERS.items():
                resp.headers[k] = v
            return resp, status_code
        return body, status_code


class RateLimiter:
    """Thread-safe sliding window rate limiter."""

    def __init__(self):
        self._buckets: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, key: str, limit: int, window_secs: int = 60) -> Tuple[bool, int]:
        now = time.time()
        cutoff = now - window_secs
        with self._lock:
            ts = self._buckets.get(key, [])
            ts = [t for t in ts if t > cutoff]
            if len(ts) >= limit:
                self._buckets[key] = ts
                return False, 0
            ts.append(now)
            self._buckets[key] = ts
            return True, limit - len(ts)

    def cleanup(self):
        now = time.time()
        cutoff = now - RATE_LIMIT_WINDOW
        with self._lock:
            stale = [k for k, ts in self._buckets.items()
                     if not any(t > cutoff for t in ts)]
            for k in stale:
                del self._buckets[k]


class TokenManager:
    """Real token-based auth with expiry and PBKDF2 password validation."""

    def __init__(self, expiry_hours: int = TOKEN_EXPIRY_HOURS):
        self._tokens: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        self._expiry = timedelta(hours=expiry_hours)
        self._vault_password_hash: Optional[str] = None
        self._auth_salt = b"pubcast_vault_api_auth_v1"

    def set_vault_password(self, password: str):
        self._vault_password_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), self._auth_salt, iterations=100_000
        ).hex()

    def login(self, password: str, user: str = "default") -> Optional[str]:
        if not self._vault_password_hash:
            logger.warning("API: login attempted before password set")
            return None
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), self._auth_salt, iterations=100_000
        ).hex()
        if not secrets.compare_digest(candidate, self._vault_password_hash):
            logger.warning(f"API: failed login for user '{user}'")
            return None
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        record = {
            "user": user,
            "role": "admin" if user in ("root", "admin", "default") else "reader",
            "created": datetime.utcnow().isoformat(),
            "expires": (datetime.utcnow() + self._expiry).isoformat(),
            "token_id": str(uuid.uuid4())
        }
        with self._lock:
            self._tokens[token_hash] = record
        logger.info(f"API: token issued for '{user}' expires {record['expires']}")
        return raw_token

    def validate(self, raw_token: str) -> Optional[Dict]:
        if not raw_token:
            return None
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        with self._lock:
            record = self._tokens.get(token_hash)
        if not record:
            return None
        if datetime.utcnow() > datetime.fromisoformat(record["expires"]):
            with self._lock:
                self._tokens.pop(token_hash, None)
            return None
        return record

    def logout(self, raw_token: str) -> bool:
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        with self._lock:
            existed = token_hash in self._tokens
            self._tokens.pop(token_hash, None)
        return existed

    def purge_expired(self):
        now = datetime.utcnow()
        with self._lock:
            expired = [h for h, r in self._tokens.items()
                       if datetime.fromisoformat(r["expires"]) < now]
            for h in expired:
                del self._tokens[h]


class InputValidator:
    @staticmethod
    def validate_password(pw: Any) -> Tuple[bool, str]:
        if not isinstance(pw, str):
            return False, "Password must be a string"
        if len(pw) < 8:
            return False, "Password must be at least 8 characters"
        if len(pw) > 1024:
            return False, "Password too long"
        return True, ""

    @staticmethod
    def validate_filename(fn: Any) -> Tuple[bool, str]:
        if not isinstance(fn, str) or not fn.strip():
            return False, "Invalid filename"
        if len(fn) > MAX_FILENAME_LENGTH:
            return False, f"Filename too long (max {MAX_FILENAME_LENGTH})"
        safe = Path(fn).name
        if safe != fn:
            return False, "Filename cannot contain path separators"
        if not SAFE_FILENAME_RE.match(safe):
            return False, "Filename contains disallowed characters"
        return True, ""

    @staticmethod
    def validate_file_id(fid: Any) -> Tuple[bool, str]:
        if not isinstance(fid, str):
            return False, "File ID must be a string"
        if not re.match(r'^[a-zA-Z0-9_\-]{1,64}$', fid):
            return False, "Invalid file ID format"
        return True, ""

    @staticmethod
    def validate_source(src: Any) -> Tuple[bool, str]:
        if not isinstance(src, str):
            return False, "Source must be a string"
        if len(src) > 128 or not re.match(r'^[a-zA-Z0-9_\-. ]+$', src):
            return False, "Invalid source"
        return True, ""

    @staticmethod
    def safe_int(val: Any, default: int, min_val: int, max_val: int) -> int:
        try:
            return max(min_val, min(max_val, int(val)))
        except (TypeError, ValueError):
            return default


class PubCastVaultAPI:
    """
    Hardened REST API for PubCast Security Vault.

    Session 4 additions vs Session 3:
      - Real PBKDF2 password auth with 24h expiring tokens
      - Per-IP (100 req/min) + per-token (200 req/min) rate limiting
      - Full input validation on all endpoints
      - Security headers (CSP, HSTS, nosniff, etc.) on every response
      - Request size limits (500 MB file, 64 KB JSON)
      - Background token/bucket cleanup thread
      - Audit log endpoint reads decrypted vault logs (admin only)
    """

    def __init__(self, vault=None, port: int = 5000, https_only: bool = False):
        self.vault = vault
        self.port = port
        self.https_only = https_only
        self.tokens = TokenManager()
        self.rate_limiter = RateLimiter()
        self.validator = InputValidator()
        self._cleanup = threading.Thread(
            target=self._background_cleanup, daemon=True
        )
        self._cleanup.start()

        if HAS_FLASK:
            self.app = Flask("pubcast-vault-api")
            self.app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE_MB * 1024 * 1024
            self._setup_middleware()
            self._setup_routes()
            logger.info(f"Hardened API initialized on port {port}")
        else:
            logger.warning("Flask not installed - REST API disabled")
            self.app = None

    def _setup_middleware(self):
        @self.app.before_request
        def before_each():
            g.start_time = time.time()
            g.request_id = str(uuid.uuid4())[:8]
            if self.https_only and not request.is_secure:
                return APIResponse.error("HTTPS required", "HTTPS_REQUIRED", 403)
            if request.content_type == "application/json":
                if len(request.get_data()) > MAX_JSON_SIZE_BYTES:
                    return APIResponse.error(
                        f"Body too large (max {MAX_JSON_SIZE_BYTES} bytes)",
                        "BODY_TOO_LARGE", 413
                    )
            ip = request.remote_addr or "unknown"
            allowed, _ = self.rate_limiter.is_allowed(
                f"ip:{ip}", RATE_LIMIT_PER_IP, RATE_LIMIT_WINDOW
            )
            if not allowed:
                return APIResponse.error(
                    "Rate limit exceeded. Retry in 60s.",
                    "RATE_LIMIT_EXCEEDED", 429
                )

        @self.app.after_request
        def after_each(response):
            for k, v in SECURITY_HEADERS.items():
                response.headers[k] = v
            duration = time.time() - getattr(g, "start_time", time.time())
            logger.info(
                f"[{getattr(g, 'request_id', '?')}] "
                f"{request.method} {request.path} "
                f"-> {response.status_code} ({duration*1000:.1f}ms)"
            )
            return response

    def _require_auth(self, f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return APIResponse.error(
                    "Authorization: Bearer <token> required",
                    "AUTH_REQUIRED", 401
                )
            raw = auth[7:].strip()
            record = self.tokens.validate(raw)
            if not record:
                return APIResponse.error(
                    "Invalid or expired token. Please log in again.",
                    "TOKEN_INVALID", 401
                )
            allowed, _ = self.rate_limiter.is_allowed(
                f"token:{record['token_id']}", RATE_LIMIT_PER_TOKEN, RATE_LIMIT_WINDOW
            )
            if not allowed:
                return APIResponse.error(
                    "Token rate limit exceeded.", "RATE_LIMIT_EXCEEDED", 429
                )
            g.user = record["user"]
            g.role = record["role"]
            g.token_id = record["token_id"]
            return f(*args, **kwargs)
        return decorated

    def _require_admin(self, f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if getattr(g, "role", "") != "admin":
                return APIResponse.error("Admin role required", "FORBIDDEN", 403)
            return f(*args, **kwargs)
        return decorated

    def _setup_routes(self):
        ra = self._require_auth
        raa = self._require_admin

        @self.app.route("/health", methods=["GET"])
        def health():
            return jsonify(APIResponse.success({
                "status": "healthy",
                "vault_ready": self.vault is not None,
                "version": "session4-hardened"
            }))

        @self.app.route("/api/v1/auth/login", methods=["POST"])
        def login():
            try:
                data = request.get_json(silent=True) or {}
                password = data.get("password")
                user = str(data.get("user", "default"))[:64]
                valid, msg = self.validator.validate_password(password)
                if not valid:
                    return APIResponse.error(msg, "INVALID_INPUT")
                token = self.tokens.login(password, user)
                if not token:
                    time.sleep(0.3)  # Slow down brute force
                    return APIResponse.error("Authentication failed", "AUTH_FAILED", 401)
                return jsonify(APIResponse.success({
                    "token": token,
                    "expires_in_hours": TOKEN_EXPIRY_HOURS,
                    "user": user
                }, "Login successful"))
            except Exception as e:
                logger.error(f"Login error: {e}")
                return APIResponse.error("Login failed", "LOGIN_ERROR")

        @self.app.route("/api/v1/auth/logout", methods=["POST"])
        @ra
        def logout():
            auth = request.headers.get("Authorization", "")
            raw = auth[7:].strip() if auth.startswith("Bearer ") else ""
            self.tokens.logout(raw)
            return jsonify(APIResponse.success(None, "Logged out"))

        @self.app.route("/api/v1/vault/init", methods=["POST"])
        def init_vault():
            try:
                data = request.get_json(silent=True) or {}
                password = data.get("password")
                valid, msg = self.validator.validate_password(password)
                if not valid:
                    return APIResponse.error(msg, "INVALID_INPUT")
                vault_path = str(Path(str(data.get("vault_path", "/tmp/pubcast_vault"))).resolve())
                self.tokens.set_vault_password(password)
                return jsonify(APIResponse.success({
                    "vault_path": vault_path,
                    "status": "initialized"
                }, "Vault initialized"))
            except Exception as e:
                return APIResponse.error(str(e), "INIT_FAILED")

        @self.app.route("/api/v1/files/intake", methods=["POST"])
        @ra
        def intake_file():
            try:
                if "file" not in request.files:
                    return APIResponse.error("No file provided", "NO_FILE")
                file = request.files["file"]
                filename = file.filename or ""
                valid, msg = self.validator.validate_filename(filename)
                if not valid:
                    return APIResponse.error(msg, "INVALID_FILENAME")
                source = request.form.get("source", "api")
                valid, msg = self.validator.validate_source(source)
                if not valid:
                    return APIResponse.error(msg, "INVALID_SOURCE")
                if not self.vault:
                    return APIResponse.error("Vault not initialized", "VAULT_NOT_READY", 503)
                suffix = Path(filename).suffix[:10]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="intake_") as tmp:
                    file.save(tmp.name)
                    tmp_path = Path(tmp.name)
                try:
                    file_id = self.vault.intake_file(tmp_path, source=source)
                    return jsonify(APIResponse.success({
                        "file_id": file_id,
                        "filename": filename,
                        "source": source,
                        "intake_user": g.user
                    }, "File intake successful"))
                finally:
                    try:
                        tmp_path.unlink(missing_ok=True)
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Intake error: {e}")
                return APIResponse.error(str(e), "INTAKE_FAILED")

        @self.app.route("/api/v1/files", methods=["GET"])
        @ra
        def list_files():
            try:
                if not self.vault:
                    return APIResponse.error("Vault not initialized", "VAULT_NOT_READY", 503)
                files = self.vault.list_vault_files(user=g.user)
                return jsonify(APIResponse.success({"files": files, "count": len(files)}))
            except Exception as e:
                return APIResponse.error(str(e), "LIST_FAILED")

        @self.app.route("/api/v1/files/<file_id>", methods=["GET"])
        @ra
        def get_file(file_id):
            valid, msg = self.validator.validate_file_id(file_id)
            if not valid:
                return APIResponse.error(msg, "INVALID_FILE_ID")
            try:
                if not self.vault:
                    return APIResponse.error("Vault not initialized", "VAULT_NOT_READY", 503)
                files = self.vault.list_vault_files(user=g.user)
                match = next((f for f in files if f.get("file_id") == file_id), None)
                if not match:
                    return APIResponse.error(f"File '{file_id}' not found", "NOT_FOUND", 404)
                return jsonify(APIResponse.success({"file": match}))
            except Exception as e:
                return APIResponse.error(str(e), "GET_FAILED")

        @self.app.route("/api/v1/files/<file_id>/verify", methods=["POST"])
        @ra
        def verify_file(file_id):
            valid, msg = self.validator.validate_file_id(file_id)
            if not valid:
                return APIResponse.error(msg, "INVALID_FILE_ID")
            try:
                if not self.vault:
                    return APIResponse.error("Vault not initialized", "VAULT_NOT_READY", 503)
                ok, detail = self.vault.verify_file_integrity(file_id, user=g.user)
                return jsonify(APIResponse.success({
                    "file_id": file_id, "verified": ok, "detail": detail
                }))
            except Exception as e:
                return APIResponse.error(str(e), "VERIFY_FAILED")

        @self.app.route("/api/v1/vault/verify", methods=["POST"])
        @ra
        def verify_vault():
            try:
                if not self.vault:
                    return APIResponse.error("Vault not initialized", "VAULT_NOT_READY", 503)
                ok, msg = self.vault.verify_vault_integrity(user=g.user)
                return jsonify(APIResponse.success({"verified": ok, "message": msg}))
            except Exception as e:
                return APIResponse.error(str(e), "VERIFY_FAILED")

        @self.app.route("/api/v1/vault/stats", methods=["GET"])
        @ra
        def get_stats():
            try:
                if not self.vault:
                    return APIResponse.error("Vault not initialized", "VAULT_NOT_READY", 503)
                stats = self.vault.get_intake_stats()
                stats["api"] = {
                    "active_tokens": len(self.tokens._tokens),
                    "rate_limit_buckets": len(self.rate_limiter._buckets)
                }
                return jsonify(APIResponse.success({"stats": stats}))
            except Exception as e:
                return APIResponse.error(str(e), "STATS_FAILED")

        @self.app.route("/api/v1/audit", methods=["GET"])
        @ra
        @raa
        def get_audit():
            try:
                if not self.vault:
                    return APIResponse.error("Vault not initialized", "VAULT_NOT_READY", 503)
                limit = self.validator.safe_int(
                    request.args.get("limit"), default=100, min_val=1, max_val=1000
                )
                try:
                    entries = self.vault.vault.read_audit_log(user=g.user, limit=limit)
                except AttributeError:
                    entries = []
                return jsonify(APIResponse.success({
                    "audit_logs": entries, "count": len(entries), "limit": limit
                }))
            except PermissionError as e:
                return APIResponse.error(str(e), "FORBIDDEN", 403)
            except Exception as e:
                return APIResponse.error(str(e), "AUDIT_FAILED")

        @self.app.errorhandler(404)
        def not_found(e):
            return APIResponse.error("Endpoint not found", "NOT_FOUND", 404)

        @self.app.errorhandler(413)
        def too_large(e):
            return APIResponse.error(
                f"File too large (max {MAX_FILE_SIZE_MB} MB)", "FILE_TOO_LARGE", 413
            )

        @self.app.errorhandler(500)
        def server_error(e):
            logger.error(f"Unhandled error: {e}")
            return APIResponse.error("Internal server error", "SERVER_ERROR", 500)

    def _background_cleanup(self):
        while True:
            time.sleep(300)
            try:
                self.tokens.purge_expired()
                self.rate_limiter.cleanup()
            except Exception as e:
                logger.warning(f"Cleanup error: {e}")

    def run(self, debug: bool = False, ssl_context=None):
        if not self.app:
            logger.error("Flask not available")
            return
        logger.info(f"Starting Hardened PubCast Vault API on port {self.port}")
        self.app.run(
            host="127.0.0.1",
            port=self.port,
            debug=debug,
            use_reloader=False,
            ssl_context=ssl_context
        )


def create_api_server(vault=None, port: int = 5000) -> PubCastVaultAPI:
    return PubCastVaultAPI(vault, port)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    if not HAS_FLASK:
        print("Flask not installed: pip install flask")
    else:
        api = PubCastVaultAPI(port=5000)
        print("Hardened API ready. Call api.run() to start.")
