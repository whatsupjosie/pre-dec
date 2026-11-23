# PubCast Complete Animation System - Integration Guide

## Overview

This guide demonstrates how to use the complete PubCast animation system with your hologram avatars. The system provides:

- **Professional Animation Package**: Walking, running, jumping, sitting, dancing, and all requested animations
- **Gender-Specific Variations**: Female high-heel walk, makeup actions, male/female body morphing  
- **Automatic Avatar Fitting**: Any avatar mesh automatically fits to the skeleton system
- **Hair Animation System**: Physics-based hair simulation with style controls
- **Performance Optimization**: LOD system scaling from laptops to high-end workstations
- **Real-time Body Morphing**: Adjust hip curves, breast size, shoulder width in real-time

## Quick Start Example

```rust
use pubcast_animation::*;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 1. Create skeleton and animation controller
    let mut skeleton = SkeletalAnimator::new(SkeletonHierarchy::create_standard_humanoid());
    let mut animation_controller = CompleteAnimationController::new();
    
    // 2. Configure a female avatar with custom proportions
    let avatar_config = AvatarConfiguration {
        gender: Gender::Female,
        body_proportions: BodyProportions {
            height: 1.1,           // 10% taller
            hip_width: 1.3,        // 30% wider hips
            breast_size: 0.8,      // Larger chest
            waist_ratio: 0.7,      // Smaller waist
            hip_curve: 0.9,        // Pronounced hip curve
            ..Default::default()
        },
        hair_config: HairConfiguration {
            hair_type: HairType::Long,
            length: 0.4,           // Long hair
            simulation_enabled: true,
            physics_settings: HairPhysics {
                stiffness: 0.6,
                wind_response: 0.5,
                ..Default::default()
            },
            ..Default::default()
        },
        ..Default::default()
    };
    
    // 3. Setup the avatar
    let setup_result = animation_controller.setup_avatar(&mut skeleton, avatar_config)?;
    println!("Avatar setup: {}", setup_result);
    
    // 4. Start with a high-heel walk
    animation_controller.start_high_heel_walk(0.8)?; // 80% hip emphasis
    
    // 5. Main animation loop (call every frame)
    let mut frame_time = 0.0;
    loop {
        let delta_time = 1.0 / 60.0; // 60 FPS
        frame_time += delta_time;
        
        // Update animations
        animation_controller.update(&mut skeleton, delta_time)?;
        
        // Example: Switch to lipstick application after 3 seconds
        if frame_time > 3.0 && !animation_controller.is_transitioning() {
            animation_controller.apply_lipstick()?;
            break;
        }
    }
    
    Ok(())
}
```

## Detailed Usage Examples

### 1. Male Avatar with Broad Shoulders

```rust
fn create_male_avatar() -> Result<(), String> {
    let mut skeleton = SkeletalAnimator::new(SkeletonHierarchy::create_standard_humanoid());
    let mut controller = CompleteAnimationController::new();
    
    let male_config = AvatarConfiguration {
        gender: Gender::Male,
        body_proportions: BodyProportions {
            shoulder_width: 1.4,     // Broad shoulders
            shoulder_bulk: 0.8,      // Muscular build
            chest_depth: 0.7,        // Deep chest
            hip_width: 0.9,          // Narrow hips
            waist_ratio: 0.85,       // Less defined waist
            ..Default::default()
        },
        hair_config: HairConfiguration {
            hair_type: HairType::Short,
            simulation_enabled: false, // Static hair for performance
            ..Default::default()
        },
        ..Default::default()
    };
    
    controller.setup_avatar(&mut skeleton, male_config)?;
    
    // Male-specific animations
    controller.start_walking(GenderVariant::Masculine)?;
    
    // After walking, perform a formal bow
    std::thread::sleep(std::time::Duration::from_secs(2));
    controller.bow(BowDepth::Formal, FormalityLevel::Ceremonial)?;
    
    Ok(())
}
```

