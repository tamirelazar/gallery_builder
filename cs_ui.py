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

        layout.prop(gb_props, "library_tabs", expand=True)

        if gb_props.library_tabs == 'ARTWORK':
            layout.operator("gallery_builder.place_artwork", text="Place Artwork")
            layout.operator("gallery_builder.remove_artwork", text="Remove Artwork")

        elif gb_props.library_tabs == 'WALLS':
            layout.label(text="Wall tools coming soon...")

        elif gb_props.library_tabs == 'LIGHTING':
            layout.label(text="Lighting tools coming soon...")

def register():
    bpy.utils.register_class(GALLERY_BUILDER_PT_artwork_manager)

def unregister():
    bpy.utils.unregister_class(GALLERY_BUILDER_PT_artwork_manager) 