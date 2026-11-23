"""Place an approved PubWorld voxel asset on a 2.5D production set."""
import hashlib
import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Path as PathParameter
from pydantic import BaseModel, ConfigDict, Field

from .persistence import read_json, write_json
from .pubworld_blocks import Prop, get_prop, list_props
from .route_security import require_role

Package = Annotated[str, PathParameter(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
MAX_BLOCKS = 2048


class Placement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prop_id: str = Field(pattern=r"^prp_[a-f0-9]{10}$")
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    size: float = Field(ge=0.02, le=0.5)
    angle: float = Field(ge=-180, le=180)


class PlacementChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    placement: Placement | None


def _geometry(prop: Prop, placement: Placement) -> dict:
    if not prop.visual_patch_approved:
        raise HTTPException(422, "Select an approved Visual Patch Kit prop")
    if not 0 < len(prop.blocks) <= MAX_BLOCKS:
        raise HTTPException(422, f"A production prop must have 1 to {MAX_BLOCKS} voxels")
    blocks = [{"x": block.x, "y": block.y, "z": block.z, "color": block.color} for block in prop.blocks]
    geometry_digest = hashlib.sha256(json.dumps(blocks, separators=(",", ":")).encode()).hexdigest()
    return {
        **placement.model_dump(),
        "label": prop.label,
        "blocks": blocks,
        "block_count": len(blocks),
        "geometry_sha256": geometry_digest,
    }


def create_voxel_placement_router(data_dir: Path) -> APIRouter:
    router = APIRouter(prefix="/api/studio25d/voxel-props", tags=["2.5D Voxel Props"])

    def placement_path(package: str) -> Path:
        return data_dir / "studio25d" / "voxel_placements" / f"{package}.json"

    def resolve(placement: Placement) -> dict:
        try:
            prop = get_prop(data_dir, placement.prop_id)
        except FileNotFoundError as exc:
            raise HTTPException(422, "The placed voxel prop is missing. Choose another prop or clear the placement.") from exc
        return _geometry(prop, placement)

    @router.get("/assets")
    def assets(identity: dict = Depends(require_role("mod"))):
        return {"props": [
            {"prop_id": prop.prop_id, "label": prop.label}
            for prop in list_props(data_dir)
            if prop.visual_patch_approved and 0 < len(prop.blocks) <= MAX_BLOCKS
        ]}

    @router.get("/{package}")
    def read_placement(package: Package, identity: dict = Depends(require_role("mod"))):
        row = read_json(placement_path(package))
        placement = Placement.model_validate(row["placement"]) if row.get("placement") else None
        return {"placement": resolve(placement) if placement else None}

    @router.put("/{package}")
    def save_placement(package: Package, body: PlacementChange, identity: dict = Depends(require_role("mod"))):
        geometry = resolve(body.placement) if body.placement else None
        write_json(placement_path(package), body.model_dump())
        return {"placement": geometry}

    return router