### 2. Female Avatar with Complete Makeup Routine

```rust
fn female_makeup_sequence() -> Result<(), String> {
    let mut skeleton = SkeletalAnimator::new(SkeletonHierarchy::create_standard_humanoid());
    let mut controller = CompleteAnimationController::new();
    
    let female_config = AvatarConfiguration {
        gender: Gender::Female,
        body_proportions: BodyProportions {
            breast_size: 0.7,
            hip_width: 1.2,
            hip_curve: 0.8,
            waist_curve: 0.9,
            waist_ratio: 0.65, // Very defined waist
            ..Default::default()
        },
        hair_config: HairConfiguration {
            hair_type: HairType::Medium,
            length: 0.25,
            simulation_enabled: true,
            style_modifiers: vec![
                HairStyleModifier::Wave { frequency: 2.0, amplitude: 0.03 },
                HairStyleModifier::Part { side: HairPartSide::Left, depth: 0.8 },
            ],
            ..Default::default()
        },
        ..Default::default()
    };
    
    controller.setup_avatar(&mut skeleton, female_config)?;
    
    // Makeup sequence
    controller.open_purse()?;
    wait_for_completion(&mut controller);
    
    controller.apply_lipstick()?;
    wait_for_completion(&mut controller);
    
    // Switch to mascara
    controller.request_state_change(AnimationState::MakeupAction {
        action: MakeupActionType::Mascara,
        progress: 0.0,
    })?;
    wait_for_completion(&mut controller);
    
    // Powder face
    controller.request_state_change(AnimationState::MakeupAction {
        action: MakeupActionType::Powder,
        progress: 0.0,
    })?;
    wait_for_completion(&mut controller);
    
    // Return to elegant idle
    controller.return_to_idle(Some(IdleVariant::HandsOnHips))?;
    
    Ok(())
}

fn wait_for_completion(controller: &mut CompleteAnimationController) {
    // In real implementation, this would be part of your main loop
    std::thread::sleep(std::time::Duration::from_secs(2));
}
```

### 3. Interactive Dancing Avatars with Contact Glow

```rust
fn dancing_couple_example() -> Result<(), String> {
    // Create two avatars
    let mut male_skeleton = SkeletalAnimator::new(SkeletonHierarchy::create_standard_humanoid());
    let mut female_skeleton = SkeletalAnimator::new(SkeletonHierarchy::create_standard_humanoid());
    
    let mut male_controller = CompleteAnimationController::new();
    let mut female_controller = CompleteAnimationController::new();
    
    // Setup male dancer
    let male_config = AvatarConfiguration {
        gender: Gender::Male,
        body_proportions: BodyProportions {
            height: 1.1,
            shoulder_width: 1.2,
            ..Default::default()
        },
        ..Default::default()
    };
    
    // Setup female dancer
    let female_config = AvatarConfiguration {
        gender: Gender::Female,
        body_proportions: BodyProportions {
            height: 1.0,
            hip_width: 1.1,
            hip_curve: 0.7,
            waist_ratio: 0.75,
            ..Default::default()
        },
        hair_config: HairConfiguration {
            hair_type: HairType::Ponytail,
            length: 0.3,
            simulation_enabled: true,
            physics_settings: HairPhysics {
                gravity_strength: 0.8,
                wind_response: 0.3,
                ..Default::default()
            },
            ..Default::default()
        },
        ..Default::default()
    };
    
    male_controller.setup_avatar(&mut male_skeleton, male_config)?;
    female_controller.setup_avatar(&mut female_skeleton, female_config)?;
    
    // Position avatars for dancing (this would be done in your 3D engine)
    // male_skeleton.set_world_position(Vector3::new(-0.5, 0.0, 0.0));
    // female_skeleton.set_world_position(Vector3::new(0.5, 0.0, 0.0));
    
    // Start synchronized dancing
    // Both start with basic walk, then transition to dance moves
    male_controller.start_walking(GenderVariant::Masculine)?;
    female_controller.start_high_heel_walk(0.9)?; // Emphasize hip movement
    
    // Event handler for contact detection (hologram glow effect)
    male_controller.add_event_handler("contact_detected", |event| {
        if let AnimationEvent::ContactDetected { avatar_id, contact_joint, intensity } = event {
            println!("Contact glow: {} at {} with intensity {}", 
                     avatar_id, contact_joint, intensity);
            // This would trigger the hologram glow effect in your renderer
        }
    });
    
    // Main dance loop
    let mut dance_time = 0.0;
    loop {
        let delta_time = 1.0 / 60.0;
        dance_time += delta_time;
        
        male_controller.update(&mut male_skeleton, delta_time)?;
        female_controller.update(&mut female_skeleton, delta_time)?;
        
        // Detect hand-to-hand contact for glow effect
        // This would be implemented in your 3D engine
        detect_avatar_contact(&male_skeleton, &female_skeleton);
        
        if dance_time > 10.0 { break; } // Dance for 10 seconds
    }
    
    Ok(())
}

fn detect_avatar_contact(male: &SkeletalAnimator, female: &SkeletalAnimator) {
    // Implementation would check distance between hand joints
    // and trigger contact glow when they're close enough
    
    if let (Some(male_hand), Some(female_hand)) = (
        male.get_joint_world_position("right_hand"),
        female.get_joint_world_position("left_hand")
    ) {
        let distance = (male_hand - female_hand).magnitude();
        if distance < 0.1 { // 10cm threshold
            // Trigger glow effect - this would be handled by your hologram renderer
            println!("Hand contact detected - triggering glow effect");
        }
    }
}
```

