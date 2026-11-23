#!/usr/bin/env python3
"""
PubCast Vault TLS/HTTPS Setup
=============================
Generate self-signed certificates and configure HTTPS for REST API.

For production, you should:
  1. Use proper certificates from a CA (Let's Encrypt, etc.)
  2. Never commit certificates to version control
  3. Protect private keys with proper permissions (0400)

This script helps with development and small deployments.

Usage:
    python pubcast_vault_tls_setup.py generate --cert-dir ./certs
    python pubcast_vault_tls_setup.py --help
"""

import argparse
import sys
import subprocess
from pathlib import Path
from typing import Optional, Tuple


def has_openssl() -> bool:
    """Check if openssl is available."""
    try:
        subprocess.run(["openssl", "version"], capture_output=True, timeout=2)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def generate_self_signed_cert(
    cert_dir: Path,
    cn: str = "localhost",
    days: int = 365,
    keysize: int = 2048
) -> Tuple[bool, str]:
    """
    Generate a self-signed TLS certificate.
    
    Args:
        cert_dir: Directory to store cert and key
        cn: Common name (hostname)
        days: Validity period
        keysize: RSA key size
    
    Returns:
        (success: bool, message: str)
    """
    if not has_openssl():
        return False, "OpenSSL not found. Install with: apt-get install openssl"
    
    cert_dir = Path(cert_dir)
    cert_dir.mkdir(parents=True, exist_ok=True)
    
    cert_file = cert_dir / "pubcast_vault.crt"
    key_file = cert_dir / "pubcast_vault.key"
    
    if cert_file.exists() and key_file.exists():
        return True, f"Certificate already exists at {cert_file}"
    
    try:
        # Generate self-signed cert valid for N days
        cmd = [
            "openssl", "req", "-x509", "-newkey",
            f"rsa:{keysize}",
            "-keyout", str(key_file),
            "-out", str(cert_file),
            "-days", str(days),
            "-nodes",
            "-subj", f"/C=US/ST=CA/L=Local/O=PubCast/CN={cn}"
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        
        if result.returncode != 0:
            error = result.stderr.decode()
            return False, f"Certificate generation failed: {error}"
        
        # Secure the private key
        key_file.chmod(0o400)
        cert_file.chmod(0o444)
        
        return True, f"""
✓ Self-signed certificate generated:
  Certificate: {cert_file}
  Private Key: {key_file}
  Valid for: {days} days
  
⚠️  This is a self-signed certificate. For production:
  1. Use certificates from a trusted CA
  2. Do NOT commit certificates to git
  3. Protect keys with proper file permissions
  
To use with the API:
  api = PubCastVaultAPI(vault, port=5000)
  api.run(ssl_context=('pubcast_vault.crt', 'pubcast_vault.key'))
"""
    
    except subprocess.TimeoutExpired:
        return False, "Certificate generation timed out"
    except Exception as e:
        return False, f"Certificate generation error: {e}"


def create_systemd_service(
    vault_root: Path,
    api_port: int = 5000,
    user: str = "pubcast-vault",
    output_file: Optional[Path] = None
) -> str:
    """Generate systemd service file for production deployment."""
    
    service_content = f"""[Unit]
Description=PubCast Security Vault REST API
Documentation=https://github.com/pubcast/vault
After=network.target
Wants=pubcast-vault-monitor.service

[Service]
Type=notify
User={user}
Group={user}

# Working directory and environment
WorkingDirectory={vault_root}
Environment="VAULT_ROOT={vault_root}"
Environment="API_PORT={api_port}"
Environment="PYTHONUNBUFFERED=1"

# Startup command
ExecStart=/usr/bin/python3 -c \\
  "import sys; sys.path.insert(0, '{vault_root}'); \\
   from pubcast_vault_api import PubCastVaultAPI; \\
   from phase3_integration.pubcast_vault import PubCastSecurityVault; \\
   from pathlib import Path; \\
   vault = PubCastSecurityVault(Path('{vault_root}')); \\
   api = PubCastVaultAPI(vault, port={api_port}); \\
   api.run(ssl_context=('{vault_root}/certs/pubcast_vault.crt', \\
                         '{vault_root}/certs/pubcast_vault.key'))"

# Restart policy
Restart=on-failure
RestartSec=10
StartLimitInterval=60
StartLimitBurst=3

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths={vault_root}
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictRealtime=true
RestrictNamespaces=true
LockPersonality=true

# Resource limits
MemoryLimit=2G
TasksMax=10
CPUQuota=50%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pubcast-vault-api

[Install]
WantedBy=multi-user.target
"""
    
    if output_file:
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(service_content)
        return f"Service file written to {output_file}"
    
    return service_content


def create_monitoring_service(vault_root: Path, output_file: Optional[Path] = None) -> str:
    """Generate systemd service for background integrity monitoring."""
    
    service_content = f"""[Unit]
Description=PubCast Vault Background Integrity Monitor
Documentation=https://github.com/pubcast/vault
After=pubcast-vault-api.service
Wants=pubcast-vault-api.service

[Service]
Type=simple
User=pubcast-vault
Group=pubcast-vault

WorkingDirectory={vault_root}
Environment="VAULT_ROOT={vault_root}"

ExecStart=/usr/bin/python3 -c \\
  "import sys, logging; sys.path.insert(0, '{vault_root}'); \\
   logging.basicConfig(level=logging.INFO); \\
   from phase3_integration.pubcast_vault import PubCastSecurityVault; \\
   from phase1_iteration_wallet.integrity_checker import add_background_checking_to_vault; \\
   from pathlib import Path; \\
   vault = PubCastSecurityVault(Path('{vault_root}')); \\
   add_background_checking_to_vault(vault); \\
   print('Background monitor started'); \\
   import time; [time.sleep(3600) for _ in range(999)]"

Restart=always
RestartSec=30

StandardOutput=journal
StandardError=journal
SyslogIdentifier=pubcast-vault-monitor

[Install]
WantedBy=multi-user.target
"""
    
    if output_file:
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(service_content)
        return f"Monitor service file written to {output_file}"
    
    return service_content


def main():
    parser = argparse.ArgumentParser(
        description="PubCast Vault TLS and systemd setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate self-signed certificate
  python pubcast_vault_tls_setup.py generate --cert-dir ./certs
  
  # Create systemd service file
  python pubcast_vault_tls_setup.py systemd \\
    --vault-root /var/lib/pubcast-vault \\
    --output /etc/systemd/system/pubcast-vault-api.service
  
  # Create monitoring service
  python pubcast_vault_tls_setup.py monitor \\
    --vault-root /var/lib/pubcast-vault \\
    --output /etc/systemd/system/pubcast-vault-monitor.service
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Generate certificate
    gen = subparsers.add_parser("generate", help="Generate self-signed certificate")
    gen.add_argument("--cert-dir", required=True, help="Directory for cert and key")
    gen.add_argument("--cn", default="localhost", help="Common name (hostname)")
    gen.add_argument("--days", type=int, default=365, help="Validity period (days)")
    gen.add_argument("--keysize", type=int, default=2048, help="RSA key size")
    
    # Systemd service
    svc = subparsers.add_parser("systemd", help="Generate systemd service file")
    svc.add_argument("--vault-root", required=True, help="Vault root directory")
    svc.add_argument("--port", type=int, default=5000, help="API port")
    svc.add_argument("--user", default="pubcast-vault", help="System user")
    svc.add_argument("--output", help="Output file (default: print to stdout)")
    
    # Monitoring service
    mon = subparsers.add_parser("monitor", help="Generate monitoring service file")
    mon.add_argument("--vault-root", required=True, help="Vault root directory")
    mon.add_argument("--output", help="Output file (default: print to stdout)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == "generate":
        ok, msg = generate_self_signed_cert(
            Path(args.cert_dir),
            cn=args.cn,
            days=args.days,
            keysize=args.keysize
        )
        print(msg)
        return 0 if ok else 1
    
    elif args.command == "systemd":
        content = create_systemd_service(
            Path(args.vault_root),
            api_port=args.port,
            user=args.user,
            output_file=Path(args.output) if args.output else None
        )
        if not args.output:
            print(content)
        else:
            print(f"✓ Service file created")
        return 0
    
    elif args.command == "monitor":
        content = create_monitoring_service(
            Path(args.vault_root),
            output_file=Path(args.output) if args.output else None
        )
        if not args.output:
            print(content)
        else:
            print(f"✓ Monitor service file created")
        return 0
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
