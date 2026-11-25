# Voxel Asset System for PubCast AI

**Professional 3D Environment Management for Virtual Production**

---

## Overview

The **Voxel Asset System** is a complete 3D environment management suite for PubCast AI's virtual production platform. It manages your asset library, composes scenes, and integrates seamlessly with the Studio Control Room's preflight system.

### What's Included

- **voxel_asset_library.json** - Asset catalog (91 items: furniture, structures, props, vehicles, outdoor)
- **voxel_asset_manager.py** - Python backend for asset and scene management
- **voxel_scene_builder.html** - Visual scene composition interface
- **voxel_studio_integration.py** - Studio Control Room integration layer

---

## Quick Start

### 1. Place Files

```
your-pubcast-project/
├── data/
│   └── voxel_asset_library.json       # Asset catalog
├── modules/
│   ├── voxel_asset_manager.py         # Asset manager
│   └── voxel_studio_integration.py    # Studio integration
├── static/
│   └── voxel_scene_builder.html       # Scene builder UI
└── main.py
```

### 2. Initialize in Python

```python
from pathlib import Path
from modules.voxel_asset_manager import VoxelAssetManager
from modules.voxel_studio_integration import VoxelStudioIntegration

# Initialize asset manager
voxel_manager = VoxelAssetManager(
    library_path=Path("./data/voxel_asset_library.json"),
    pete=pete_enhanced
)

# Create integration with Studio Control
voxel_integration = VoxelStudioIntegration(
    asset_manager=voxel_manager,
    studio_control=studio_control,
    pete=pete_enhanced
)

# Register preflight hooks
await voxel_integration.register_preflight_hooks()
```

### 3. Access Scene Builder

```python
# Add route to your FastAPI app
@app.get("/scene-builder", response_class=HTMLResponse)
async def get_scene_builder():
    with open("./static/voxel_scene_builder.html") as f:
        return HTMLResponse(content=f.read())
```

Navigate to: `http://localhost:8000/scene-builder`

---

## Asset Library Structure

The asset library contains **91 curated 3D assets** organized into categories:

### Furniture (16 items)
**Standard:** couch, chair, recliner, crib, dining table, coffee table, bookshelf, dresser, nightstand, TV stand

**Fancy:** sectional couch, leather recliner, canopy bed, marble dining table, glass coffee table, ornate bookshelf

### Home Structure (14 items)
**Standard:** wall, window, door, floor, ceiling, tile floor, wood paneling, stairs, garage door

**Fancy:** arched window, double door, skylight, marble floor, decorative columns

### Rooms (9 prefabs)
Complete room prefabs: master bedroom, nursery, game room, TV room, dining room, kitchen, bathroom, garage, backyard

### Outdoor (10 items)
**Standard:** tree, sidewalk, light pole, mailbox, fence, grass patch

**Fancy:** garden fountain, stone path, decorative lamp post, gazebo

### Vehicles (6 items)
**Standard:** car, truck, motorcycle

**Fancy:** sports car, luxury SUV, pickup with lift

### Props (6 items)
phone, lamp, glass, cake, horse, potty

---

## Scene Composition Workflow

### Using Scene Builder (Visual)

1. **Navigate** to `http://localhost:8000/scene-builder`
2. **Browse** assets by category (furniture, structures, rooms, etc.)
3. **Click** assets to add them to your scene
4. **Configure** environment (lighting, fog, camera)
5. **Validate** scene for preflight
6. **Save** scene as JSON

### Using Python API