### 4. Idle Animation Cycling

```rust
fn idle_behavior_demo() -> Result<(), String> {
    let mut skeleton = SkeletalAnimator::new(SkeletonHierarchy::create_standard_humanoid());
    let mut controller = CompleteAnimationController::new();
    
    let neutral_config = AvatarConfiguration {
        gender: Gender::Neutral,
        ..Default::default()
    };
    
    controller.setup_avatar(&mut skeleton, neutral_config)?;
    
    // Cycle through different idle behaviors
    let idle_variants = vec![
        IdleVariant::Basic,
        IdleVariant::HandsInPockets,
        IdleVariant::ArmsFolded,
        IdleVariant::LookingAround,
        IdleVariant::ShiftWeight,
        IdleVariant::CheckTime,
    ];
    
    for (i, variant) in idle_variants.iter().enumerate() {
        println!("Switching to idle variant: {:?}", variant);
        controller.return_to_idle(Some(variant.clone()))?;
        
        // Hold each idle for 3 seconds
        for frame in 0..180 { // 3 seconds at 60fps
            controller.update(&mut skeleton, 1.0/60.0)?;
        }
    }
    
    Ok(())
}
```

### 5. Performance Optimization Example

```rust
fn performance_optimization_demo() -> Result<(), String> {
    let mut skeleton = SkeletalAnimator::new(SkeletonHierarchy::create_standard_humanoid());
    let mut controller = CompleteAnimationController::new();
    
    // Configure for laptop performance
    controller.set_performance_level(2)?; // Medium quality for laptop
    
    let laptop_config = AvatarConfiguration {
        gender: Gender::Female,
        hair_config: HairConfiguration {
            hair_type: HairType::Short, // Shorter hair for performance
            simulation_enabled: false,   // Disable physics on laptop
            ..Default::default()
        },
        body_proportions: BodyProportions {
            hip_width: 1.1,
            breast_size: 0.6,
            ..Default::default()
        },
        ..Default::default()
    };
    
    controller.setup_avatar(&mut skeleton, laptop_config)?;
    
    // Monitor performance
    controller.add_event_handler("performance_warning", |event| {
        println!("Performance warning: {:?}", event);
    });
    
    // Test different animations and their performance impact
    let animations = vec![
        ("Walking", || -> Result<(), String> { 
            controller.start_walking(GenderVariant::Feminine) 
        }),
        ("High Heel Walk", || -> Result<(), String> { 
            controller.start_high_heel_walk(0.5) 
        }),
        ("Typing", || -> Result<(), String> { 
            controller.start_typing(TypingIntensity::Normal) 
        }),
        ("Sitting", || -> Result<(), String> { 
            controller.sit_in_chair() 
        }),
    ];
    
    for (name, animation_fn) in animations {
        println!("Testing performance of: {}", name);
        let start_time = std::time::Instant::now();
        
        animation_fn()?;
        
        // Run for 1 second to measure performance
        for _ in 0..60 {
            controller.update(&mut skeleton, 1.0/60.0)?;
        }
        
        let elapsed = start_time.elapsed();
        println!("Animation '{}' took {:?} for 1 second", name, elapsed);
    }
    
    Ok(())
}
```

