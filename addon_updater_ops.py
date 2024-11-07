# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

"""Blender UI integrations for the addon updater.

Implements draw calls, popups, and operators that use the addon_updater.
"""

import os
import traceback

import bpy
from bpy.app.handlers import persistent

# Safely import the updater.
# Prevents popups for users with invalid python installs e.g. missing libraries
# and will replace with a fake class instead if it fails (so UI draws work).
try:
    from .addon_updater import Updater as updater
except Exception as e:
    print("ERROR INITIALIZING UPDATER")
    print(str(e))
    traceback.print_exc()

    class SingletonUpdaterNone(object):
        """Fake, bare minimum fields and functions for the updater object."""

        def __init__(self):
            self.invalid_updater = True  # Used to distinguish bad install.

            self.addon = None
            self.verbose = False
            self.use_print_traces = True
            self.error = None
            self.error_msg = None
            self.async_checking = None

        def clear_state(self):
            self.addon = None
            self.verbose = False
            self.invalid_updater = True
            self.error = None
            self.error_msg = None
            self.async_checking = None

        def run_update(self, force, callback, clean):
            pass

        def check_for_update(self, now):
            pass

    updater = SingletonUpdaterNone()
    updater.error = "Error initializing updater module"
    updater.error_msg = str(e)

# Must declare this before classes are loaded, otherwise the bl_idname's will
# not match and have errors. Must be all lowercase and no spaces! Should also
# be unique among any other addons that could exist (using this updater code),
# to avoid clashes in operator registration.
updater.addon = "gallery_builder"


# -----------------------------------------------------------------------------
# Blender version utils
# -----------------------------------------------------------------------------
def make_annotations(cls):
    """Add annotation attribute to fields to avoid Blender 2.8+ warnings"""
    if not hasattr(bpy.app, "version") or bpy.app.version < (2, 80):
        return cls
    if bpy.app.version < (2, 93, 0):
        bl_props = {k: v for k, v in cls.__dict__.items()
                    if isinstance(v, tuple)}
    else:
        bl_props = {k: v for k, v in cls.__dict__.items()
                    if isinstance(v, bpy.props._PropertyDeferred)}
    if bl_props:
        if '__annotations__' not in cls.__dict__:
            setattr(cls, '__annotations__', {})
        annotations = cls.__dict__['__annotations__']
        for k, v in bl_props.items():
            annotations[k] = v
            delattr(cls, k)
    return cls


def layout_split(layout, factor=0.0, align=False):
    """Intermediate method for pre and post blender 2.8 split UI function"""
    if not hasattr(bpy.app, "version") or bpy.app.version < (2, 80):
        return layout.split(percentage=factor, align=align)
    return layout.split(factor=factor, align=align)


def get_user_preferences(context=None):
    """Intermediate method for pre and post blender 2.8 grabbing preferences"""
    if not context:
        context = bpy.context

    prefs = None
    if hasattr(context, "user_preferences"):
        if hasattr(context.user_preferences, "addons"):
            prefs = context.user_preferences.addons.get(__package__, None)
    elif hasattr(context, "preferences"):
        if hasattr(context.preferences, "addons"):
            prefs = context.preferences.addons.get(__package__, None)
    if prefs:
        return prefs.preferences
    # To make the addon stable and non-exception prone, return None
    # raise Exception("Could not fetch user preferences")
    return None


# -----------------------------------------------------------------------------
# Updater operators
# -----------------------------------------------------------------------------


# Simple popup to prompt use to check for update & offer install if available.
class AddonUpdaterInstallPopup(bpy.types.Operator):
    """Check and install update if available"""
    bl_label = "Update {x} addon".format(x=updater.addon)
    bl_idname = updater.addon + ".updater_install_popup"
    bl_description = "Popup to check and display current updates available"
    bl_options = {'REGISTER', 'INTERNAL'}

    # if true, run clean install - ie remove all files before adding new
    # equivalent to deleting the addon and reinstalling, except the
    # updater folder/backup folder remains
    clean_install = bpy.props.BoolProperty(
        name="Clean install",
        description=("If enabled, completely clear the addon's folder before "
                     "installing new update, creating a fresh install"),
        default=False,
        options={'HIDDEN'}
    )

    ignore_enum = bpy.props.EnumProperty(
        name="Process update",
        description="Decide to install, ignore, or defer new addon update",
        items=[
            ("install", "Update Now", "Install update now"),
            ("ignore", "Ignore", "Ignore this update to prevent future popups"),
            ("defer", "Defer", "Defer choice till next blender session")
        ],
        options={'HIDDEN'}
    )

    def check(self, context):
        return True

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        if updater.invalid_updater:
            layout.label(text="Updater module error")
            return
        elif updater.update_ready:
            col = layout.column()
            col.scale_y = 0.7
            col.label(text="Update {} ready!".format(updater.update_version),
                      icon="LOOP_FORWARDS")
            col.label(text="Choose 'Update Now' & press OK to install, ",
                      icon="BLANK1")
            col.label(text="or click outside window to defer", icon="BLANK1")
            row = col.row()
            row.prop(self, "ignore_enum", expand=True)
            col.split()
        elif not updater.update_ready:
            col = layout.column()
            col.scale_y = 0.7
            col.label(text="No updates available")
            col.label(text="Press okay to dismiss dialog")
            # add option to force install
        else:
            # Case: updater.update_ready = None
            # we have not yet checked for the update.
            layout.label(text="Check for update now?")

        # Potentially in future, UI to 'check to select/revert to old version'.

    def execute(self, context):
        # In case of error importing updater.
        if updater.invalid_updater:
            return {'CANCELLED'}

        if updater.manual_only:
            bpy.ops.wm.url_open(url=updater.website)
        elif updater.update_ready:

            # Action based on enum selection.
            if self.ignore_enum == 'defer':
                return {'FINISHED'}
            elif self.ignore_enum == 'ignore':
                updater.ignore_update()
                return {'FINISHED'}

            res = updater.run_update(force=False,
                                     callback=post_update_callback,
                                     clean=self.clean_install)

            # Should return 0, if not something happened.
            if updater.verbose:
                if res == 0:
                    print("Updater returned successful")
                else:
                    print("Updater returned {}, error occurred".format(res))
        elif updater.update_ready is None:
            _ = updater.check_for_update(now=True)

            # Re-launch this dialog.
            atr = AddonUpdaterInstallPopup.bl_idname.split(".")
            getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')
        else:
            updater.print_verbose("Doing nothing, not ready for update")
        return {'FINISHED'}


# List all updater-related classes here
classes = (
    AddonUpdaterInstallPopup,
    # Add other classes like AddonUpdaterCheckNow, AddonUpdaterUpdateNow, etc.
)

def register(bl_info):
    if bpy.app.background:
        return
    for cls in classes:
        make_annotations(cls)
        bpy.utils.register_class(cls)

def unregister():
    if bpy.app.background:
        return
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    updater.clear_state()
