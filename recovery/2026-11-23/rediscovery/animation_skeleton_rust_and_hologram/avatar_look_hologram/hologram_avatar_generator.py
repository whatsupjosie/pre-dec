import bpy
import bmesh
import mathutils
from mathutils import Vector
import math

class HologramAvatarGenerator:
    """
    Generate hologram avatar base meshes based on the energy being reference images.
    Creates optimized topology suitable for animation and energy shader effects.
    """
    
    def __init__(self):
        self.clear_scene()
        
    def clear_scene(self):
        """Clear all mesh objects from the scene"""
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        
    def create_base_humanoid(self, name="HologramAvatar", scale=1.0, gender="neutral"):
        """
        Create base humanoid mesh with proper topology for hologram effect
        
        Args:
            name: Object name
            scale: Overall scale factor
            gender: "male", "female", or "neutral"
        """
        
        # Create new mesh and object
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        
        # Create bmesh for easier mesh generation
        bm = bmesh.new()
        
        # Generate body segments
        self._create_torso(bm, scale, gender)
        self._create_head(bm, scale)
        self._create_arms(bm, scale)
        self._create_legs(bm, scale, gender)
        
        # Apply smooth shading and optimize for hologram effect
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        
        # Update mesh
        bm.to_mesh(mesh)
        bm.free()
        
        # Set smooth shading
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.shade_smooth()
        
        # Add subdivision surface modifier for smooth curves
        subdiv = obj.modifiers.new(name="Subdivision", type='SUBSURF')
        subdiv.levels = 1
        subdiv.render_levels = 2
        
        # Create vertex groups for contact detection
        self._create_vertex_groups(obj)
        
        # Setup UV mapping
        self._setup_uv_mapping(obj)
        
        return obj
        
    def _create_torso(self, bm, scale, gender):
        """Create torso geometry"""
        # Define torso profile points (side view proportions from reference images)
        torso_points = [
            (0.0, -0.15, 1.2),   # Top of torso
            (0.18, -0.1, 1.1),   # Chest width
            (0.16, -0.08, 0.9),  # Waist
            (0.18, -0.12, 0.7),  # Hips
            (0.15, -0.1, 0.5),   # Lower torso
        ]
        
        # Adjust for gender if specified
        if gender == "female":
            torso_points[1] = (0.16, -0.08, 1.1)  # Narrower shoulders
            torso_points[3] = (0.22, -0.14, 0.7)  # Wider hips
        elif gender == "male":
            torso_points[1] = (0.22, -0.12, 1.1)  # Broader shoulders
            torso_points[3] = (0.16, -0.1, 0.7)   # Narrower hips
            
        # Scale all points
        torso_points = [(x*scale, y*scale, z*scale) for x, y, z in torso_points]
        
        # Create torso using extrusion method for clean topology
        segments = 12  # Radial segments
        
        for i, (x, y, z) in enumerate(torso_points):
            for j in range(segments):
                angle = (j / segments) * 2 * math.pi
                vx = x * math.cos(angle)
                vy = x * math.sin(angle) + y
                
                vert = bm.verts.new((vx, vy, z))
                
                # Add to appropriate vertex group data
                if i == 1:  # Chest area
                    vert.tag = True  # Mark for chest vertex group
                    
    def _create_head(self, bm, scale):
        """Create head geometry optimized for hologram effect"""
        # Head is simplified sphere for performance
        bmesh.ops.create_uvsphere(
            bm, 
            u_segments=8, 
            v_segments=6, 
            radius=0.12*scale
        )
        
        # Move head to correct position
        head_verts = [v for v in bm.verts if not v.select]
        for v in bm.verts:
            if not v.select:  # These are the new head verts
                v.co.z += 1.4 * scale
                
    def _create_arms(self, bm, scale):
        """Create arm geometry with proper joint placement"""
        arm_segments = [
            # Left arm
            [(0.18*scale, -0.05*scale, 1.1*scale),   # Shoulder
             (0.35*scale, -0.05*scale, 1.05*scale),  # Upper arm
             (0.48*scale, -0.05*scale, 1.0*scale),   # Elbow
             (0.58*scale, -0.05*scale, 0.95*scale)], # Hand
            
            # Right arm (mirrored)
            [(-0.18*scale, -0.05*scale, 1.1*scale),
             (-0.35*scale, -0.05*scale, 1.05*scale),
             (-0.48*scale, -0.05*scale, 1.0*scale),
             (-0.58*scale, -0.05*scale, 0.95*scale)]
        ]
        
        for arm in arm_segments:
            self._create_limb(bm, arm, radius=0.04*scale)
            
    def _create_legs(self, bm, scale, gender):
        """Create leg geometry"""
        hip_width = 0.16*scale if gender == "male" else 0.18*scale
        
        leg_segments = [
            # Left leg
            [(hip_width/2, -0.08*scale, 0.5*scale),    # Hip
             (hip_width/2, -0.06*scale, 0.25*scale),   # Upper leg
             (hip_width/2, -0.04*scale, 0.0*scale),    # Knee
             (hip_width/2, -0.02*scale, -0.25*scale),  # Lower leg
             (hip_width/2, 0.04*scale, -0.45*scale)],  # Foot
            
            # Right leg
            [(-hip_width/2, -0.08*scale, 0.5*scale),
             (-hip_width/2, -0.06*scale, 0.25*scale),
             (-hip_width/2, -0.04*scale, 0.0*scale),
             (-hip_width/2, -0.02*scale, -0.25*scale),
             (-hip_width/2, 0.04*scale, -0.45*scale)]
        ]
        
        for leg in leg_segments:
            self._create_limb(bm, leg, radius=0.06*scale)
            
    def _create_limb(self, bm, points, radius=0.05, segments=6):
        """Create a limb segment using cylinder extrusion"""
        prev_verts = []
        
        for i, point in enumerate(points):
            # Create circular cross-section
            current_verts = []
            for j in range(segments):
                angle = (j / segments) * 2 * math.pi
                x = point[0] + radius * math.cos(angle)
                y = point[1] + radius * math.sin(angle)
                z = point[2]
                
                vert = bm.verts.new((x, y, z))
                current_verts.append(vert)
                
            # Connect to previous segment
            if prev_verts:
                for j in range(segments):
                    next_j = (j + 1) % segments
                    
                    # Create quad faces
                    face = bm.faces.new([
                        prev_verts[j],
                        prev_verts[next_j], 
                        current_verts[next_j],
                        current_verts[j]
                    ])
                    
            prev_verts = current_verts
            
    def _create_vertex_groups(self, obj):
        """Create vertex groups for contact detection and animation"""
        contact_points = [
            "head", "neck", "chest", "left_shoulder", "right_shoulder",
            "left_hand", "right_hand", "left_hip", "right_hip",
            "left_foot", "right_foot"
        ]
        
        for group_name in contact_points:
            obj.vertex_groups.new(name=group_name)
            
    def _setup_uv_mapping(self, obj):
        """Setup UV mapping optimized for energy flow effects"""
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        
        # Select all faces
        bpy.ops.mesh.select_all(action='SELECT')
        
        # Smart UV project for clean unwrapping
        bpy.ops.uv.smart_project(
            angle_limit=66,
            island_margin=0.02,
            area_weight=0.0,
            correct_aspect=True,
            scale_to_bounds=False
        )
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
    def create_dancing_pose_variant(self, base_obj, pose_name="DancingPose"):
        """Create a variant with dancing pose for reference"""
        # Duplicate the object
        dancing_obj = base_obj.copy()
        dancing_obj.data = base_obj.data.copy()
        dancing_obj.name = pose_name
        bpy.context.collection.objects.link(dancing_obj)
        
        # Apply basic dancing pose deformation
        # This is a simplified version - full poses would come from mocap data
        bpy.context.view_layer.objects.active = dancing_obj
        bpy.ops.object.mode_set(mode='EDIT')
        
        # Get vertex positions and apply dance-like modifications
        mesh = bmesh.from_mesh(dancing_obj.data)
        
        # Raise arms (simplified)
        for vert in mesh.verts:
            if vert.co.x > 0.2 or vert.co.x < -0.2:  # Arm vertices
                if vert.co.z > 0.8:  # Upper arm area
                    vert.co.z += 0.1
                    
        # Slight hip rotation
        for vert in mesh.verts:
            if abs(vert.co.x) < 0.2 and vert.co.z < 0.7 and vert.co.z > 0.3:
                # Rotate around Z axis
                angle = 0.1  # Small rotation
                new_x = vert.co.x * math.cos(angle) - vert.co.y * math.sin(angle)
                new_y = vert.co.x * math.sin(angle) + vert.co.y * math.cos(angle)
                vert.co.x = new_x
                vert.co.y = new_y
                
        mesh.to_mesh(dancing_obj.data)
        mesh.free()
        bpy.ops.object.mode_set(mode='OBJECT')
        
        return dancing_obj
        
    def setup_hologram_material(self, obj, material_name="HologramMaterial"):
        """Setup Blender material for hologram effect"""
        # Create material
        mat = bpy.data.materials.new(name=material_name)
        mat.use_nodes = True
        obj.data.materials.append(mat)
        
        # Get material nodes
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        
        # Clear default nodes
        nodes.clear()
        
        # Create material nodes for hologram effect
        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (400, 0)
        
        # Mix shader for transparency
        mix_shader = nodes.new(type='ShaderNodeMixShader')
        mix_shader.location = (200, 0)
        
        # Emission shader for glow
        emission = nodes.new(type='ShaderNodeEmission')
        emission.location = (0, 100)
        emission.inputs['Color'].default_value = (0, 1, 1, 1)  # Cyan
        emission.inputs['Strength'].default_value = 3.0
        
        # Transparent shader
        transparent = nodes.new(type='ShaderNodeBsdfTransparent')
        transparent.location = (0, -100)
        
        # Fresnel for edge glow
        fresnel = nodes.new(type='ShaderNodeFresnel')
        fresnel.location = (-200, 0)
        fresnel.inputs['IOR'].default_value = 1.8
        
        # Color ramp for fresnel control
        color_ramp = nodes.new(type='ShaderNodeValToRGB')
        color_ramp.location = (-400, 0)
        color_ramp.color_ramp.elements[0].position = 0.3
        color_ramp.color_ramp.elements[1].position = 0.8
        
        # Noise texture for energy distortion
        noise = nodes.new(type='ShaderNodeTexNoise')
        noise.location = (-600, -200)
        noise.inputs['Scale'].default_value = 5.0
        noise.inputs['Detail'].default_value = 8.0
        
        # Math nodes for animation
        math_add = nodes.new(type='ShaderNodeMath')
        math_add.operation = 'ADD'
        math_add.location = (-400, -200)
        math_add.inputs[1].default_value = 0.5
        
        # Texture coordinate for noise
        tex_coord = nodes.new(type='ShaderNodeTexCoord')
        tex_coord.location = (-800, -200)
        
        # Connect nodes
        links.new(tex_coord.outputs['Object'], noise.inputs['Vector'])
        links.new(noise.outputs['Fac'], math_add.inputs[0])
        links.new(fresnel.outputs['Fac'], color_ramp.inputs['Fac'])
        links.new(color_ramp.outputs['Color'], mix_shader.inputs['Fac'])
        links.new(emission.outputs['Emission'], mix_shader.inputs[1])
        links.new(transparent.outputs['BSDF'], mix_shader.inputs[2])
        links.new(mix_shader.outputs['Shader'], output.inputs['Surface'])
        
        # Set material properties
        mat.blend_method = 'BLEND'
        mat.use_backface_culling = False
        
        return mat