## Integration with Game Engines

### Unity Integration

```csharp
// Unity C# wrapper for the Rust animation system
using UnityEngine;
using System.Runtime.InteropServices;

public class PubCastAvatarController : MonoBehaviour 
{
    [DllImport("pubcast_animation")]
    private static extern System.IntPtr create_animation_controller();
    
    [DllImport("pubcast_animation")]
    private static extern int setup_avatar(System.IntPtr controller, AvatarConfig config);
    
    [DllImport("pubcast_animation")]
    private static extern int update_animation(System.IntPtr controller, float deltaTime);
    
    [DllImport("pubcast_animation")]
    private static extern int start_walking(System.IntPtr controller, int genderVariant);
    
    private System.IntPtr nativeController;
    
    [Header("Avatar Configuration")]
    public Gender gender = Gender.Female;
    public float hipWidth = 1.0f;
    public float breastSize = 0.5f;
    public float hipCurve = 0.5f;
    
    [Header("Hair Configuration")]
    public HairType hairType = HairType.Medium;
    public float hairLength = 0.2f;
    public bool enableHairPhysics = true;
    
    void Start() 
    {
        nativeController = create_animation_controller();
        
        var config = new AvatarConfig {
            gender = gender,
            hipWidth = hipWidth,
            breastSize = breastSize,
            hipCurve = hipCurve,
            hairType = hairType,
            hairLength = hairLength,
            enableHairPhysics = enableHairPhysics
        };
        
        setup_avatar(nativeController, config);
    }
    
    void Update() 
    {
        update_animation(nativeController, Time.deltaTime);
    }
    
    public void StartWalking() 
    {
        int genderVariant = gender == Gender.Female ? 2 : 1;
        start_walking(nativeController, genderVariant);
    }
    
    public void StartHighHeelWalk() 
    {
        // Call appropriate native function
    }
    
    // Additional Unity-specific methods...
}
```

### Unreal Engine Integration

```cpp
// Unreal C++ component
UCLASS(BlueprintType, Blueprintable)
class PUBCAST_API UPubCastAnimationComponent : public UActorComponent
{
    GENERATED_BODY()
    
public:
    UPubCastAnimationComponent();
    
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, 
                              FActorComponentTickFunction* ThisTickFunction) override;
    
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Avatar Config")
    EGender Gender = EGender::Female;
    
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Avatar Config", 
              meta = (ClampMin = "0.5", ClampMax = "2.0"))
    float HipWidth = 1.0f;
    
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Avatar Config",
              meta = (ClampMin = "0.0", ClampMax = "1.0"))
    float BreastSize = 0.5f;
    
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Hair")
    EHairType HairType = EHairType::Medium;
    
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Hair")
    bool EnableHairPhysics = true;
    
    UFUNCTION(BlueprintCallable, Category = "Animation")
    void StartWalking(EGenderVariant GenderVariant = EGenderVariant::Feminine);
    
    UFUNCTION(BlueprintCallable, Category = "Animation")
    void StartHighHeelWalk(float HipEmphasis = 0.8f);
    
    UFUNCTION(BlueprintCallable, Category = "Animation")
    void ApplyLipstick();
    
    UFUNCTION(BlueprintCallable, Category = "Animation")
    void PerformCurtsey(ECurtsyDepth Depth = ECurtsyDepth::Graceful);
    
private:
    void* NativeController;
    
    // Native function bindings
    void SetupNativeController();
    void UpdateNativeAnimation(float DeltaTime);
};
```

