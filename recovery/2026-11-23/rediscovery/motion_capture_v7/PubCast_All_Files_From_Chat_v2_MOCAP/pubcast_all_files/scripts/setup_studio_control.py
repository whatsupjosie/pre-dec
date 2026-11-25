#!/usr/bin/env python3
"""
STUDIO CONTROL ROOM - QUICK START SETUP
========================================
This script helps you integrate the Studio Control Room into your PubCast AI system.

Usage:
    python setup_studio_control.py [--validate-only]

Options:
    --validate-only    Check environment without making changes
"""

import sys
import argparse
from pathlib import Path
from typing import List, Tuple


class Colors:
    """Terminal colors for pretty output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")


def print_success(text: str):
    print(f"{Colors.OKGREEN}✓{Colors.ENDC} {text}")


def print_error(text: str):
    print(f"{Colors.FAIL}✗{Colors.ENDC} {text}")


def print_warning(text: str):
    print(f"{Colors.WARNING}⚠{Colors.ENDC} {text}")


def print_info(text: str):
    print(f"{Colors.OKCYAN}ℹ{Colors.ENDC} {text}")


def check_dependencies() -> List[Tuple[str, bool, str]]:
    """Check if required Python packages are installed"""
    print_header("Checking Python Dependencies")
    
    results = []
    
    # Core dependencies (should already exist in PubCast AI)
    dependencies = [
        ("fastapi", "FastAPI framework for WebSocket server"),
        ("uvicorn", "ASGI server for FastAPI"),
        ("websockets", "WebSocket protocol support"),
        ("pydantic", "Data validation"),
        ("asyncio", "Async I/O (built-in)"),
    ]
    
    for package, description in dependencies:
        try:
            if package == "asyncio":
                import asyncio
                results.append((package, True, description))
            else:
                __import__(package)
                results.append((package, True, description))
            print_success(f"{package}: {description}")
        except ImportError:
            results.append((package, False, description))
            print_error(f"{package}: {description} - NOT INSTALLED")
    
    return results


def check_project_structure() -> bool:
    """Verify PubCast AI project structure"""
    print_header("Checking Project Structure")
    
    required_files = [
        ("pete_enhanced.py", "Pete Enhanced orchestrator"),
        ("pubcast_launcher.html", "PubCast launcher interface"),
    ]
    
    optional_files = [
        ("main.py", "FastAPI main application"),
        ("hub.py", "PubCast hub system"),
    ]
    
    all_found = True
    
    print_info("Checking for required PubCast AI files...")
    for filename, description in required_files:
        if Path(filename).exists():
            print_success(f"{filename}: {description}")
        else:
            print_error(f"{filename}: {description} - NOT FOUND")
            all_found = False
    
    print_info("\nChecking for optional files...")
    for filename, description in optional_files:
        if Path(filename).exists():
            print_success(f"{filename}: {description}")
        else:
            print_warning(f"{filename}: {description} - NOT FOUND (optional)")
    
    return all_found


def check_studio_control_files() -> bool:
    """Check if Studio Control Room files are present"""
    print_header("Checking Studio Control Room Files")
    
    files = [
        ("studio_control.py", "Studio Control backend module"),
        ("studio_websocket.py", "WebSocket handler"),
        ("studio_control_room.html", "Control Room interface"),
        ("STUDIO_CONTROL_INTEGRATION.md", "Integration guide"),
    ]
    
    all_found = True
    
    for filename, description in files:
        if Path(filename).exists():
            print_success(f"{filename}: {description}")
        else:
            print_error(f"{filename}: {description} - NOT FOUND")
            all_found = False
    
    return all_found


def create_modules_directory():
    """Create modules directory if it doesn't exist"""
    modules_dir = Path("modules")
    if not modules_dir.exists():
        print_info(f"Creating {modules_dir}/ directory...")
        modules_dir.mkdir(parents=True)
        print_success(f"Created {modules_dir}/")
        return True
    else:
        print_info(f"{modules_dir}/ already exists")
        return False


def create_static_directory():
    """Create static directory if it doesn't exist"""
    static_dir = Path("static")
    if not static_dir.exists():
        print_info(f"Creating {static_dir}/ directory...")
        static_dir.mkdir(parents=True)
        print_success(f"Created {static_dir}/")
        return True
    else:
        print_info(f"{static_dir}/ already exists")
        return False


def move_files_to_structure(validate_only: bool = False):
    """Move Studio Control files to proper locations"""
    print_header("Organizing Files")
    
    file_moves = [
        ("studio_control.py", "modules/studio_control.py"),
        ("studio_websocket.py", "modules/studio_websocket.py"),
        ("studio_control_room.html", "static/studio_control_room.html"),
    ]
    
    if validate_only:
        print_info("Validation mode - no files will be moved")
        return
    
    for src, dst in file_moves:
        src_path = Path(src)
        dst_path = Path(dst)
        
        if not src_path.exists():
            print_warning(f"{src} not found - skipping")
            continue
        
        if dst_path.exists():
            print_warning(f"{dst} already exists - skipping")
            continue
        
        # Ensure destination directory exists
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Move file
        src_path.rename(dst_path)
        print_success(f"Moved {src} → {dst}")