```python
# Create a new scene
scene = voxel_manager.create_scene(
    scene_id="detective_office",
    name="Detective's Office",
    description="Noir-style detective office"
)

# Add assets
from voxel_asset_manager import SceneAssetInstance

# Desk
scene.add_instance(SceneAssetInstance(
    instance_id="desk_1",
    asset_id="furniture_standard_desk",
    position=[0.0, 0.0, 0.0],
    rotation=[0.0, 0.0, 0.0],
    scale=[1.0, 1.0, 1.0]
))

# Chair
scene.add_instance(SceneAssetInstance(
    instance_id="chair_1",
    asset_id="furniture_standard_chair",
    position=[0.0, 0.0, 1.5]
))

# Lamp (prop)
scene.add_instance(SceneAssetInstance(
    instance_id="lamp_1",
    asset_id="prop_lamp",
    position=[0.0, 0.8, 0.0]
))

# Configure environment
scene.ambient_light = 0.15  # Low for noir atmosphere
scene.directional_light = [0.8, -0.5, 0.3]  # Strong directional

# Configure camera
scene.camera_position = [3.0, 1.6, 4.0]
scene.camera_target = [0.0, 1.0, 0.0]

# Set as active
voxel_manager.set_active_scene(scene.scene_id)

# Save to file
voxel_manager.save_scene_to_file(
    scene.scene_id,
    Path("./scenes/detective_office.json")
)
```

### Preset Scenes

The system includes two preset scenes ready to use:

```python
# Detective Humphrey's noir office
scene = voxel_manager.create_preset_scene_detective_office()

# Standard family living room
scene = voxel_manager.create_preset_scene_living_room()
```

---

## Studio Control Room Integration

The Voxel Asset System integrates with Studio Control Room's **5-second preflight countdown**:

### Automatic Preflight Checks

**T-4: Scene Validation** (with Gate Check)
- Verifies all assets exist in library
- Checks scene complexity (max 1000 instances)
- Validates memory usage (max 512MB)
- Identifies missing dependencies

**T-2: Asset Preloading** (with Ghost Mic Detection)
- Preloads all required assets
- Verifies files accessible
- Synchronizes with Rust engine
- Confirms textures/models ready

### Integration Points

```python
# In your Studio Control setup
from modules.voxel_studio_integration import VoxelStudioIntegration

voxel_integration = VoxelStudioIntegration(
    asset_manager=voxel_manager,
    studio_control=studio_control,
    pete=pete_enhanced
)

# Register preflight hooks
await voxel_integration.register_preflight_hooks()

# Hook into state transitions
studio_control.on_state_change("LIVE", voxel_integration.on_studio_live)
studio_control.on_emergency_save(voxel_integration.on_studio_emergency)
```

When you press **START COUNTDOWN** in Studio Control Room:
1. T-4: Scene validation runs automatically
2. T-2: Assets preload automatically
3. T-0: Scene syncs to Rust engine
4. Recording starts with environment ready

---

## API Reference

### VoxelAssetManager

#### Asset Queries

```python
# Get specific asset
asset = voxel_manager.get_asset("furniture_standard_couch")

# Get assets by category
furniture = voxel_manager.get_assets_by_category(
    AssetCategory.FURNITURE,
    quality=AssetQuality.STANDARD
)

# Search assets
results = voxel_manager.search_assets("chair")

# Get all assets
all_assets = voxel_manager.get_all_assets()
```

#### Scene Management

```python
# Create scene
scene = voxel_manager.create_scene(
    scene_id="my_scene",
    name="My Scene",
    description="Custom environment"
)

# Get scene
scene = voxel_manager.get_scene("my_scene")

# Set active scene
voxel_manager.set_active_scene("my_scene")

# Get active scene
scene = voxel_manager.get_active_scene()

# Load from file
scene = voxel_manager.load_scene_from_file(Path("scene.json"))

# Save to file
voxel_manager.save_scene_to_file("my_scene", Path("scene.json"))
```

#### Scene Validation

```python
# Validate scene for preflight
result = await voxel_manager.validate_scene_for_preflight("my_scene")

# Returns:
# {
#     "passed": True/False,
#     "errors": ["error1", "error2"],
#     "warnings": ["warning1"],
#     "info": {
#         "instance_count": 42,
#         "required_assets": 15,
#         "estimated_memory_mb": 37.5,
#         "scene_name": "My Scene"
#     }
# }
```

