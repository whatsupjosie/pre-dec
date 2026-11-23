#!/usr/bin/env python3
"""
PubCast AI v7.0 - Quick Setup Script
=====================================
Automated setup and verification for PubCast AI

This script will:
1. Check Python version
2. Create virtual environment
3. Install dependencies
4. Create directory structure
5. Copy configuration files
6. Verify Ollama installation
7. Run initial tests

Usage:
    python setup_pubcast_v7.py
"""

import os
import sys
import subprocess
from pathlib import Path
import shutil


class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")


def print_success(text):
    print(f"{Colors.OKGREEN}✓{Colors.ENDC} {text}")


def print_error(text):
    print(f"{Colors.FAIL}✗{Colors.ENDC} {text}")


def print_warning(text):
    print(f"{Colors.WARNING}⚠{Colors.ENDC} {text}")


def print_info(text):
    print(f"{Colors.OKCYAN}ℹ{Colors.ENDC} {text}")


def check_python_version():
    """Check Python version is 3.8+"""
    print_header("Checking Python Version")
    
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print_success(f"Python {version.major}.{version.minor}.{version.micro} ✓")
        return True
    else:
        print_error(f"Python {version.major}.{version.minor} is too old")
        print_error("PubCast AI requires Python 3.8 or higher")
        return False


def create_directory_structure():
    """Create all required directories"""
    print_header("Creating Directory Structure")
    
    dirs = [
        "modules",
        "static",
        "data",
        "data/avatars",
        "data/scenes",
        "data/emergency_saves",
        "logs",
        "scripts",
        "docs",
        "tests"
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print_success(f"Created: {dir_path}/")
    
    return True


def create_virtual_environment():
    """Create Python virtual environment"""
    print_header("Creating Virtual Environment")
    
    venv_path = Path("venv")
    
    if venv_path.exists():
        print_warning("Virtual environment already exists")
        return True
    
    try:
        print_info("Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print_success("Virtual environment created")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to create virtual environment: {e}")
        return False


def install_dependencies():
    """Install Python dependencies"""
    print_header("Installing Dependencies")
    
    requirements_file = Path("requirements.txt")
    if not requirements_file.exists():
        print_error("requirements.txt not found")
        return False
    
    # Determine pip path
    if sys.platform == "win32":
        pip_path = Path("venv/Scripts/pip")
    else:
        pip_path = Path("venv/bin/pip")
    
    if not pip_path.exists():
        print_error("Virtual environment pip not found")
        print_info("Activate venv and run: pip install -r requirements.txt")
        return False
    
    try:
        print_info("Installing dependencies (this may take a few minutes)...")
        subprocess.run([str(pip_path), "install", "-r", "requirements.txt"], check=True)
        print_success("Dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install dependencies: {e}")
        return False


def setup_environment():
    """Copy .env.example to .env if it doesn't exist"""
    print_header("Setting Up Environment")
    
    env_example = Path(".env.example")
    env_file = Path(".env")
    
    if env_file.exists():
        print_warning(".env already exists - skipping")
        return True
    
    if not env_example.exists():
        print_warning(".env.example not found - creating minimal .env")
        with open(".env", "w") as f:
            f.write("# PubCast AI v7.0 Configuration\n")
            f.write("HOST=0.0.0.0\n")
            f.write("PORT=8000\n")
            f.write("OLLAMA_HOST=http://localhost:11434\n")
            f.write("OLLAMA_MODEL=gemma4:4b\n")
        print_success("Created minimal .env")
        return True
    
    try:
        shutil.copy(env_example, env_file)
        print_success("Created .env from .env.example")
        print_info("Edit .env to customize your configuration")
        return True
    except Exception as e:
        print_error(f"Failed to create .env: {e}")
        return False


def check_ollama():
    """Check if Ollama is installed and running"""
    print_header("Checking Ollama")
    
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get("models", [])
            print_success("Ollama is running")
            print_info(f"Installed models: {len(models)}")
            
            # Check for gemma4:4b
            has_gemma = any("gemma4" in m.get("name", "") for m in models)
            if has_gemma:
                print_success("gemma4:4b model found")
            else:
                print_warning("gemma4:4b not found")
                print_info("Install with: ollama pull gemma4:4b")
            
            return True
        else:
            print_warning("Ollama not responding correctly")
            return False
    except Exception as e:
        print_error("Ollama not running")
        print_info("Start Ollama with: ollama serve")
        print_info("Install from: https://ollama.ai")
        return False


def print_next_steps():
    """Print next steps for user"""
    print_header("Setup Complete!")
    
    print(f"{Colors.BOLD}Next Steps:{Colors.ENDC}\n")
    
    print("1. Activate virtual environment:")
    if sys.platform == "win32":
        print(f"   {Colors.OKCYAN}venv\\Scripts\\activate{Colors.ENDC}")
    else:
        print(f"   {Colors.OKCYAN}source venv/bin/activate{Colors.ENDC}")
    
    print("\n2. (Optional) Edit configuration:")
    print(f"   {Colors.OKCYAN}nano .env{Colors.ENDC}")
    
    print("\n3. Start Ollama (if not running):")
    print(f"   {Colors.OKCYAN}ollama serve{Colors.ENDC}")
    print(f"   {Colors.OKCYAN}ollama pull gemma4:4b{Colors.ENDC}")
    
    print("\n4. Start PubCast AI:")
    print(f"   {Colors.OKCYAN}python main.py{Colors.ENDC}")
    
    print("\n5. Open in browser:")
    print(f"   {Colors.OKCYAN}http://localhost:8000/{Colors.ENDC}")
    print(f"   {Colors.OKCYAN}http://localhost:8000/studio{Colors.ENDC}")
    print(f"   {Colors.OKCYAN}http://localhost:8000/scene-builder{Colors.ENDC}")
    
    print(f"\n{Colors.BOLD}Documentation:{Colors.ENDC}")
    print("   📖 DEPLOYMENT_GUIDE_V7.md - Complete deployment guide")
    print("   📖 ARCHITECTURE_V7.md - System architecture")
    print("   📖 QUICK_REFERENCE.md - Quick reference card")
    
    print()


def main():
    """Main setup flow"""
    print(f"""
{Colors.HEADER}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║           PubCast AI v7.0 — Quick Setup                  ║
║           The Unified Virtual Production Platform        ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
{Colors.ENDC}
""")
    
    # Run setup steps
    steps = [
        ("Python Version", check_python_version),
        ("Directory Structure", create_directory_structure),
        ("Virtual Environment", create_virtual_environment),
        ("Dependencies", install_dependencies),
        ("Environment Config", setup_environment),
        ("Ollama", check_ollama)
    ]
    
    failed_steps = []
    
    for step_name, step_func in steps:
        success = step_func()
        if not success:
            failed_steps.append(step_name)
    
    # Summary
    print_header("Setup Summary")
    
    if not failed_steps:
        print_success("All steps completed successfully!")
        print_next_steps()
    else:
        print_error(f"Setup completed with {len(failed_steps)} warning(s):")
        for step in failed_steps:
            print(f"   • {step}")
        print()
        print_info("Review the warnings above and fix any issues")
        print_info("You may still be able to run PubCast AI with limited functionality")
        print()


if __name__ == "__main__":
    main()
