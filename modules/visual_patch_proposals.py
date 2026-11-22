"""Connect the recovered proposal planners to PubWorld's approval workflow."""
from dataclasses import replace
from types import SimpleNamespace
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from runtime.spine.event_bus import EventBus
from runtime.spine.performers.contact import ContactObject
from runtime.spine.performers.interaction_fit import InteractionFitCoordinator
from runtime.spine.visual import VisualPatchWorkflow, parse_styling_request, workflow_request_from_payload
from runtime.spine.visual.styling_aide import STYLE_DOMAIN_REPAIR

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
SceneID = Annotated[str, StringConstraints(strip_whitespace=True, min_length=6, max_length=48)]
Measurement = Annotated[float, Field(gt=0, le=8)]


class ScreenRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class CostumePatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patch_kind: Literal["visual_patch"]
    scene_id: SceneID
    performer_id: Identifier
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    region: ScreenRegion


class PropFitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patch_kind: Literal["adaptive_extension"]
    scene_id: SceneID
    performer_id: Identifier
    object_id: Identifier
    object_type: Literal["chair", "desk"]
    performer_height: Measurement
    prop_height: Measurement
    prop_width: Measurement
    prop_depth: Measurement


VisualProposalRequest = Annotated[CostumePatchRequest | PropFitRequest, Field(discriminator="patch_kind")]


def propose_visual_patch(request: CostumePatchRequest | PropFitRequest, actor: str) -> dict:
    """Plan a patch without emitting stage events or writing assets."""
    if isinstance(request, CostumePatchRequest):
        workflow = VisualPatchWorkflow(EventBus())
        inspection = workflow.handle_request(workflow_request_from_payload({
            "requester": {"requester_id": actor, "role": "director"},
            "performer_id": request.performer_id,
            "room_id": request.scene_id,
            "description": request.description,
            "selection": {"bounds": request.region.model_dump(), "target_ids": [request.performer_id]},
        }), emit=False)
        proposal = None
        message = "The description suggests a material adjustment. No geometry patch was proposed."
        if inspection.patch_needed:
            style = parse_styling_request(request.description, performer_id=request.performer_id, palette="match_outfit")
            plan = workflow.patch_kit.plan(replace(style, domain=STYLE_DOMAIN_REPAIR), emit=False)
            patch = workflow.patch_kit.patch_coordinator.build_patch(plan.actions[0]["payload"])
            if patch:
                proposal = {**patch.to_dict(), "description": request.description,
                            "screen_region": request.region.model_dump()}
                message = f"Suggested {patch.kind} patch at {patch.anchor_joint.replace('_', ' ')}."
        return _receipt(request, proposal, message, inspection.to_dict())

    # With entered height only, the recovered solver estimates the remaining body proportions.
    skeleton = SimpleNamespace(bind_pose={
        "root": {"position": [0, 0, 0]},
        "head": {"position": [0, request.performer_height, 0]},
    })
    performer = SimpleNamespace(performer_id=request.performer_id, avatar_skeleton=skeleton)
    if request.object_type == "chair":
        measurements = {"seat_height": request.prop_height, "seat_width": request.prop_width,
                        "seat_depth": request.prop_depth}
    else:
        measurements = {"desk_height": request.prop_height, "surface_width": request.prop_width,
                        "surface_depth": request.prop_depth}
    prop = ContactObject(request.object_id, request.object_type, [0, 0, 0], metadata=measurements)
    fit = InteractionFitCoordinator().evaluate(performer, prop, emit=False)
    proposal = next(iter(fit.adaptive_extensions), None)
    message = "The entered measurements did not yield an extension."
    if proposal:
        message = f"Suggested {proposal['kind'].replace('_', ' ')} based on the entered measurements."
    return _receipt(request, proposal, message, fit.to_dict())


def _receipt(request: CostumePatchRequest | PropFitRequest, proposal: dict | None, message: str, report: dict) -> dict:
    return {
        "ok": True,
        "scene_id": request.scene_id,
        "patch_kind": request.patch_kind,
        "proposal": proposal,
        "label": (
            f"Costume patch · {request.performer_id}" if isinstance(request, CostumePatchRequest)
            else f"{request.object_type.title()} fit · {request.object_id}"
        )[:64],
        "message": message,
        "report": report,
    }
