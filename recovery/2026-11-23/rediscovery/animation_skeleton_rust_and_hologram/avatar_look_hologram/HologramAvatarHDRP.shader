Shader "PubCast/HologramAvatarHDRP"
{
    Properties
    {
        [Header(Base Properties)]
        _BaseColor ("Base Color", Color) = (0, 1, 1, 1)
        _EmissionColor ("Emission Color", Color) = (0.8, 1, 1, 1)
        _EmissionIntensity ("Emission Intensity", Range(0, 10)) = 3
        _AlphaMultiplier ("Alpha", Range(0, 1)) = 0.7
        
        [Header(Energy Effects)]
        _FresnelPower ("Fresnel Power", Range(0.1, 8)) = 2
        _GlowRadius ("Glow Radius", Range(0, 0.5)) = 0.1
        _PulseSpeed ("Pulse Speed", Range(0, 5)) = 1
        _PulseAmplitude ("Pulse Amplitude", Range(0, 1)) = 0.2
        
        [Header(Contact Glow)]
        _ContactGlowIntensity ("Contact Glow Intensity", Range(0, 5)) = 2
        _ContactGlowRadius ("Contact Glow Radius", Range(0, 1)) = 0.3
        _ContactFadeSpeed ("Contact Fade Speed", Range(0, 10)) = 3
        
        [Header(Noise and Distortion)]
        _NoiseScale ("Noise Scale", Range(0, 20)) = 5
        _NoiseSpeed ("Noise Speed", Vector) = (0.5, 0.3, 0.1, 0)
        _DistortionStrength ("Distortion Strength", Range(0, 0.1)) = 0.02
        
        [Header(Advanced)]
        _RimLightIntensity ("Rim Light Intensity", Range(0, 3)) = 1.5
        _InnerGlow ("Inner Glow", Range(0, 2)) = 0.8
        _EdgeSharpness ("Edge Sharpness", Range(0.1, 5)) = 1
        
        [Header(Textures)]
        _NoiseTexture ("Noise Texture", 2D) = "white" {}
        _FlowTexture ("Flow Texture", 2D) = "white" {}
    }

    SubShader
    {
        Tags 
        { 
            "RenderPipeline" = "HDRenderPipeline"
            "RenderType" = "Transparent" 
            "Queue" = "Transparent+0"
        }

        Pass
        {
            Name "ForwardOnly"
            Tags { "LightMode" = "ForwardOnly" }

            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            Cull Off

            HLSLPROGRAM
            #pragma target 4.5
            #pragma only_renderers d3d11 playstation xboxone xboxseries vulkan metal switch
            
            #pragma multi_compile_instancing
            #pragma multi_compile _ DEBUG_DISPLAY
            #pragma multi_compile _ LIGHTMAP_ON
            #pragma multi_compile _ DIRLIGHTMAP_COMBINED
            #pragma multi_compile _ DYNAMICLIGHTMAP_ON
            #pragma multi_compile_fragment _ SHADOWS_SHADOWMASK
            #pragma multi_compile_fragment DECALS_OFF DECALS_3RT DECALS_4RT
            #pragma multi_compile_fragment _ LIGHT_LAYERS
            
            #pragma vertex Vert
            #pragma fragment Frag

            #include "Packages/com.unity.render-pipelines.core/ShaderLibrary/Common.hlsl"
            #include "Packages/com.unity.render-pipelines.core/ShaderLibrary/Color.hlsl"
            #include "Packages/com.unity.render-pipelines.high-definition/Runtime/ShaderLibrary/ShaderVariables.hlsl"
            #include "Packages/com.unity.render-pipelines.high-definition/Runtime/Material/Material.hlsl"

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float4 tangentOS : TANGENT;
                float2 uv0 : TEXCOORD0;
                float2 uv1 : TEXCOORD1;
                float4 color : COLOR;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float3 tangentWS : TEXCOORD2;
                float3 bitangentWS : TEXCOORD3;
                float2 uv0 : TEXCOORD4;
                float2 uv1 : TEXCOORD5;
                float4 color : COLOR0;
                float3 viewDirWS : TEXCOORD6;
                float4 screenPos : TEXCOORD7;
                UNITY_VERTEX_INPUT_INSTANCE_ID
                UNITY_VERTEX_OUTPUT_STEREO
            };

            CBUFFER_START(UnityPerMaterial)
                float4 _BaseColor;
                float4 _EmissionColor;
                float _EmissionIntensity;
                float _AlphaMultiplier;
                float _FresnelPower;
                float _GlowRadius;
                float _PulseSpeed;
                float _PulseAmplitude;
                float _ContactGlowIntensity;
                float _ContactGlowRadius;
                float _ContactFadeSpeed;
                float _NoiseScale;
                float4 _NoiseSpeed;
                float _DistortionStrength;
                float _RimLightIntensity;
                float _InnerGlow;
                float _EdgeSharpness;
                float4 _NoiseTexture_ST;
                float4 _FlowTexture_ST;
            CBUFFER_END

            TEXTURE2D(_NoiseTexture);
            SAMPLER(sampler_NoiseTexture);
            TEXTURE2D(_FlowTexture);
            SAMPLER(sampler_FlowTexture);

            // Advanced noise functions
            float hash(float n) { return frac(sin(n) * 1e4); }
            float hash(float2 p) { return frac(1e4 * sin(17.0 * p.x + p.y * 0.1) * (0.1 + abs(sin(p.y * 13.0 + p.x)))); }

            float noise3D(float3 x) {
                const float3 step = float3(110, 241, 171);
                float3 i = floor(x);
                float3 f = frac(x);
                float n = dot(i, step);
                float3 u = f * f * (3.0 - 2.0 * f);
                return lerp(lerp(lerp( hash(n + dot(step, float3(0, 0, 0))), hash(n + dot(step, float3(1, 0, 0))), u.x),
                            lerp( hash(n + dot(step, float3(0, 1, 0))), hash(n + dot(step, float3(1, 1, 0))), u.x), u.y),
                       lerp(lerp( hash(n + dot(step, float3(0, 0, 1))), hash(n + dot(step, float3(1, 0, 1))), u.x),
                            lerp( hash(n + dot(step, float3(0, 1, 1))), hash(n + dot(step, float3(1, 1, 1))), u.x), u.y), u.z);
            }

            float fbm(float3 x, int octaves) {
                float v = 0.0;
                float a = 0.5;
                float3 shift = float3(100, 100, 100);
                for (int i = 0; i < octaves; ++i) {
                    v += a * noise3D(x);
                    x = x * 2.0 + shift;
                    a *= 0.5;
                }
                return v;
            }

            // Contact glow calculation
            float calculateContactGlow(float4 vertexColor, float3 worldPos) {
                // Use vertex color red channel for contact intensity
                float contactBase = vertexColor.r;
                
                // Add some noise to make contact points more organic
                float3 noisePos = worldPos * _NoiseScale * 0.5 + _Time.y * _ContactFadeSpeed;
                float contactNoise = noise3D(noisePos) * 0.3 + 0.7;
                
                // Fade contact over time if not actively maintained
                float timeFade = saturate(1.0 - _Time.y * _ContactFadeSpeed * 0.1);
                
                return contactBase * contactNoise * _ContactGlowIntensity;
            }

            Varyings Vert(Attributes input)
            {
                Varyings output;
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_TRANSFER_INSTANCE_ID(input, output);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);

                float3 positionWS = TransformObjectToWorld(input.positionOS.xyz);
                float3 normalWS = TransformObjectToWorldNormal(input.normalOS);

                // Add slight vertex animation for energy effect
                float3 noisePos = positionWS * _NoiseScale + _Time.y * _NoiseSpeed.xyz;
                float vertexNoise = fbm(noisePos, 3) * _DistortionStrength;
                positionWS += normalWS * vertexNoise;

                output.positionCS = TransformWorldToHClip(positionWS);
                output.positionWS = positionWS;
                output.normalWS = normalWS;
                
                float3 tangentWS = TransformObjectToWorldDir(input.tangentOS.xyz);
                output.tangentWS = tangentWS;
                output.bitangentWS = cross(normalWS, tangentWS) * input.tangentOS.w;
                
                output.uv0 = TRANSFORM_TEX(input.uv0, _NoiseTexture);
                output.uv1 = TRANSFORM_TEX(input.uv1, _FlowTexture);
                output.color = input.color;
                output.viewDirWS = normalize(_WorldSpaceCameraPos - positionWS);
                output.screenPos = ComputeScreenPos(output.positionCS);

                return output;
            }

            float4 Frag(Varyings input) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);

                // Base setup
                float3 normalWS = normalize(input.normalWS);
                float3 viewDirWS = normalize(input.viewDirWS);
                
                // Sample textures
                float noise = SAMPLE_TEXTURE2D(_NoiseTexture, sampler_NoiseTexture, input.uv0).r;
                float flow = SAMPLE_TEXTURE2D(_FlowTexture, sampler_FlowTexture, input.uv1).r;
                
                // Fresnel effect for edge glow
                float fresnel = 1.0 - saturate(dot(normalWS, viewDirWS));
                fresnel = pow(fresnel, _FresnelPower);
                
                // Advanced 3D noise for energy distortion
                float3 noisePos = input.positionWS * _NoiseScale + _Time.y * _NoiseSpeed.xyz;
                float energyNoise = fbm(noisePos, 4);
                
                // Pulsing animation
                float pulse = sin(_Time.y * _PulseSpeed) * _PulseAmplitude + (1.0 - _PulseAmplitude);
                
                // Contact glow from vertex colors
                float contactGlow = calculateContactGlow(input.color, input.positionWS);
                
                // Rim lighting effect
                float rimLight = pow(fresnel, _EdgeSharpness) * _RimLightIntensity;
                
                // Inner glow based on surface curvature
                float innerGlow = (1.0 - fresnel) * _InnerGlow;
                
                // Combine all glow effects
                float totalGlow = fresnel + rimLight + innerGlow + contactGlow;
                totalGlow *= pulse * (energyNoise * 0.5 + 0.5) * (noise * 0.3 + 0.7);
                
                // Color mixing
                float3 baseColor = _BaseColor.rgb;
                float3 emissionColor = _EmissionColor.rgb;
                
                // Energy flow effect using flow texture
                float3 flowEffect = lerp(baseColor, emissionColor, flow * totalGlow);
                
                // Final color composition
                float3 finalColor = lerp(baseColor, flowEffect, totalGlow);
                finalColor *= _EmissionIntensity;
                
                // Dynamic alpha based on glow intensity
                float alpha = _AlphaMultiplier + (totalGlow * 0.3);
                alpha = saturate(alpha) * _BaseColor.a;
                
                // Add extra brightness at contact points
                if (input.color.r > 0.1) {
                    finalColor += emissionColor * contactGlow * 0.5;
                    alpha += contactGlow * 0.2;
                }
                
                return float4(finalColor, saturate(alpha));
            }
            ENDHLSL
        }
    }
    
    CustomEditor "UnityEditor.ShaderGraph.PBRMasterGUI"
}