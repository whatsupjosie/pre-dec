import pytest
import requests
import websockets
import asyncio
import json
import logging
import sys
import os
import time

# Add project root to Python path
project_root = os.path.abspath('/mnt/project')
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='/mnt/project/pubcast_tests.log',
    filemode='w'  # Overwrite log file each time
)
logger = logging.getLogger('pubcast_tests')

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws"

class TestPubcastControlRoom:
    @pytest.mark.integration
    def test_advanced_camera_management(self, test_client):
        """Test advanced camera management with status and metrics"""
        # Get initial camera sources
        response = test_client.get("/api/cameras")
        logger.info(f"Camera sources response: {response.text}")
        
        assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
        cameras = response.json()
        
        # Verify default cameras are present
        expected_cameras = ["program", "cam1"]
        camera_ids = [cam.get("source_id") for cam in cameras]
        
        for expected_cam in expected_cameras:
            assert expected_cam in camera_ids, f"Expected camera {expected_cam} not found"

        # Test adding a new camera with metrics
        new_camera = {
            "source_id": "test_cam_advanced",
            "name": "Advanced Test Camera",
            "description": "A camera with advanced metrics",
            "location": "test_location",
            "transport": "ndi",
            "endpoint": "ndi://test-stream",
            "status": "offline",
            "input_slot": 1,
            "metrics": {
                "latency_ms": 50.0,
                "frame_rate": 30.0,
                "resolution": "1920x1080",
                "signal_strength": 85.5,
                "connection_attempts": 1
            }
        }
        
        add_response = test_client.post("/api/cameras", json=new_camera)
        logger.info(f"Add camera response status: {add_response.status_code}")
        logger.info(f"Add camera response text: {add_response.text}")
        
        assert add_response.status_code == 200, f"Camera addition failed: {add_response.status_code}, {add_response.text}"
        assert add_response.json().get("ok") == True, "Camera not added successfully"

        # Test updating camera status
        status_update_response = test_client.post(f"/api/cameras/test_cam_advanced/status", json={
            "status": "online",
            "metrics": {
                "latency_ms": 25.0,
                "connection_attempts": 1
            }
        })
        
        logger.info(f"Camera status update response: {status_update_response.text}")
        assert status_update_response.status_code == 200, f"Camera status update failed: {status_update_response.status_code}"

    @pytest.mark.integration
    def test_advanced_audio_job_management(self, test_client):
        """Test advanced audio job management with tracking"""
        # Create an audio patch job
        audio_patch_payload = {
            "source": "uploads/test_audio.wav",
            "preset": "podcast_mix",
            "start_ms": 0,
            "end_ms": 30000
        }
        
        response = test_client.post("/api/audio/patch", json=audio_patch_payload)
        logger.info(f"Audio patch response: {response.text}")
        
        assert response.status_code == 200, f"Audio patch failed: {response.status_code}"
        patch_result = response.json()
        
        assert patch_result.get('ok') == True, "Audio patch not processed"
        assert 'job_id' in patch_result, "No job ID returned"
        assert patch_result.get('status') == 'processing', "Audio patch not in processing state"

        job_id = patch_result['job_id']

        # Wait and check job status
        time.sleep(3)  # Allow processing to start
        job_status_response = test_client.get(f"/api/audio/job/{job_id}")
        logger.info(f"Job status response: {job_status_response.text}")

        assert job_status_response.status_code == 200, f"Job status retrieval failed: {job_status_response.status_code}"
        job_status = job_status_response.json()

        assert job_status.get('ok') == True, "Job status retrieval unsuccessful"
        assert job_status['job'].get('status') in ['processing', 'completed'], "Job not processed"

        # List recent jobs
        jobs_list_response = test_client.get("/api/audio/jobs")
        logger.info(f"Jobs list response: {jobs_list_response.text}")

        assert jobs_list_response.status_code == 200, f"Jobs list retrieval failed: {jobs_list_response.status_code}"
        jobs_list = jobs_list_response.json()

        assert jobs_list.get('ok') == True, "Jobs list retrieval unsuccessful"
        assert len(jobs_list.get('jobs', [])) > 0, "No jobs returned"

def main():
    """Run tests and log results"""
    logger.info("Starting PubCast Control Room advanced management tests")
    
    # Run pytest programmatically
    import subprocess
    result = subprocess.run(
        ['pytest', '/mnt/project/test_pubcast_control_room.py', '-v', '-k', 'advanced'], 
        capture_output=True, 
        text=True
    )
    
    # Log test results
    logger.info("Test stdout:\n" + result.stdout)
    if result.stderr:
        logger.error("Test stderr:\n" + result.stderr)
    
    logger.info(f"Test exit code: {result.returncode}")

if __name__ == "__main__":
    main()