def create_hologram_avatar_scene():
    """Main function to create complete hologram avatar scene"""
    generator = HologramAvatarGenerator()
    
    # Create male and female variants
    male_avatar = generator.create_base_humanoid("MaleHologram", scale=1.0, gender="male")
    female_avatar = generator.create_base_humanoid("FemaleHologram", scale=1.0, gender="female")
    
    # Position them side by side
    male_avatar.location = (1.5, 0, 0)
    female_avatar.location = (-1.5, 0, 0)
    
    # Create dancing pose variants
    male_dancing = generator.create_dancing_pose_variant(male_avatar, "MaleDancing")
    female_dancing = generator.create_dancing_pose_variant(female_avatar, "FemaleDancing") 
    
    # Position dancing variants
    male_dancing.location = (1.5, 3, 0)
    female_dancing.location = (-1.5, 3, 0)
    
    # Setup materials
    male_mat = generator.setup_hologram_material(male_avatar, "HologramMale")
    female_mat = generator.setup_hologram_material(female_avatar, "HologramFemale")
    
    # Apply materials to dancing variants
    male_dancing.data.materials.append(male_mat)
    female_dancing.data.materials.append(female_mat)
    
    # Setup scene for rendering
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.samples = 128
    bpy.context.scene.world.use_nodes = True
    
    # Dark background
    world = bpy.context.scene.world
    bg_node = world.node_tree.nodes['Background']
    bg_node.inputs['Color'].default_value = (0.02, 0.02, 0.08, 1.0)
    bg_node.inputs['Strength'].default_value = 0.1
    
    # Add basic lighting
    bpy.ops.object.light_add(type='AREA', location=(5, 5, 5))
    light = bpy.context.object
    light.data.energy = 50
    light.data.color = (0.8, 0.9, 1.0)
    
    print("Hologram avatar scene created successfully!")
    print("Objects created: MaleHologram, FemaleHologram, MaleDancing, FemaleDancing")
    print("Materials: HologramMale, HologramFemale")
    print("Ready for export to Unity, Unreal, or further customization")

# Run the script
if __name__ == "__main__":
    create_hologram_avatar_scene()
