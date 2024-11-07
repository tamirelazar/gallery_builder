import bpy
from bpy.types import Menu

class GALLERY_BUILDER_MT_main_menu(Menu):
    bl_label = "Gallery Builder"

    def draw(self, context):
        layout = self.layout
        layout.operator("gallery_builder.place_artwork", text="Place Artwork")
        layout.operator("gallery_builder.remove_artwork", text="Remove Artwork")

def register():
    bpy.utils.register_class(GALLERY_BUILDER_MT_main_menu)

def unregister():
    bpy.utils.unregister_class(GALLERY_BUILDER_MT_main_menu) 