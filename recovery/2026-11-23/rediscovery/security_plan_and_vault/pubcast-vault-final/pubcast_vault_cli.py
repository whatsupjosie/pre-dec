#!/usr/bin/env python3
"""
pubcast-vault CLI
=================
Command-line interface for PubCast Security Vault operations.

Usage:
  pubcast-vault init <vault_root>
  pubcast-vault intake <file> [--source=NAME]
  pubcast-vault list [--project=NAME]
  pubcast-vault verify
  pubcast-vault audit [--recent]
  pubcast-vault stats
"""

import sys
import argparse
import json
from pathlib import Path
from typing import Optional
import getpass

# Import vault
sys.path.insert(0, str(Path(__file__).parent / "../phase3_integration"))
from pubcast_vault import PubCastSecurityVault

class PubCastCLI:
    """CLI interface."""
    
    def __init__(self):
        self.vault: Optional[PubCastSecurityVault] = None
        self.vault_root: Optional[Path] = None
        self._audio = self._load_audio()
    
    def _load_audio(self):
        """Load audio signature player if available."""
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from pubcast_vault_audio_signatures import AudioPlayer
            return AudioPlayer(Path(__file__).parent)
        except Exception:
            return None
    
    def _play(self, sound: str):
        """Play a named audio signature (vault_open, vault_close, success, error)."""
        if self._audio:
            try:
                self._audio.play(sound)
            except Exception:
                pass  # Audio is always optional
    
    def load_vault(self, vault_root: Path, password: Optional[str] = None) -> bool:
        """Load vault from disk."""
        if not password:
            password = getpass.getpass("Vault password: ")
        
        self.vault_root = Path(vault_root)
        self.vault = PubCastSecurityVault(self.vault_root)
        
        if self.vault.initialize(password):
            self._play("vault_open")
            return True
        self._play("error")
        return False
    
    def cmd_init(self, args):
        """Initialize new vault."""
        vault_root = Path(args.vault_root)
        password = getpass.getpass("Create vault password: ")
        password_verify = getpass.getpass("Verify password: ")
        
        if password != password_verify:
            print("✗ Passwords don't match")
            return False
        
        vault = PubCastSecurityVault(vault_root)
        if vault.initialize(password):
            self._play("vault_open")
            print(f"✓ Vault initialized at {vault_root}")
            print(f"✓ Owner: {vault.owner_user}")
            return True
        else:
            self._play("error")
            print("✗ Vault initialization failed")
            return False
    
    def cmd_intake(self, args):
        """Intake file into vault."""
        if not self.load_vault(self.vault_root or Path.cwd()):
            print("✗ Failed to load vault")
            return False
        
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"✗ File not found: {file_path}")
            return False
        
        source = args.source or "cli_intake"
        
        print(f"Intaking {file_path.name}...")
        status, file_id, details = self.vault.intake_file(file_path, source_name=source)
        
        print(f"✓ Status: {status.value}")
        if file_id:
            self._play("success")
            print(f"✓ File ID: {file_id}")
            print(f"✓ Classification: {details['classification']['class']}")
            if details.get('warnings'):
                print(f"⚠ Warnings: {', '.join(details['warnings'])}")
        else:
            self._play("error")
        
        return status.value == "safe"
    
    def cmd_list(self, args):
        """List vault files."""
        if not self.load_vault(self.vault_root or Path.cwd()):
            print("✗ Failed to load vault")
            return False
        
        files = self.vault.list_vault_files()
        
        if not files:
            print("(empty vault)")
            return True
        
        print(f"\n{'File ID':<36} {'Path':<40} {'Status':<15} {'Created':<20}")
        print("-" * 111)
        
        for f in files:
            print(f"{f['file_id']:<36} {Path(f['original_path']).name:<40} {f['status']:<15} {f['created_at']:<20}")
        
        print(f"\nTotal: {len(files)} files")
        return True
    
    def cmd_verify(self, args):
        """Verify vault integrity."""
        if not self.load_vault(self.vault_root or Path.cwd()):
            print("✗ Failed to load vault")
            return False
        
        print("Verifying vault integrity...")
        results = self.vault.verify_vault_integrity()
        
        print(f"✓ Total files: {results['total_files']}")
        print(f"✓ Verified: {results['verified']}")
        if results['corrupted'] > 0:
            print(f"⚠ Corrupted (restored): {results['corrupted']}")
        
        return results['corrupted'] == 0
    
    def cmd_stats(self, args):
        """Show vault statistics."""
        if not self.load_vault(self.vault_root or Path.cwd()):
            print("✗ Failed to load vault")
            return False
        
        stats = self.vault.get_intake_stats()
        
        print("\nIntake Statistics:")
        print(f"  Total attempts: {stats['total_attempts']}")
        print(f"  Successful: {stats['successful_intakes']}")
        print(f"  Quarantined: {stats['quarantined']}")
        print(f"  Failed: {stats['failed']}")
        print(f"  Success rate: {stats['success_rate']:.1f}%")
        
        return True
    
    def run(self, argv):
        """Run CLI."""
        parser = argparse.ArgumentParser(description="PubCast Security Vault CLI")
        
        # Global options
        parser.add_argument("--vault", default=".", help="Vault root directory")
        
        subparsers = parser.add_subparsers(dest="command", help="Command")
        
        # init command
        init_parser = subparsers.add_parser("init", help="Initialize new vault")
        init_parser.add_argument("vault_root", help="Vault root directory")
        
        # intake command
        intake_parser = subparsers.add_parser("intake", help="Intake file")
        intake_parser.add_argument("file", help="File path")
        intake_parser.add_argument("--source", help="Source name")
        
        # list command
        list_parser = subparsers.add_parser("list", help="List files")
        list_parser.add_argument("--project", help="Filter by project")
        
        # verify command
        verify_parser = subparsers.add_parser("verify", help="Verify integrity")
        
        # stats command
        stats_parser = subparsers.add_parser("stats", help="Show statistics")
        
        args = parser.parse_args(argv[1:])
        self.vault_root = Path(args.vault)
        
        # Route to command
        if args.command == "init":
            return self.cmd_init(args)
        elif args.command == "intake":
            return self.cmd_intake(args)
        elif args.command == "list":
            return self.cmd_list(args)
        elif args.command == "verify":
            return self.cmd_verify(args)
        elif args.command == "stats":
            return self.cmd_stats(args)
        else:
            parser.print_help()
            return False

if __name__ == "__main__":
    cli = PubCastCLI()
    success = cli.run(sys.argv)
    sys.exit(0 if success else 1)
