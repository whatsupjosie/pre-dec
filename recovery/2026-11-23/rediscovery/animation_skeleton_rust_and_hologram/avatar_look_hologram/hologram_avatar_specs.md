# Hologram Avatar Technical Specifications
## Based on Energy Being Reference Images

### Visual Analysis
**Color Profile:**
- Primary: Cyan/Electric Blue (#00FFFF to #0080FF)
- Core Intensity: Bright white-blue center (#E0F6FF)
- Edge Glow: Soft cyan falloff (#40C0FF with alpha)
- Background: Deep space blue-black (#0A0A20)

**Energy Characteristics:**
- Soft volumetric glow extending 5-10cm from mesh surface
- Brighter intensity at contact points and extremities
- Wispy, flowing energy tendrils
- Semi-transparent core with opaque highlights
- Dynamic brightness variation (pulsing/breathing effect)

### Mesh Topology Requirements

**Base Geometry:**
- Humanoid mesh: 2000-4000 triangles for hero characters
- Clean quad topology for animation
- Extra edge loops at joints for deformation
- Separate clothing meshes for flowing garments

**LOD Levels:**
1. **Hero (0-10m)**: Full 4K tri mesh with cloth simulation
2. **Mid (10-50m)**: 2K tri mesh, simplified cloth
3. **Crowd (50m+)**: 800 tri mesh, no cloth, billboard glow

**Special Geometry Requirements:**
- Smooth normals throughout (no hard edges)
- UV unwrapping optimized for energy flow patterns
- Vertex colors for glow intensity variation
- Extra vertices for contact point highlighting

### Shader Implementation

#### Unity HLSL Shader (URP/HDRP)
```hlsl
Shader "PubCast/HologramAvatar"
{
    Properties
    {
        _BaseColor ("Base Color", Color) = (0, 1, 1, 1)
        _EmissionColor ("Emission Color", Color) = (0.8, 1, 1, 1)
        _EmissionIntensity ("Emission Intensity", Range(0, 5)) = 2
        _GlowRadius ("Glow Radius", Range(0, 1)) = 0.1
        _ContactGlow ("Contact Glow", Range(0, 3)) = 1
        _AlphaMultiplier ("Alpha Multiplier", Range(0, 1)) = 0.7
        _PulseSpeed ("Pulse Speed", Range(0, 5)) = 1
        _FresnelPower ("Fresnel Power", Range(0, 5)) = 2
        _NoiseScale ("Noise Scale", Range(0, 10)) = 3
        _NoiseSpeed ("Noise Speed", Range(0, 2)) = 0.5
    }
    
    SubShader
    {
        Tags { "RenderType"="Transparent" "Queue"="Transparent" }
        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off
        Cull Off
        
        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            
            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float4 color : COLOR;
                float2 uv : TEXCOORD0;
            };
            
            struct Varyings
            {
                float4 positionHCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float4 color : COLOR;
                float2 uv : TEXCOORD2;
                float3 viewDirWS : TEXCOORD3;
            };
            
            CBUFFER_START(UnityPerMaterial)
                float4 _BaseColor;
                float4 _EmissionColor;
                float _EmissionIntensity;
                float _GlowRadius;
                float _ContactGlow;
                float _AlphaMultiplier;
                float _PulseSpeed;
                float _FresnelPower;
                float _NoiseScale;
                float _NoiseSpeed;
            CBUFFER_END
            
            // Simple noise function
            float noise(float3 pos)
            {
                return frac(sin(dot(pos, float3(12.9898, 78.233, 45.164))) * 43758.5453);
            }
            
            Varyings vert(Attributes input)
            {
                Varyings output;
                
                VertexPositionInputs positionInputs = GetVertexPositionInputs(input.positionOS.xyz);
                VertexNormalInputs normalInputs = GetVertexNormalInputs(input.normalOS);
                
                output.positionHCS = positionInputs.positionCS;
                output.positionWS = positionInputs.positionWS;
                output.normalWS = normalInputs.normalWS;
                output.color = input.color;
                output.uv = input.uv;
                output.viewDirWS = normalize(_WorldSpaceCameraPos - positionInputs.positionWS);
                
                return output;
            }
            
            float4 frag(Varyings input) : SV_Target
            {
                // Base color
                float4 color = _BaseColor;
                
                // Fresnel effect for energy glow
                float fresnel = 1.0 - saturate(dot(input.normalWS, input.viewDirWS));
                fresnel = pow(fresnel, _FresnelPower);
                
                // Animated noise for energy distortion
                float3 noisePos = input.positionWS * _NoiseScale + _Time.y * _NoiseSpeed;
                float energyNoise = noise(noisePos) * 0.5 + 0.5;
                
                // Pulsing effect
                float pulse = sin(_Time.y * _PulseSpeed) * 0.1 + 0.9;
                
                // Contact glow from vertex colors (set by contact system)
                float contactIntensity = input.color.r * _ContactGlow;
                
                // Combine effects
                float glowIntensity = (fresnel + contactIntensity) * pulse * energyNoise;
                color.rgb = lerp(_BaseColor.rgb, _EmissionColor.rgb, glowIntensity);
                
                // Emission
                color.rgb *= _EmissionIntensity;
                
                // Alpha with glow falloff
                color.a = (_AlphaMultiplier + glowIntensity) * _BaseColor.a;
                color.a = saturate(color.a);
                
                return color;
            }
            ENDHLSL
        }
    }
}
```

#### Unreal Engine Material Blueprint Nodes
```
MaterialExpression Setup:
1. Fresnel (ExponentIn: 2.0) -> Multiply -> EmissionColor
2. Time -> Sine -> Multiply(0.1) -> Add(0.9) = PulseEffect
3. WorldPosition -> Multiply(NoiseScale) -> Add(Time*NoiseSpeed) -> Noise
4. VertexColor.R -> Multiply(ContactGlowStrength)
5. All combined through Add/Multiply network
6. Final output to Emissive Color and Opacity
```

#### Blender Shader Nodes
```
Node Setup:
- Geometry -> Fresnel -> ColorRamp -> Mix with Base Color
- Object Info -> Random -> Noise Texture (animated) -> ColorRamp
- Vertex Color -> Separate RGB -> R channel for contact glow
- Math nodes for pulsing animation using #frame
- Emission BSDF mixed with Transparent BSDF
```

### Implementation Guidelines

#### For Unity:
1. Import base humanoid mesh
2. Apply HologramAvatar shader
3. Set up contact detection script to write vertex colors
4. Configure particle systems for additional energy effects
5. Use Universal Render Pipeline for proper transparency

#### For Unreal Engine 5:
1. Create Material with Blend Mode: Translucent
2. Enable "Responsive AA" for smooth edges
3. Use Niagara particle systems for energy wisps
4. Implement custom contact detection in Blueprint/C++
5. Configure Lumen for proper glow lighting

#### For Blender:
1. Use Cycles render engine for proper volumetrics
2. Enable Bloom in Compositor for glow effect
3. Set up drivers for animated properties
4. Use volume shaders for surrounding glow
5. Configure for real-time viewport shading

#### For PubCast Integration:
1. Export as GLTF 2.0 with custom shader extension
2. Implement WebGL-compatible shader variant
3. Use instanced rendering for crowd scenes
4. Optimize draw calls with LOD system
5. Integrate with existing skeleton system

### Performance Optimization

**GPU Performance:**
- Use shader LOD system based on distance
- Implement frustum culling for glow effects
- Batch similar avatars in single draw calls
- Use temporal upsampling for volumetric effects

**CPU Performance:**
- Limit contact detection to nearby avatars
- Use spatial partitioning for interaction queries
- Cache shader parameters between frames
- Implement async loading for avatar variations

**Memory Optimization:**
- Share base mesh between avatar instances
- Use texture atlasing for multiple avatar types
- Compress vertex data where possible
- Stream LOD levels based on importance

### Contact Glow System Integration

**Vertex Color Mapping:**
- R channel: Contact glow intensity
- G channel: Energy flow direction
- B channel: Special effects (healing, damage, etc.)
- A channel: Unused (reserved)

**Contact Detection:**
```rust
// Integrate with existing skeleton system
pub fn update_contact_glow(&mut self, contact_points: &[ContactPoint]) {
    for contact in contact_points {
        let joint_idx = self.find_joint(&contact.joint_name)?;
        let glow_intensity = contact.intensity.clamp(0.0, 1.0);
        
        // Update vertex colors in mesh for real-time glow
        self.update_vertex_color_at_joint(joint_idx, glow_intensity);
    }
}
```

### Export Specifications

**File Formats:**
- Unity: .prefab with materials and scripts
- Unreal: .uasset with Blueprint setup  
- Blender: .blend with full node setup
- Generic: .gltf with embedded materials
- PubCast: Custom .pca format with shader data

**Required Assets per Avatar:**
1. Base mesh (2-4K triangles)
2. Energy shader/material
3. Contact detection script/Blueprint
4. LOD variants (3 levels)
5. Animation retargeting setup
6. Particle effect prefabs
