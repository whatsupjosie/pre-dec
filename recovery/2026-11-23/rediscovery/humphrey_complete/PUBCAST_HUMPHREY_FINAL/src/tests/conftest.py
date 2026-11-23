"""Pytest configuration for PubCast AI V7."""

import sys
from pathlib import Path

import pytest
import pytest
import subprocess
import time
import requests
import sys
import os

# Add project root to Python path
project_root = os.path.abspath('/mnt/project')
sys.path.insert(0, project_root)

# Modify PYTHONPATH to include the project root
os.environ['PYTHONPATH'] = project_root + ':' + os.environ.get('PYTHONPATH', '')

# Add modules directory to path
modules_path = os.path.join(project_root, 'modules')
sys.path.append(modules_path)

from fastapi.testclient import TestClient

# Import the FastAPI application
sys.path.append(project_root)
import main

@pytest.fixture(scope="module")
def test_client():
    """
    Create a TestClient for API testing
    """
    return TestClient(main.app)

@pytest.fixture(scope="session", autouse=True)
def pubcast_server():
    """
    Fixture to start the PubCast server before tests and stop it after
    """
    # Start the server
    server_process = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000'],
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for server to start
    max_attempts = 10
    for _ in range(max_attempts):
        try:
            response = requests.get('http://localhost:8000/', timeout=2)
            if response.status_code == 200:
                break
        except requests.ConnectionError:
            time.sleep(1)
    else:
        pytest.fail("Could not start PubCast server")

    # Yield control to tests
    yield server_process

    # Terminate the server after tests
    server_process.terminate()
    server_process.wait()

def pytest_configure(config):
    """
    Configure pytest to add custom markers
    """
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "websocket: mark test involving WebSocket"
    )

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import app  # noqa: E402


@pytest.fixture(scope="function")
def client() -> TestClient:
    """Fresh TestClient per test with a seeded session cookie."""
    c = TestClient(app)
    c.get("/")  # seed cookie/state
    return c

@pytest.fixture(scope="module")
def test_client():
    """
    Create a TestClient for API testing
    """
    return TestClient(main.app)

@pytest.fixture(scope="session", autouse=True)
def pubcast_server():
    """
    Fixture to start the PubCast server before tests and stop it after
    """
    # Start the server
    server_process = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000'],
        cwd='/mnt/project',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for server to start
    max_attempts = 10
    for _ in range(max_attempts):
        try:
            response = requests.get('http://localhost:8000/', timeout=2)
            if response.status_code == 200:
                break
        except requests.ConnectionError:
            time.sleep(1)
    else:
        pytest.fail("Could not start PubCast server")

    # Yield control to tests
    yield server_process

    # Terminate the server after tests
    server_process.terminate()
    server_process.wait()
