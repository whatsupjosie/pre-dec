
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class ProductionState(BaseModel):
    mode: str = Field(default="LIVE", description="LIVE or REPLAY")
    on_air: bool = False
    replay_asset: str = ""  # e.g., assets/vod/demo.mp4 (relative to root)
    lower_third: str = ""
    camera: str = "wide"  # 'wide' | 'closeup' | 'overhead'
    lighting: str = "normal"  # 'normal' | 'warm' | 'cool'

class UserState(BaseModel):
    user_id: str
    display_name: str = "User"
    avatar_color: str = "#00e0ff"
    badge: str = ""
    last_room: str = "dressing"
    # extend with more fields as needed
