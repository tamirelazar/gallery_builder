import bpy
from bpy.types import Operator

class GALLERY_BUILDER_OT_drop_handler(Operator):
    bl_idname = "gallery_builder.drop_handler"
    bl_label = "Drop Handler"
    bl_description = "Handle drops in the gallery"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Implement drop handling logic here
        self.report({'INFO'}, "Handled drop successfully")
        return {'FINISHED'}

def register():
    bpy.utils.register_class(GALLERY_BUILDER_OT_drop_handler)

def unregister():
    bpy.utils.unregister_class(GALLERY_BUILDER_OT_drop_handler) 