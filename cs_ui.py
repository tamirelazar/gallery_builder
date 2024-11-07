import bpy
from bpy.types import Panel

class GALLERY_BUILDER_PT_artwork_manager(Panel):
    bl_label = "Artwork Manager"
    bl_idname = "GALLERY_BUILDER_PT_artwork_manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Gallery Builder'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        gb_props = scene.gallery_builder

        # Main tabs
        layout.prop(gb_props, "library_tabs", expand=True)

        if gb_props.library_tabs == 'ARTWORK':
            # Artwork Section
            box = layout.box()
            col = box.column(align=True)
            
            # Place Artwork Button with Options
            row = col.row(align=True)
            row.scale_y = 1.5
            place_op = row.operator("gallery_builder.place_artwork", text="Place Artwork", icon='IMAGE_DATA')
            
            # Quick Settings
            col.separator()
            row = col.row(align=True)
            row.prop(gb_props, "artwork_placement_mode", text="")
            if gb_props.artwork_placement_mode == 'WALL':
                row.prop(gb_props, "wall_offset", text="Offset")
            
            # Active Artwork Info
            if gb_props.active_artwork:
                artwork = gb_props.active_artwork
                box = layout.box()
                col = box.column(align=True)
                col.label(text="Active Artwork:", icon='OUTLINER_OB_IMAGE')
                
                # Artwork Details
                col.prop(artwork, "name", text="Name")
                col.prop(artwork, "artist", text="Artist")
                col.prop(artwork, "year", text="Year")
                
                # Dimensions
                row = col.row(align=True)
                row.prop(artwork, "width", text="Width")
                row.prop(artwork, "height", text="Height")
                
                # Image Preview
                if artwork.image:
                    col.template_ID_preview(artwork, "image", open="image.open")
                
                # Transform Options
                box_sub = box.box()
                col = box_sub.column(align=True)
                col.label(text="Transform:", icon='TRANSFORM')
                row = col.row(align=True)
                row.prop(artwork, "rotation", text="Rotation")
                row.prop(artwork, "elevation", text="Height")
            
            # Artwork List
            box = layout.box()
            col = box.column(align=True)
            col.label(text="Placed Artworks:", icon='RENDERLAYERS')
            
            # Filter Options
            row = col.row(align=True)
            row.prop(gb_props, "artwork_filter", text="", icon='FILTER')
            row.prop(gb_props, "show_dimensions", icon='DRIVER_DISTANCE', text="")
            row.prop(gb_props, "show_hidden", icon='HIDE_OFF', text="")
            
            # List all artwork objects in the scene
            for obj in context.scene.objects:
                if obj.gallery_builder.is_artwork:
                    if not gb_props.show_hidden and obj.hide_viewport:
                        continue
                        
                    row = col.row(align=True)
                    # Selection
                    icon = 'RESTRICT_SELECT_OFF' if obj == context.active_object else 'RESTRICT_SELECT_ON'
                    row.operator("gallery_builder.select_artwork", text="", icon=icon).object_name = obj.name
                    
                    # Name
                    row.label(text=obj.name, icon='IMAGE_DATA')
                    
                    # Dimensions if enabled
                    if gb_props.show_dimensions:
                        sub = row.row()
                        sub.scale_x = 0.6
                        sub.label(text=f"{obj.dimensions.x:.2f}x{obj.dimensions.y:.2f}")
                    
                    # Visibility toggle
                    icon = 'HIDE_ON' if obj.hide_viewport else 'HIDE_OFF'
                    row.prop(obj, "hide_viewport", text="", icon=icon, emboss=False)
                    
                    # Remove button
                    op = row.operator("gallery_builder.remove_artwork", text="", icon='X')
                    op.object_name = obj.name

        elif gb_props.library_tabs == 'WALLS':
            box = layout.box()
            col = box.column(align=True)
            col.label(text="Wall Tools", icon='MESH_PLANE')
            col.prop(gb_props, "wall_height", text="Default Height")
            col.label(text="Wall tools coming soon...")

        elif gb_props.library_tabs == 'LIGHTING':
            box = layout.box()
            col = box.column(align=True)
            col.label(text="Lighting Tools", icon='LIGHT')
            col.label(text="Lighting tools coming soon...")

        # Settings Section
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Settings", icon='PREFERENCES')
        col.prop(gb_props, "auto_align_to_walls", text="Auto-align to Walls")
        col.prop(gb_props, "maintain_aspect_ratio", text="Keep Aspect Ratio")

def register():
    bpy.utils.register_class(GALLERY_BUILDER_PT_artwork_manager)

def unregister():
    bpy.utils.unregister_class(GALLERY_BUILDER_PT_artwork_manager) 