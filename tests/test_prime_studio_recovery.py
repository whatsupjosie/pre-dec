from tests.host_lifespan_helpers import run_isolated_host


def test_production_placement_reuses_a_real_approved_pubworld_patch(tmp_path):
    run_isolated_host("""
import os
from fastapi.testclient import TestClient
from modules.auth import create_access_token
from modules.pubworld_blocks import get_prop, save_prop
import main

os.environ["PUBCAST_ENFORCE_AUTH"] = "1"
def auth(role):
    return {"Authorization": "Bearer " + create_access_token({"sub": role, "role": role})}

with TestClient(main.app) as studio:
    director = auth("mod")
    url = "/api/studio25d/voxel-props/news"
    assert studio.get(url, headers=director).json() == {"placement": None}
    approval = studio.post("/api/visual-patch/approve", headers=director, json={
        "patch_kind":"visual_patch", "scene_id":"pubworld_stage", "label":"Approved bridge fixture",
        "approval":{"state":"approved"},
        "proposal":{"patch_id":"capture_fixture", "dimensions":[3,2,1]},
    })
    assert approval.status_code == 200, approval.text
    prop_id = approval.json()["prop"]["prop_id"]
    data = {"placement":{"prop_id":prop_id,"x":.51,"y":.76,"size":.15,"angle":40}}
    denied = studio.put(url, headers=auth("viewer"), json=data)
    assert denied.status_code == 403
    assert studio.get(url, headers=director).json()["placement"] is None
    forged = studio.post("/api/pubworld/props",headers=director,json={
        "scene_id":"pubworld_stage", "blocks":[{"x":0,"y":0,"z":0}],
        "variants":[{"variant_id":"live_overlay"}],
    })
    assert forged.status_code == 200, forged.text
    forged_id = forged.json()["prop"]["prop_id"]
    assert studio.put(url, headers=director, json={
        "placement":{**data["placement"],"prop_id":forged_id},
    }).status_code == 422
    saved = studio.put(url, headers=director, json=data)
    assert saved.status_code == 200, saved.text
    old = saved.json()["placement"]
    assert old["block_count"] == 6
    assert len(old["geometry_sha256"]) == 64
    assert studio.get(url, headers=director).json() == saved.json()
    assert studio.get("/api/studio25d/voxel-props/general", headers=director).json() == {"placement":None}
    prop = get_prop(main.DATA_DIR, prop_id)
    prop.blocks[0].color = "#aabbcc"
    save_prop(main.DATA_DIR, prop)
    changed = studio.get(url, headers=director).json()["placement"]
    assert changed["geometry_sha256"] != old["geometry_sha256"]
    assert studio.put(url, headers=director, json={"placement":None}).status_code == 200
    assert studio.get(url, headers=director).json() == {"placement":None}
""", tmp_path)


def test_control_room_delete_checks_ownership_and_updates_persisted_roster(tmp_path):
    run_isolated_host("""
import os
from fastapi.testclient import TestClient
from modules.auth import create_access_token
from modules.bots import BotManager
import main

os.environ["PUBCAST_ENFORCE_AUTH"] = "1"
def auth(user, role):
    return {"Authorization": "Bearer " + create_access_token({"sub":user, "role":role})}

with TestClient(main.app) as studio:
    bot_id = "prime-delete-fixture"
    owner = auth("director", "mod")
    r = studio.post("/api/bots",headers=owner,json={
        "bot_id":bot_id,"name":"Disposable fixture",
        "provider":"ollama","model":"fixture","api_key_env":"","auto_reply":False,
    })
    assert r.status_code == 200, r.text
    path = "/api/bots/" + bot_id
    assert studio.delete(path, headers=auth("other","mod")).status_code == 403
    assert studio.delete(path, headers=auth("director","viewer")).status_code == 403
    assert studio.delete(path, headers=owner).status_code == 200
    assert studio.delete(path, headers=owner).status_code == 404
    assert BotManager(main.DATA_DIR, main.hub).get_config(bot_id) is None
""", tmp_path)
