from fastapi.testclient import TestClient
import logging
import main


def test_startup_boots_surface_voxel_and_studio_without_constructor_failures(tmp_path):
    from tests.host_lifespan_helpers import run_isolated_host
    run_isolated_host('import io, logging\nfrom fastapi.testclient import TestClient\nimport main\nstream = io.StringIO()\nlogging.getLogger().setLevel(logging.INFO)\nlogging.getLogger().addHandler(logging.StreamHandler(stream))\nwith TestClient(main.app):\n    pass\ntext = stream.getvalue()\nassert "[14] Surface manager failed" not in text\nassert "[16] Voxel stack failed" not in text\nassert "[17] Voxel bridge not connected" not in text\nassert "[18] Studio Control failed" not in text\nassert "[14] Surface manager ready" in text\nassert "[16] Voxel asset manager ready" in text\nassert "[18] Studio Control ready" in text', tmp_path)


def test_studio_and_voxel_endpoints_are_live_after_startup():
    with TestClient(main.app) as client:
        studio = client.get('/api/studio/status')
        assert studio.status_code == 200
        studio_body = studio.json()
        assert studio_body['available'] is True

        voxel = client.get('/api/voxel/status')
        assert voxel.status_code == 200
        voxel_body = voxel.json()
        assert voxel_body['asset_manager'] is True
        assert voxel_body['studio_integration'] is True
        integration = voxel_body['studio_integration_status']
        assert integration['native_preflight_hooks_active'] is False
        assert integration['native_scene_sync_on_roll'] is False
        assert voxel_body['bridge'] is True
        assert voxel_body['bridge_status'] is not None


def test_studio_preflight_and_emergency_save_routes_work():
    with TestClient(main.app) as client:
        preflight = client.post('/api/studio/preflight', json={})
        assert preflight.status_code == 200
        preflight_body = preflight.json()
        # No live input telemetry exists in the isolated test runtime. Preflight
        # must fail closed rather than claiming that the studio is safe to go live.
        assert preflight_body['ok'] is False
        assert 'result' in preflight_body
        assert preflight_body['result']['success'] is False
        assert preflight_body['result']['state'] == 'IDLE'
        assert 'checks' in preflight_body['result']
        assert any(not check.get('passed', False) for check in preflight_body['result']['checks'])

        emergency = client.post('/api/studio/emergency-save', json={})
        assert emergency.status_code == 200
        emergency_body = emergency.json()
        assert emergency_body['ok'] is True
        assert emergency_body['result']['ok'] is True


def test_studio_emergency_save_finalizes_capture_and_publishes_panic(tmp_path):
    from tests.host_lifespan_helpers import run_isolated_host

    run_isolated_host("""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from fastapi.testclient import TestClient
import main
from modules.capture import FFmpegCaptureEngine

active = {}
finalizing = Event()
release_capture = Event()

async def start(self, session_id, sources, profile, session_dir):
    path = session_dir / 'test-camera.mp4'
    active[session_id] = path
    return [path]

async def stop(self, session_id):
    finalizing.set()
    if not await asyncio.to_thread(release_capture.wait, 5):
        raise RuntimeError("Test never released capture")
    path = active.pop(session_id)
    path.write_bytes(b'capture finalized')
    return [path]

FFmpegCaptureEngine.start = start
FFmpegCaptureEngine.stop = stop
FFmpegCaptureEngine.is_capturing = lambda self, session_id: session_id in active
FFmpegCaptureEngine.available = property(lambda self: True)

with TestClient(main.app) as client:
    start_response = client.post('/api/studio/actions/recording.start', json={
        'session_id': 'emergency-check', 'sources': ['wide_shot'],
        'profile_id': 'broadcast_mp4', 'countdown_seconds': 0, 'confirm': True,
    })
    assert start_response.status_code == 200, start_response.text
    assert active
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.post, '/api/studio/emergency-save')
        try:
            assert finalizing.wait(4), 'capture never began finalizing'
            state = client.get('/api/state/production').json()
            assert state['blackout'] is True and state['panic_seq'] > 0
            assert client.get('/api/program-audio/status').json()['status']['master_volume'] == 0
            assert not pending.done()
        finally:
            release_capture.set()
        response = pending.result(timeout=8)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['ok'], result
    assert result['production_stop']['sessions_stopped'] == ['emergency-check']
    assert not active
    session = next(s for s in client.get('/api/recording/sessions').json()
                   if s['session_id'] == 'emergency-check')
    assert session['state'] == 'stopped'
    assert Path(session['artifacts'][0]['file_path']).read_bytes() == b'capture finalized'
    state = client.get('/api/state/production').json()
    assert state['blackout'] is True and state['panic_seq'] > 0
    assert client.get('/api/program-audio/status').json()['status']['master_volume'] == 0
    assert client.post('/api/studio/emergency-save').json()['ok']
""", tmp_path)