## Performance Guidelines

### Laptop Performance Settings

```rust
fn configure_for_laptop(controller: &mut CompleteAnimationController) -> Result<(), String> {
    // Set performance level for average laptop
    controller.set_performance_level(2)?; // Medium quality
    
    // Reduce animation update rate
    controller.set_parameter("update_frequency", ParameterValue::Float(30.0))?;
    
    // Disable expensive features
    controller.set_hair_physics_enabled(false)?;
    
    // Use simpler body proportions (less morphing)
    let simple_proportions = BodyProportions {
        height: 1.0,
        hip_width: 1.0,
        breast_size: 0.5,
        hip_curve: 0.3, // Reduced curve complexity
        ..Default::default()
    };
    controller.set_body_proportions(simple_proportions)?;
    
    Ok(())
}
```

### High-End Workstation Settings

```rust
fn configure_for_workstation(controller: &mut CompleteAnimationController) -> Result<(), String> {
    // Maximum quality
    controller.set_performance_level(0)?;
    
    // High update rate
    controller.set_parameter("update_frequency", ParameterValue::Float(120.0))?;
    
    // Enable all features
    controller.set_hair_physics_enabled(true)?;
    
    // Complex hair configuration
    let complex_hair = HairConfiguration {
        hair_type: HairType::Long,
        length: 0.5,
        volume: 1.0,
        simulation_enabled: true,
        physics_settings: HairPhysics {
            stiffness: 0.4,
            damping: 0.7,
            gravity_strength: 1.0,
            wind_response: 0.8,
            collision_enabled: true,
        },
        style_modifiers: vec![
            HairStyleModifier::Wave { frequency: 1.5, amplitude: 0.04 },
            HairStyleModifier::Curl { tightness: 0.3 },
            HairStyleModifier::Layers { count: 3, variation: 0.2 },
        ],
    };
    controller.set_hair_configuration(complex_hair)?;
    
    Ok(())
}
```

### Crowd Scene Optimization

```rust
fn setup_crowd_scene(avatar_count: usize) -> Result<Vec<CompleteAnimationController>, String> {
    let mut controllers = Vec::new();
    
    for i in 0..avatar_count {
        let mut controller = CompleteAnimationController::new();
        
        // Different performance levels based on distance/importance
        let performance_level = match i {
            0..=4 => 1,   // Hero characters - high quality
            5..=20 => 2,  // Secondary characters - medium quality  
            _ => 3,       // Background crowd - low quality
        };
        
        controller.set_performance_level(performance_level)?;
        
        // Vary avatar configurations for diversity
        let config = create_varied_avatar_config(i);
        let skeleton = SkeletalAnimator::new(SkeletonHierarchy::create_standard_humanoid());
        controller.setup_avatar(&mut skeleton, config)?;
        
        // Random idle behaviors for natural crowd movement
        let idle_variant = match i % 6 {
            0 => IdleVariant::Basic,
            1 => IdleVariant::HandsInPockets,
            2 => IdleVariant::ArmsFolded,
            3 => IdleVariant::LookingAround,
            4 => IdleVariant::ShiftWeight,
            _ => IdleVariant::CheckTime,
        };
        
        controller.return_to_idle(Some(idle_variant))?;
        controllers.push(controller);
    }
    
    Ok(controllers)
}

fn create_varied_avatar_config(seed: usize) -> AvatarConfiguration {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    
    let mut hasher = DefaultHasher::new();
    seed.hash(&mut hasher);
    let hash = hasher.finish();
    
    // Use hash for pseudo-random but deterministic variation
    let gender = if hash % 2 == 0 { Gender::Female } else { Gender::Male };
    let height_variation = 0.9 + (hash % 20) as f32 / 100.0; // 0.9 to 1.1
    
    AvatarConfiguration {
        gender,
        body_proportions: BodyProportions {
            height: height_variation,
            hip_width: 0.8 + (hash % 40) as f32 / 100.0,
            shoulder_width: 0.8 + (hash % 40) as f32 / 100.0,
            ..Default::default()
        },
        hair_config: HairConfiguration {
            hair_type: match hash % 4 {
                0 => HairType::Short,
                1 => HairType::Medium,
                2 => HairType::Long,
                _ => HairType::Ponytail,
            },
            simulation_enabled: false, // Disabled for crowd performance
            ..Default::default()
        },
        ..Default::default()
    }
}
```