#### Asset Preloading

```python
# Preload all assets for a scene
success = await voxel_manager.preload_scene_assets("my_scene")
```

#### Pete Enhanced Integration

```python
# Sync scene to Rust engine
success = await voxel_manager.sync_with_rust_engine(scene)

# Get performance stats
stats = voxel_manager.get_performance_stats()
# Returns:
# {
#     "loaded_assets": 15,
#     "total_assets": 91,
#     "memory_used_mb": 37.5,
#     "active_scene": "my_scene",
#     "scene_count": 3
# }
```

### VoxelScene

#### Scene Properties

```python
scene.scene_id          # Unique identifier
scene.name              # Display name
scene.description       # Description
scene.instances         # List of placed assets
scene.required_assets   # Set of required asset IDs

# Environment
scene.ambient_light     # 0.0 - 1.0
scene.directional_light # [x, y, z] direction
scene.fog_enabled       # True/False
scene.fog_distance      # Distance in units

# Camera
scene.camera_position   # [x, y, z]
scene.camera_target     # [x, y, z]

# Performance
scene.max_draw_distance # Culling distance
scene.lod_bias          # Level of Detail multiplier
```

#### Instance Management

```python
# Add instance
scene.add_instance(instance)

# Remove instance
scene.remove_instance("instance_id")

# Get instance
instance = scene.get_instance("instance_id")

# Convert to dict
data = scene.to_dict()
```

### SceneAssetInstance

```python
instance = SceneAssetInstance(
    instance_id="desk_1",
    asset_id="furniture_standard_desk",
    position=[0.0, 0.0, 0.0],      # [x, y, z]
    rotation=[0.0, 0.0, 0.0],      # [pitch, yaw, roll] in radians
    scale=[1.0, 1.0, 1.0],         # [x, y, z] scale factors
    visible=True,                   # Render visibility
    cast_shadows=True,              # Shadow casting
    receive_shadows=True,           # Shadow receiving
    interactive=False,              # Interactive object
    collision_enabled=True          # Collision detection
)
```

---

## Scene File Format

Scenes are saved as JSON:

```json
{
  "scene_id": "detective_office_noir",
  "name": "Detective's Office",
  "description": "Noir-style detective office",
  "instances": [
    {
      "instance_id": "desk_1",
      "asset_id": "furniture_standard_desk",
      "position": [0.0, 0.0, 0.0],
      "rotation": [0.0, 0.0, 0.0],
      "scale": [1.0, 1.0, 1.0],
      "visible": true,
      "cast_shadows": true,
      "receive_shadows": true,
      "interactive": false,
      "collision_enabled": true
    }
  ],
  "required_assets": [
    "furniture_standard_desk",
    "furniture_standard_chair",
    "prop_lamp"
  ],
  "environment": {
    "ambient_light": 0.15,
    "directional_light": [0.8, -0.5, 0.3],
    "fog_enabled": false,
    "fog_distance": 100.0
  },
  "camera": {
    "position": [3.0, 1.6, 4.0],
    "target": [0.0, 1.0, 0.0]
  },
  "performance": {
    "max_draw_distance": 50.0,
    "lod_bias": 1.0
  }
}
```

---

## Performance Limits

The system enforces production-safe limits:

| Metric | Warning | Error |
|--------|---------|-------|
| **Instances** | 500+ | 1000+ |
| **Memory** | 256+ MB | 512+ MB |
| **Assets** | N/A | Must exist in library |

These limits are validated during preflight checks.

---

## Extension Points

### Custom Asset Categories

```python
# Add to voxel_asset_library.json
{
  "custom_category": {
    "standard": ["item1", "item2"],
    "fancy": ["item3"]
  }
}

# Register in VoxelAssetManager._build_asset_catalog()
```

### Custom Preflight Checks