def test_recovered_floor_slate_is_connected_to_the_host(tmp_path):
    from tests.host_lifespan_helpers import run_isolated_host

    run_isolated_host("""
from fastapi.testclient import TestClient
from modules.auth import create_access_token, WS_SESSION_COOKIE
import main

director = create_access_token({'sub': 'director', 'role': 'mod'})
crew = create_access_token({'sub': 'camera', 'role': 'crew'})
director_headers = {'Authorization': 'Bearer ' + director}
crew_headers = {'Authorization': 'Bearer ' + crew}

with TestClient(main.app) as client:
    for path in ['/studio-control', '/director-switcher', '/static/production25d.html']:
        response = client.get(path)
        assert response.status_code == 200, (path, response.status_code)
        assert response.text.count('/static/studio_slate.js') == 1, path
    assert client.get('/static/control_room_assets/crew_reference.png').status_code == 200
    assert client.get('/api/studio/slate').status_code == 401
    with client.websocket_connect('/studio/slate/live',
                                  headers={'Cookie': WS_SESSION_COOKIE + '=' + crew}) as floor:
        response = client.post('/api/studio/slate', headers=director_headers,
                               json={'action': 'create'})
        assert response.status_code == 200, response.text
        assert floor.receive_json()['type'] == 'slate_changed'
        revision = response.json()['slate']['revision']
        response = client.post('/api/studio/slate', headers=director_headers,
                               json={'action': 'standby', 'revision': revision})
        assert response.status_code == 200, response.text
        assert floor.receive_json()['type'] == 'slate_changed'
        observed = client.get('/api/studio/slate', headers=crew_headers).json()
        assert observed['slate']['phase'] == 'standby'
        assert observed['slate']['visible']
        assert not observed['can_edit']
""", tmp_path)


def test_panic_drains_an_encoder_whose_start_is_still_in_flight(tmp_path):
    from tests.host_lifespan_helpers import run_isolated_host

    run_isolated_host("""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from fastapi.testclient import TestClient
from modules.capture import FFmpegCaptureEngine
import main

starting, release = Event(), Event()
active = {}

async def start(self, session_id, sources, profile, session_dir):
    starting.set()
    if not await asyncio.to_thread(release.wait, 5):
        raise RuntimeError("test did not release encoder")
    path = session_dir / "fixture.mp4"
    active[session_id] = path
    return [path]

async def stop(self, session_id):
    path = active.pop(session_id)
    path.write_bytes(b"test artifact")
    return [path]

FFmpegCaptureEngine.start = start
FFmpegCaptureEngine.stop = stop
FFmpegCaptureEngine.is_capturing = lambda self, session_id: session_id in active
FFmpegCaptureEngine.available = property(lambda self: True)

with TestClient(main.app) as client, ThreadPoolExecutor(max_workers=2) as pool:
    created = client.post("/api/recording/start", json={
        "session_id":"panic-during-camera-start", "sources":["wide_shot"], "countdown_seconds":5,
    })
    assert created.status_code == 200 and created.json()["state"] == "countdown", created.text
    assert not starting.is_set()
    roll = pool.submit(client.post, "/api/recording/panic-during-camera-start/activate")
    assert starting.wait(3)
    panic = pool.submit(client.post, "/api/production/panic")
    try:
        import time
        until = time.monotonic() + 3
        while not client.get("/api/state/production").json().get("blackout") and time.monotonic() < until:
            time.sleep(.01)
        assert client.get("/api/state/production").json()["blackout"]
        assert not panic.done()
    finally:
        release.set()
    assert roll.result(timeout=5).status_code == 409
    assert panic.result(timeout=5).json()["ok"]
    assert not active
    session = next(row for row in client.get("/api/recording/sessions").json()
                   if row["session_id"] == "panic-during-camera-start")
    assert session["state"] == "stopped" and len(session["artifacts"]) == 1
""", tmp_path)