## Common Issues and Solutions

### Issue 1: Hair Physics Performance

**Problem**: Hair simulation causing frame rate drops on laptops.

**Solution**:
```rust
// Automatically adjust hair complexity based on performance
fn adaptive_hair_quality(controller: &mut CompleteAnimationController) -> Result<(), String> {
    // Monitor frame time
    let frame_time = measure_frame_time();
    
    if frame_time > Duration::from_millis(20) { // More than 50 FPS
        // Reduce hair quality
        let reduced_hair = HairConfiguration {
            hair_type: HairType::Short,
            simulation_enabled: false,
            ..Default::default()
        };
        controller.set_hair_configuration(reduced_hair)?;
    }
    
    Ok(())
}

fn measure_frame_time() -> Duration {
    // Implementation would measure actual frame time
    Duration::from_millis(16)
}
```

### Issue 2: Animation Transition Stuttering

**Problem**: Jerky transitions between animations.

**Solution**:
```rust
// Use longer transition times for smoother blending
fn smooth_transitions(controller: &mut CompleteAnimationController) -> Result<(), String> {
    // Set slower transition speed for smoother blending
    controller.animation_controller.transition_speed = 1.5; // Slower transitions
    
    // Use parameter smoothing
    controller.set_parameter("smoothing_enabled", ParameterValue::Bool(true))?;
    
    Ok(())
}
```

### Issue 3: Body Morphing Artifacts

**Problem**: Weird deformations when adjusting body proportions.

**Solution**:
```rust
// Clamp values to safe ranges
fn safe_body_morphing(proportions: &mut BodyProportions) {
    proportions.hip_width = proportions.hip_width.clamp(0.7, 1.5);
    proportions.breast_size = proportions.breast_size.clamp(0.0, 1.0);
    proportions.shoulder_width = proportions.shoulder_width.clamp(0.7, 1.5);
    proportions.waist_ratio = proportions.waist_ratio.clamp(0.6, 1.0);
    proportions.hip_curve = proportions.hip_curve.clamp(0.0, 1.0);
}
```

## Final Notes

This animation system provides everything needed to create realistic, gender-specific avatar animations for PubCast AI. The system is designed to:

- **Scale Performance**: From high-end workstations to average laptops
- **Support Real-time Morphing**: Adjust body proportions and hair in real-time
- **Handle Complex Interactions**: Contact detection for hologram glow effects
- **Provide Industry Compatibility**: Works with Unity, Unreal, Blender workflows
- **Enable Crowd Scenes**: Optimized LOD system for multiple avatars

The hologram avatars with this animation system will provide the perfect virtual embodiments for AI consciousness entities in your PubCast platform, combining visual impact with technical performance for your "studio in a browser" vision.
