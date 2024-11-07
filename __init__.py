import bpy
import time
import os
import sys
import inspect

PATH = os.path.join(os.path.dirname(__file__), "python_libs")
sys.path.append(PATH)

from . import addon_updater_ops
from . import pyclone_utils
from . import pyclone_props
from . import cs_ui
from . import cs_ops
from . import cs_props
from . import cs_utils
from .pyclone_ops import pc_assembly
from .pyclone_ops import pc_driver
from .pyclone_ops import pc_general
from .pyclone_ops import pc_layout_view
from .pyclone_ops import pc_library
from .pyclone_ops import pc_material
from .pyclone_ops import pc_object
from .pyclone_ops import pc_prompts
from .walls import wall_ops
from .pyclone_ui import pc_view3d_ui_sidebar_assemblies
from .pyclone_ui import pc_view3d_ui_sidebar_object
from .pyclone_ui import pc_text_ui_sidebar_library
from .pyclone_ui import pc_view3d_ui_menu
from .pyclone_ui import pc_view3d_ui_layout_view
from .pyclone_ui import pc_lists

from bpy.app.handlers import persistent

bl_info = {
    "name": "Gallery Builder",
    "author": "Your Name",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "3D Viewport Sidebar",
    "description": "An addon to curate virtual galleries by placing artworks on walls",
    "category": "3D View",
}

@persistent
def load_driver_functions(scene):
    cs_utils.load_custom_driver_functions()

@persistent
def load_library(dummy):
    cs_utils.load_libraries_from_xml(bpy.context)
    cs_utils.load_libraries(bpy.context)
    bpy.context.scene.gallery_builder.library_tabs = bpy.context.scene.gallery_builder.library_tabs

class Gallery_Builder_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = "gallery_builder"

    auto_check_update: bpy.props.BoolProperty(
        name="Auto-check for Update",
        description="If enabled, auto-check for updates using an interval",
        default=False)

    updater_interval_months: bpy.props.IntProperty(
        name='Months',
        description="Number of months between checking for updates",
        default=0,
        min=0)

    updater_interval_days: bpy.props.IntProperty(
        name='Days',
        description="Number of days between checking for updates",
        default=7,
        min=0,
        max=31)

    updater_interval_hours: bpy.props.IntProperty(
        name='Hours',
        description="Number of hours between checking for updates",
        default=0,
        min=0,
        max=23)

    updater_interval_minutes: bpy.props.IntProperty(
        name='Minutes',
        description="Number of minutes between checking for updates",
        default=0,
        min=0,
        max=59)

    def draw(self, context):
        layout = self.layout
        addon_updater_ops.update_settings_ui(self, context)

def register():
    bpy.utils.register_class(Gallery_Builder_AddonPreferences)
    addon_updater_ops.register(bl_info)
    pc_assembly.register()
    pc_driver.register()
    pc_general.register()
    pc_layout_view.register()
    pc_library.register()
    pc_material.register()
    pc_object.register()
    pc_prompts.register()
    pc_view3d_ui_menu.register()
    cs_props.register()
    pyclone_props.register()
    pc_view3d_ui_sidebar_assemblies.register()
    pc_view3d_ui_sidebar_object.register()
    pc_text_ui_sidebar_library.register()
    pc_view3d_ui_layout_view.register()
    cs_ui.register()
    cs_ops.register()
    wall_ops.register()
    pc_lists.register()
    
    # Import and register cs_menus and cs_drop_ops locally to avoid circular import
    from . import cs_menus
    cs_menus.register()
    from . import cs_drop_ops
    cs_drop_ops.register()
    
    cs_utils.addon_version = bl_info['version']
    bpy.app.handlers.load_post.append(load_driver_functions)
    bpy.app.handlers.load_post.append(load_library)

def unregister():
    bpy.utils.unregister_class(Gallery_Builder_AddonPreferences)
    addon_updater_ops.unregister()
    pyclone_props.unregister()
    pc_assembly.unregister()
    pc_driver.unregister()
    pc_general.unregister()
    pc_layout_view.unregister()
    pc_library.unregister()
    pc_material.unregister()
    pc_object.unregister()
    pc_prompts.unregister()
    pc_view3d_ui_menu.unregister() 
    pc_view3d_ui_sidebar_assemblies.unregister()
    pc_view3d_ui_sidebar_object.unregister()
    pc_text_ui_sidebar_library.unregister()
    pc_view3d_ui_layout_view.unregister()
    cs_props.unregister()
    cs_ui.unregister()
    cs_ops.unregister()
    wall_ops.unregister()
    pc_lists.unregister()
    
    # Import and unregister cs_menus and cs_drop_ops locally to avoid circular import
    from . import cs_menus
    cs_menus.unregister()
    from . import cs_drop_ops
    cs_drop_ops.unregister()
    
    bpy.app.handlers.load_post.remove(load_driver_functions)    
    bpy.app.handlers.load_post.remove(load_library)

# Remove the manual call to register()
# This prevents the addon from registering classes multiple times
# Blender handles registration when you enable the addon via Preferences
#if __name__ == '__main__':
#    register()