def generate_fastapi_integration_snippet():
    """Generate FastAPI integration code snippet"""
    print_header("FastAPI Integration Code")
    
    code = """
# Add this to your main.py or hub.py:

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pathlib import Path

from modules.studio_control import StudioControl
from modules.studio_websocket import create_studio_websocket_endpoint

# After initializing Pete Enhanced:
studio_control = StudioControl(
    hub=hub,
    pete=pete_enhanced,
    data_dir=Path("./data"),
    config={
        "dead_man_switch_interval": 60.0,
        "audio_update_interval": 0.1,
    }
)

# Create WebSocket handler
studio_ws_handler = create_studio_websocket_endpoint(studio_control)

# WebSocket endpoint
@app.websocket("/ws/studio")
async def websocket_studio(websocket: WebSocket):
    await studio_ws_handler.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await studio_ws_handler.handle_message(websocket, data)
    except WebSocketDisconnect:
        await studio_ws_handler.disconnect(websocket)

# Serve Studio Control Room
@app.get("/studio", response_class=HTMLResponse)
async def get_studio_control_room():
    with open("./static/studio_control_room.html") as f:
        return HTMLResponse(content=f.read())
"""
    
    print(f"{Colors.OKCYAN}{code}{Colors.ENDC}")
    print_info("Copy this code to integrate Studio Control Room with your FastAPI app")


def print_next_steps():
    """Print next steps for user"""
    print_header("Next Steps")
    
    steps = [
        "1. Review the integration code above",
        "2. Add the code to your main.py or hub.py",
        "3. Restart your PubCast AI server",
        "4. Navigate to http://localhost:8000/studio",
        "5. Test the preflight countdown (SPACE key)",
        "6. Review STUDIO_CONTROL_INTEGRATION.md for detailed setup",
    ]
    
    for step in steps:
        print(f"   {step}")
    
    print(f"\n{Colors.BOLD}Documentation:{Colors.ENDC}")
    print("   📖 Read STUDIO_CONTROL_INTEGRATION.md for complete integration guide")
    print("   🎛️ Test keyboard shortcuts: SPACE (start) | ESC (emergency)")
    
    print(f"\n{Colors.BOLD}Troubleshooting:{Colors.ENDC}")
    print("   • Check Python logs for WebSocket connection status")
    print("   • Check browser console for JavaScript errors")
    print("   • Verify FastAPI server is running on port 8000")


def main():
    parser = argparse.ArgumentParser(
        description="Studio Control Room Setup Script"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Check environment without making changes"
    )
    
    args = parser.parse_args()
    
    print(f"""
{Colors.HEADER}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║           STUDIO CONTROL ROOM QUICK START                ║
║           PubCast AI Production Control                  ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
{Colors.ENDC}
""")
    
    if args.validate_only:
        print_info("Running in VALIDATION MODE - no changes will be made\n")
    
    # Step 1: Check dependencies
    deps_results = check_dependencies()
    all_deps_ok = all(ok for _, ok, _ in deps_results)
    
    if not all_deps_ok:
        print_error("\nSome dependencies are missing!")
        print_info("Install missing packages with:")
        missing = [pkg for pkg, ok, _ in deps_results if not ok and pkg != "asyncio"]
        if missing:
            print(f"   pip install {' '.join(missing)}")
        print()
    
    # Step 2: Check project structure
    structure_ok = check_project_structure()
    
    if not structure_ok:
        print_warning("\nWarning: Some PubCast AI files not found")
        print_info("Make sure you're running this in your PubCast AI project directory")
        print()
    
    # Step 3: Check Studio Control files
    studio_files_ok = check_studio_control_files()
    
    if not studio_files_ok:
        print_error("\nStudio Control Room files are missing!")
        print_info("Make sure all Studio Control Room files are in the current directory")
        print()
        sys.exit(1)
    
    # Step 4: Create directories
    if not args.validate_only:
        print_header("Setting Up Directory Structure")
        create_modules_directory()
        create_static_directory()
        
        # Step 5: Move files
        move_files_to_structure(validate_only=args.validate_only)
    else:
        print_info("\nSkipping file organization (validation mode)")
    
    # Step 6: Show integration code
    generate_fastapi_integration_snippet()
    
    # Step 7: Print next steps
    print_next_steps()
    
    # Final status
    print()
    if all_deps_ok and structure_ok and studio_files_ok:
        print(f"{Colors.OKGREEN}{Colors.BOLD}✓ Setup Complete!{Colors.ENDC}")
        print(f"{Colors.OKGREEN}Studio Control Room is ready to integrate.{Colors.ENDC}\n")
    else:
        print(f"{Colors.WARNING}{Colors.BOLD}⚠ Setup Incomplete{Colors.ENDC}")
        print(f"{Colors.WARNING}Please resolve the issues above before continuing.{Colors.ENDC}\n")


if __name__ == "__main__":
    main()
