"""Exercise the real PubWorld preview, approval and storage routes."""
from tests.host_lifespan_helpers import run_isolated_host


def test_pubworld_proposal_requires_approval_and_persists_both_kinds(tmp_path):
    run_isolated_host(r"""
import os

from fastapi.testclient import TestClient

import main
from modules.auth import create_access_token

os.environ["PUBCAST_ENFORCE_AUTH"] = "1"
director = {"Authorization": "Bearer " + create_access_token({"sub": "director", "role": "mod"})}
viewer = {"Authorization": "Bearer " + create_access_token({"sub": "viewer", "role": "viewer"})}
scene_id = "pubworld_stage"
region = {"x": .1, "y": .2, "width": .3, "height": .4}
costume = {"patch_kind": "visual_patch", "scene_id": scene_id, "performer_id": "Pete",
           "description": "Left shoulder clips through jacket", "region": region}
fit = {"patch_kind": "adaptive_extension", "scene_id": scene_id, "performer_id": "Pete",
       "object_id": "news-desk", "object_type": "desk", "performer_height": 2.4,
       "prop_height": .65, "prop_width": .8, "prop_depth": .55}
propose = "/api/visual-patch/propose"
approve = "/api/visual-patch/approve"
props = "/api/pubworld/props?scene_id=" + scene_id

with TestClient(main.app) as client:
    assert client.get("/health").status_code == 200
    stage = client.get("/pubworld-stage", headers=director)
    assert stage.status_code == 200
    assert "pubworld_visual_patch.js" in stage.text
    assert "/pubworld-stage#visual-patch" in client.get("/static/mini_console.html").text
    assert client.get("/static/pubworld_visual_patch.js").status_code == 200
    assert client.post(propose, json=costume).status_code == 401
    assert client.post(propose, json=costume, headers=viewer).status_code == 403
    bad_body = dict(costume, avatar_file_ref="unused.obj")
    assert client.post(propose, json=bad_body, headers=director).status_code == 422

    costume_response = client.post(propose, json=costume, headers=director)
    assert costume_response.status_code == 200, costume_response.text
    patch = costume_response.json()
    assert patch["proposal"]["anchor_joint"] == "upperarm_l"
    assert patch["proposal"]["screen_region"] == region
    assert patch["report"]["measurements"]["screen_bounds"] == region

    fit_response = client.post(propose, json=fit, headers=director)
    assert fit_response.status_code == 200, fit_response.text
    desk = fit_response.json()
    assert desk["proposal"]["kind"] == "surface_lift"
    assert desk["proposal"]["object_id"] == "news-desk"
    compatible = client.post(propose, json=dict(fit, prop_height=1.02), headers=director)
    assert compatible.status_code == 200, compatible.text
    assert compatible.json()["proposal"] is None
    assert client.get(props, headers=director).json()["props"] == []

    for result in (patch, desk):
        approval = {key: result[key] for key in ("scene_id", "patch_kind", "label", "proposal")}
        assert client.post(approve, json=approval, headers=director).status_code == 400
        approval["approval"] = {"state": "approved"}
        assert client.post(approve, json=approval, headers=viewer).status_code == 403
        saved = client.post(approve, json=approval, headers=director)
        assert saved.status_code == 200, saved.text
        assert len(saved.json()["voxels"]) > 0

    rows = {prop["label"]: prop for prop in client.get(props, headers=director).json()["props"]}
    assert len(rows) == 2
    assert rows[patch["label"]]["description"] == costume["description"]
    assert rows[patch["label"]]["variants"][0]["screen_region"] == region
    assert rows[desk["label"]]["variants"][0]["object_id"] == "news-desk"
""", tmp_path)