```python
async def custom_check(self) -> PreflightCheck:
    """Custom validation logic"""
    # Your check here
    return PreflightCheck(
        check_id="custom_check",
        name="Custom Check",
        passed=True,
        message="All good"
    )

# Register in VoxelStudioIntegration
```

---

## Integration with Pete Enhanced

Pete Enhanced orchestrates the complete pipeline:

```python
class PeteEnhanced:
    async def load_voxel_scene(self, scene_data: Dict) -> bool:
        """Load scene into Rust voxel engine"""
        # Send to Rust engine via Bridge
        await self.voxel_bridge.load_scene(scene_data)
        return True
    
    async def get_connected_devices(self) -> List[str]:
        """Query hardware for Gate Check"""
        # Return detected audio/video devices
        return self.hardware_monitor.get_devices()
```

---

## Troubleshooting

### Asset Not Found

**Problem:** "Asset not found: furniture_standard_couch"

**Solutions:**
- Verify asset_id matches library exactly
- Check voxel_asset_library.json loaded
- Rebuild asset catalog with `_build_asset_catalog()`

### Scene Validation Fails

**Problem:** Preflight check fails with "Scene too complex"

**Solutions:**
- Reduce instance count below 1000
- Use room prefabs instead of individual furniture
- Optimize asset quality (standard vs fancy)
- Increase culling distance

### Memory Limit Exceeded

**Problem:** Estimated memory usage > 512MB

**Solutions:**
- Reduce number of unique assets
- Use standard quality instead of fancy
- Implement LOD (Level of Detail) system
- Increase system limit in config

---

## Best Practices

1. **Use Preset Scenes** - Start with presets, customize from there
2. **Test Before Live** - Always validate scenes during preflight
3. **Optimize Early** - Keep instance counts reasonable
4. **Name Consistently** - Use descriptive scene_ids and instance_ids
5. **Version Control** - Save scene files to git
6. **Document Scenes** - Add descriptions to complex scenes

---

## Complete Example

```python
# main.py - Complete integration example

from pathlib import Path
from fastapi import FastAPI
from modules.voxel_asset_manager import VoxelAssetManager
from modules.voxel_studio_integration import VoxelStudioIntegration
from modules.studio_control import StudioControl
from pete_enhanced import PeteEnhanced

app = FastAPI()

# Initialize Pete
pete = PeteEnhanced(hub, bridge, motion_system, Path("./data"))

# Initialize Studio Control
studio = StudioControl(hub, pete, Path("./data"))

# Initialize Voxel Asset Manager
voxel_manager = VoxelAssetManager(
    library_path=Path("./data/voxel_asset_library.json"),
    pete=pete
)

# Create integration
voxel_integration = VoxelStudioIntegration(
    asset_manager=voxel_manager,
    studio_control=studio,
    pete=pete
)

# Register hooks
await voxel_integration.register_preflight_hooks()

# Load Detective Office scene
scene = voxel_manager.create_preset_scene_detective_office()
voxel_manager.set_active_scene(scene.scene_id)

# Serve Scene Builder
@app.get("/scene-builder")
async def scene_builder():
    with open("./static/voxel_scene_builder.html") as f:
        return HTMLResponse(f.read())

# Start server
# uvicorn main:app --reload
```

---

## Next Steps

1. **Customize Asset Library** - Add your own 3D models
2. **Create Custom Scenes** - Build environments for your shows
3. **Integrate with Rust Engine** - Complete the rendering pipeline
4. **Add Animation** - Animate camera paths and asset transforms
5. **Extend Preflight** - Add custom validation checks

---

## Credits

**Voxel Asset System** - Professional 3D environment management for PubCast AI

Designed for creators who need production-grade scene composition with broadcast-quality preflight validation.

**"Build your world. The system makes sure it's ready."** 🎨

---

*Feic Mo Chroí (See My Heart) - Technology serving human storytelling.*
