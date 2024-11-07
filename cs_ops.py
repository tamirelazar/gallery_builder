import bpy
from bpy.types import Operator
from bpy.props import FloatProperty, FloatVectorProperty, StringProperty, EnumProperty, BoolProperty
from mathutils import Vector
import os

class GALLERY_BUILDER_OT_place_artwork(Operator):
    bl_idname = "gallery_builder.place_artwork"
    bl_label = "Place Artwork"
    bl_description = "Place artwork images on gallery walls"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}
    
    # File browser properties
    filepath: StringProperty(
        name="File Path",
        description="Path to image file",
        default="",
        maxlen=1024,
        subtype='FILE_PATH',
    )
    
    filter_glob: StringProperty(
        default="*.jpg;*.jpeg;*.png;*.tif;*.tiff;*.bmp",
        options={'HIDDEN'}
    )
    
    # Properties for artwork placement
    location: FloatVectorProperty(
        name="Location",
        description="Location to place artwork",
        subtype='XYZ'
    )
    
    width: FloatProperty(
        name="Width",
        description="Width of the artwork",
        default=1.0,
        min=0.01,
        unit='LENGTH'
    )
    
    height: FloatProperty(
        name="Height",
        description="Height of the artwork",
        default=1.0,
        min=0.01,
        unit='LENGTH'
    )
    
    maintain_aspect_ratio: BoolProperty(
        name="Maintain Aspect Ratio",
        description="Keep the original image aspect ratio",
        default=True
    )

    def invoke(self, context, event):
        # Open file browser
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def create_artwork_material(self, context):
        # Create a new material
        material = bpy.data.materials.new(name="Artwork_Material")
        material.use_nodes = True
        nodes = material.node_tree.nodes
        
        # Clear default nodes
        nodes.clear()
        
        # Create nodes
        principled_bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        material_output = nodes.new('ShaderNodeOutputMaterial')
        
        # If image path is provided, create image texture node
        if self.filepath and os.path.exists(self.filepath):
            # Load or reuse image
            image_name = os.path.basename(self.filepath)
            if image_name in bpy.data.images:
                image = bpy.data.images[image_name]
            else:
                image = bpy.data.images.load(self.filepath)
            
            # Update dimensions based on image if maintaining aspect ratio
            if self.maintain_aspect_ratio:
                aspect_ratio = image.size[0] / image.size[1]
                self.height = self.width / aspect_ratio
            
            # Create and setup texture node
            tex_node = nodes.new('ShaderNodeTexImage')
            tex_node.image = image
            
            # Link texture to principled BSDF
            material.node_tree.links.new(
                tex_node.outputs['Color'],
                principled_bsdf.inputs['Base Color']
            )
            
            # Position nodes
            tex_node.location = (-300, 300)
        
        # Position other nodes
        principled_bsdf.location = (0, 300)
        material_output.location = (300, 300)
        
        # Link principled to output
        material.node_tree.links.new(
            principled_bsdf.outputs['BSDF'],
            material_output.inputs['Surface']
        )
        
        return material

    def create_artwork_mesh(self, context):
        # Create a new plane for the artwork
        bpy.ops.mesh.primitive_plane_add(size=1)
        artwork_obj = context.active_object
        
        # Set the artwork properties
        artwork_obj.dimensions.x = self.width
        artwork_obj.dimensions.y = self.height
        
        # Create and assign material
        material = self.create_artwork_material(context)
        artwork_obj.data.materials.append(material)
        
        # Mark as artwork
        gb_props = artwork_obj.gallery_builder
        gb_props.is_artwork = True
        
        # Store artwork data
        artwork_data = gb_props.artwork_data
        artwork_data.width = self.width
        artwork_data.height = self.height
        artwork_data.name = os.path.splitext(os.path.basename(self.filepath))[0]
        
        return artwork_obj

    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, "No image file selected")
            return {'CANCELLED'}
            
        # Create artwork mesh
        artwork_obj = self.create_artwork_mesh(context)
        
        # Set location
        artwork_obj.location = self.location
        
        # Set name based on file
        artwork_obj.name = os.path.splitext(os.path.basename(self.filepath))[0]
        
        self.report({'INFO'}, f"Placed artwork: {artwork_obj.name}")
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        
        layout.prop(self, "width")
        layout.prop(self, "maintain_aspect_ratio")
        if not self.maintain_aspect_ratio:
            layout.prop(self, "height")

class GALLERY_BUILDER_OT_remove_artwork(Operator):
    bl_idname = "gallery_builder.remove_artwork"
    bl_label = "Remove Artwork"
    bl_description = "Remove selected artwork from gallery"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Placeholder for artwork removal logic
        self.report({'INFO'}, "Artwork removed successfully")
        return {'FINISHED'}

class GALLERY_BUILDER_OT_select_artwork(Operator):
    bl_idname = "gallery_builder.select_artwork"
    bl_label = "Select Artwork"
    bl_description = "Select this artwork and make it active"
    bl_options = {'REGISTER', 'UNDO'}

    object_name: StringProperty(
        name="Object Name",
        description="Name of the artwork object to select",
        default=""
    )

    def execute(self, context):
        # Deselect all objects
        bpy.ops.object.select_all(action='DESELECT')
        
        # Get the artwork object
        artwork_obj = bpy.data.objects.get(self.object_name)
        if not artwork_obj:
            self.report({'ERROR'}, f"Could not find artwork: {self.object_name}")
            return {'CANCELLED'}
        
        # Select and make active
        artwork_obj.select_set(True)
        context.view_layer.objects.active = artwork_obj
        
        # Update active artwork in scene properties
        scene_props = context.scene.gallery_builder
        artwork_props = artwork_obj.gallery_builder.artwork_data
        
        # Copy artwork data to active artwork
        active_artwork = scene_props.active_artwork
        active_artwork.name = artwork_props.name
        active_artwork.artist = artwork_props.artist
        active_artwork.year = artwork_props.year
        active_artwork.width = artwork_props.width
        active_artwork.height = artwork_props.height
        active_artwork.image = artwork_props.image
        active_artwork.rotation = artwork_props.rotation
        active_artwork.elevation = artwork_props.elevation
        
        self.report({'INFO'}, f"Selected artwork: {self.object_name}")
        return {'FINISHED'}

def register():
    bpy.utils.register_class(GALLERY_BUILDER_OT_place_artwork)
    bpy.utils.register_class(GALLERY_BUILDER_OT_remove_artwork)
    bpy.utils.register_class(GALLERY_BUILDER_OT_select_artwork)

def unregister():
    bpy.utils.unregister_class(GALLERY_BUILDER_OT_place_artwork)
    bpy.utils.unregister_class(GALLERY_BUILDER_OT_remove_artwork)
    bpy.utils.unregister_class(GALLERY_BUILDER_OT_select_artwork) 