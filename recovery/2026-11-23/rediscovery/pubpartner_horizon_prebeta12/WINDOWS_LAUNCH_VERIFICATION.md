# Windows Launch Verification

## Verified Here

- Windows `.bat` and PowerShell launchers point to the project launcher rather than Bash.
- The Python launcher prefers/creates project-local environment behavior and performs preflight before serving.
- Quoting/path handling was exercised from a copied project path containing spaces; preflight passed.
- Launcher supports `--no-browser`, custom port and custom data directory.
- Restart probe showed termination and relaunch did not require recreating owner state or secrets.
- No registry, service, driver, firewall, PATH, partition, BIOS or other system-core changes were made.

## Not Verified Here

This execution environment is Linux, not Windows 10. Native PowerShell policy behavior, `cmd.exe` quoting, browser opening, Windows Defender prompts, and process-tree cleanup under the Windows kernel were not directly exercised. The wrappers are therefore **statically verified and portable-path tested**, not certified native-Windows-tested.

## Recommended Native Acceptance Check

On Windows 10, extract to a path containing spaces, run `RUN_PUBPARTNER_WINDOWS.bat`, complete owner setup, restart it, verify an old session, and confirm no duplicate `python.exe` server remains after closing. Record the exact PowerShell output before any public-release claim.
