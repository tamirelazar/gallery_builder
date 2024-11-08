import bpy
import os
import time
import math
import inspect
import sys
import codecs
import subprocess
import shutil
import mathutils
from mathutils import Vector
import bmesh
import bgl
import blf
import gpu
from mathutils.geometry import intersect_line_plane
from gpu_extras.batch import batch_for_shader
from bpy_extras.view3d_utils import region_2d_to_location_3d, region_2d_to_vector_3d
from bpy_extras.io_utils import ImportHelper
from pc_lib import pc_utils, pc_unit, pc_types, pc_snap
from bpy_extras import view3d_utils
from gpu_extras.presets import draw_circle_2d
from . import addon_updater_ops
from . import hb_utils
from . import pyclone_utils
from . import hb_utils
from . import hb_paths
from . import hb_props
from .walls import wall_library

def get_current_view_rotation(context):
    '''
    Gets the current view rotation for creating thumbnails
    '''
    for window in context.window_manager.windows:
        screen = window.screen

        for area in screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        return space.region_3d.view_rotation

    return (0,0,0)

class home_builder_OT_about_home_builder(bpy.types.Operator):
    bl_idname = "home_builder.about_home_builder"
    bl_label = "About Home Builder"
    bl_description = "Show the about home builder interface"

    tabs: bpy.props.EnumProperty(name="Library Tabs",
                       items=[('VERSION',"Version","Show the Home Builder Version"),
                              ('INSTALLED_LIBRARIES',"Installed Libraries","Show the Installed Libraries"),
                              ('TRAINING',"Training","Show the Training Videos")],
                       default='VERSION')

    def invoke(self,context,event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=500)

    def execute(self, context):  
        return {'FINISHED'}

    def get_library_icon(self,library):
        if library.library_type == 'PRODUCTS':
            return  'META_CUBE'
        if library.library_type == 'DECORATIONS':
            return  'SCENE_DATA'
        if library.library_type == 'STARTERS':
            return  'STICKY_UVS_LOC'
        if library.library_type == 'INSERTS':
            return  'STICKY_UVS_VERT'
        if library.library_type == 'PARTS':
            return  'STICKY_UVS_DISABLE'
        if library.library_type == 'BUILD_LIBRARY':
            return  'USER'            
        if library.library_type == 'MATERIALS':
            return  'MATERIAL_DATA'
        return 'BLANK1'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        wm = context.window_manager        
        wm_props = wm.home_builder
        
        row = layout.row(align=True)
        row.scale_y = 1.2
        row.prop_enum(self, "tabs", 'VERSION',icon='INFO')
        row.prop_enum(self, "tabs", 'INSTALLED_LIBRARIES',icon='ASSET_MANAGER')
        row.prop_enum(self, "tabs", 'TRAINING',icon='QUESTION')

        if self.tabs == 'VERSION':
            main_box = layout.box()
            version = hb_utils.addon_version
            row = main_box.row()
            row.label(text="Home Builder Version " + str(version[0]) + "." + str(version[1])+ "." + str(version[2]) + " (BETA)")
            if addon_updater_ops.updater.update_ready == True:
                row.separator()
                addon_updater_ops.update_notice_box_ui(self,context,row)        
            else:
                row.separator()
                row.operator('home_builder.updater_check_now',text="Check for Updates",icon='FILE_REFRESH')

        if self.tabs == 'INSTALLED_LIBRARIES':
            main_box = layout.box()
            row = main_box.row()
            # row.label(text="Installed Libraries")
            # row.label(text=" ")
            row.operator('home_builder.create_new_external_library',text="Create Library",icon='ADD')
            row.operator('home_builder.add_external_library',text="Install Library",icon='IMPORT')
            row.operator('home_builder.save_library_settings',text="Save Settings",icon='CHECKMARK')
            
            row = main_box.row()
            row.alignment = 'LEFT'
            row.prop(wm_props,'show_built_in_asset_libraries',text="Built-In Libraries",icon='DISCLOSURE_TRI_DOWN' if wm_props.show_built_in_asset_libraries else 'DISCLOSURE_TRI_RIGHT',emboss=False)
            row.operator('home_builder.open_browser_window',text="Open Folder in File Browser",icon='WINDOW').path = hb_paths.get_built_in_asset_path()
            if wm_props.show_built_in_asset_libraries:
                col = main_box.column(align=True)
                for lib in wm_props.asset_libraries:
                    if lib.is_external_library == False:
                        row = col.row()
                        row.label(text="",icon=self.get_library_icon(lib))
                        row.prop(lib,'enabled',text=lib.name)
                        
                    
            for ex_lib in wm_props.library_packages:
                ex_lib_box = main_box.box()
                row = ex_lib_box.row()
                if os.path.exists(ex_lib.package_path):
                    path = ex_lib.package_path
                    if path[-1] == '\\':
                        dir_name = os.path.dirname(ex_lib.package_path)
                        folder_name = os.path.basename(dir_name)
                    else:
                        dir_name = os.path.dirname(ex_lib.package_path + "\\")
                        folder_name = os.path.basename(dir_name)
                    row.alignment = 'LEFT'
                    row.prop(ex_lib,'expand',text="",icon='DISCLOSURE_TRI_DOWN' if ex_lib.expand else 'DISCLOSURE_TRI_RIGHT',emboss=False)
                    row.prop(ex_lib,'enabled',text=folder_name)
                else:
                    row.prop(ex_lib,'expand',text="",icon='DISCLOSURE_TRI_DOWN' if ex_lib.expand else 'DISCLOSURE_TRI_RIGHT',emboss=False)
                    row.prop(ex_lib,'enabled',text="")
                    row.prop(ex_lib,'package_path',text="Set Path")
                    row.operator('home_builder.delete_external_library',text="",icon='X',emboss=False).package_path = ex_lib.package_path
                    
                if ex_lib.expand:
                    mat_lib_count = 0
                    deco_lib_count = 0
                    build_lib_count = 0
                    product_lib_count = 0                    
                    for asset_lib in ex_lib.asset_libraries:
                        if asset_lib.library_type == 'MATERIALS':
                            mat_lib_count += 1
                        if asset_lib.library_type == 'DECORATIONS':
                            deco_lib_count += 1
                        if asset_lib.library_type == 'BUILD_LIBRARY':
                            build_lib_count += 1
                        if asset_lib.library_type == 'PRODUCTS':
                            product_lib_count += 1                                                                        
                    row = ex_lib_box.row()
                    row.label(text="",icon='BLANK1')
                    row.label(text="Material",icon='MATERIAL_DATA')
                    row.label(text="Decoration",icon='SCENE_DATA')
                    row.label(text="Build",icon='USER')
                    row.label(text="Product",icon='META_CUBE')
                    row = ex_lib_box.row()
                    row.label(text="",icon='BLANK1')
                    row.label(text=str(mat_lib_count))
                    row.label(text=str(deco_lib_count))
                    row.label(text=str(build_lib_count))
                    row.label(text=str(product_lib_count))                    
                    row = ex_lib_box.row()
                    row.label(text="",icon='BLANK1')
                    row.prop(ex_lib,'package_path',text="Set Path")
                    row.operator('home_builder.delete_external_library',text="",icon='X',emboss=False).package_path = ex_lib.package_path

        if self.tabs == 'TRAINING':
            main_box = layout.box()
            row = main_box.row()
            row.scale_y = 2
            row.operator('wm.url_open',text="Home Builder Online Documentation",icon='HELP').url = "https://creativedesigner3d.github.io/home_builder_3_docs/"


class home_builder_OT_update_library_xml(bpy.types.Operator):
    bl_idname = "home_builder.update_library_xml"
    bl_label = "Update Library XMl"
    bl_description = "This updates the library xml that stores information about what libraries are active"

    def execute(self, context):
        wm_props = context.window_manager.home_builder
        file_path = hb_paths.get_library_path_xml()
        xml = pc_types.HB_XML()
        root = xml.create_tree()
        paths = xml.add_element(root,'LibraryPaths')
        packages = xml.add_element(paths,'Packages')
        for ex_lib in wm_props.library_packages:
            if os.path.exists(ex_lib.package_path):
                lib_package = xml.add_element(packages,'Package',ex_lib.package_path)
                xml.add_element_with_text(lib_package,'Enabled',str(ex_lib.enabled))

        xml.write(file_path)
        return {'FINISHED'}


class home_builder_OT_todo(bpy.types.Operator):
    bl_idname = "home_builder.todo"
    bl_label = "TODO"
    bl_description = "This command has not been implemented yet"

    def execute(self, context):
        print("NOT IMPLEMENTED: TODO")
        return {'FINISHED'}


class home_builder_OT_load_library(bpy.types.Operator):
    bl_idname = "home_builder.load_library"
    bl_label = "Reload Library"

    def invoke(self,context,event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=500)

    def execute(self, context):
        hb_utils.load_libraries(context)
        hb_utils.load_custom_driver_functions()
        prefs = context.preferences
        asset_lib = prefs.filepaths.asset_libraries.get('home_builder_library')
        library = hb_utils.get_active_library(context)
        if library:
            asset_lib.path = library.library_path

            for workspace in bpy.data.workspaces:
                workspace.asset_library_ref = "home_builder_library"
            
            if bpy.ops.asset.library_refresh.poll():
                bpy.ops.asset.library_refresh()        
        return {'FINISHED'}

    def draw(self, context):
        prefs = context.preferences
        paths = prefs.filepaths

        layout = self.layout
        layout.label(text="Auto Run Python Scripts needs to be enabled for Home Builder Library Data.")
        layout.label(text="Check the box below and click OK to continue.")
        layout.prop(paths, "use_scripts_auto_execute")


class home_builder_OT_add_external_library(bpy.types.Operator, ImportHelper):
    bl_idname = "home_builder.add_external_library"
    bl_label = "Add External Library"
    bl_description = "Add a new library"

    directory: bpy.props.StringProperty(name="Directory",subtype='DIR_PATH')
    filter_glob: bpy.props.StringProperty(default="*.blend", options={'HIDDEN'})
    display_type: bpy.props.EnumProperty(name="Display Type",
                                        items=[('DEFAULT',"Standard","Standard"),
                                               ('LIST_VERTICAL',"Standard","Standard"),
                                               ('LIST_HORIZONTAL',"Standard","Standard"),
                                               ('THUMBNAIL',"Blum Soft Close","Blum Soft Close")],
                                        default='LIST_VERTICAL')
    hide_props_region: bpy.props.BoolProperty(name="Hide Props Region",default=True)

    def invoke(self, context, event):
        self.display_type = 'LIST_VERTICAL'
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        wm_props = context.window_manager.home_builder
        lib = wm_props.library_packages.add()
        lib.name = self.directory
        lib.package_path = self.directory
        lib.enabled = True
        hb_utils.load_libraries(context)
        return {'FINISHED'}


class home_builder_OT_delete_external_library(bpy.types.Operator):
    bl_idname = "home_builder.delete_external_library"
    bl_label = "Delete External Library"
    bl_description = "Delete a new library"

    package_path: bpy.props.StringProperty(name="Package Path",subtype='DIR_PATH')

    def execute(self, context):
        wm_props = context.window_manager.home_builder
        for i, package in enumerate(wm_props.library_packages):
            if package.package_path == self.package_path:
                wm_props.library_packages.remove(i)
        bpy.ops.home_builder.update_library_xml()
        hb_utils.load_libraries(context)
        return {'FINISHED'}


class home_builder_OT_create_new_external_library(bpy.types.Operator, ImportHelper):
    bl_idname = "home_builder.create_new_external_library"
    bl_label = "Create New External Library"
    bl_description = "This allows you to create a new external library"

    directory: bpy.props.StringProperty(name="Directory",subtype='DIR_PATH')
    filter_glob: bpy.props.StringProperty(default="*.blend", options={'HIDDEN'})
    display_type: bpy.props.EnumProperty(name="Display Type",
                                        items=[('DEFAULT',"Standard","Standard"),
                                               ('LIST_VERTICAL',"Standard","Standard"),
                                               ('LIST_HORIZONTAL',"Standard","Standard"),
                                               ('THUMBNAIL',"Blum Soft Close","Blum Soft Close")],
                                        default='LIST_VERTICAL')
    hide_props_region: bpy.props.BoolProperty(name="Hide Props Region",default=False)
    asset_libraries: bpy.props.CollectionProperty(
        type=hb_props.Asset_Library,
        description="Collection of all asset libraries loaded into Home Builder")
    
    library_pack_name: bpy.props.StringProperty(name="Library Pack Name",default="New Library Pack Name")
    remove_libraries: bpy.props.BoolProperty(name="Hide Props Region",default=False)

    def invoke(self, context, event):
        self.load_libraries(context)
        self.display_type = 'LIST_VERTICAL'
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def load_libraries(self,context):
        for library in self.asset_libraries:
            self.asset_libraries.remove(0)

        wm = context.window_manager        
        wm_props = wm.home_builder        
        for lib in wm_props.asset_libraries:
            if lib.is_external_library == False:     
                new_lib = self.asset_libraries.add()  
                new_lib.name = lib.name
                new_lib.enabled = False
                new_lib.library_type = lib.library_type
                new_lib.library_path = lib.library_path

    def execute(self, context):
        wm_props = context.window_manager.home_builder

        libraries = []
        for lib in self.asset_libraries:
            if lib.enabled:
                libraries.append(lib)

        library_pack_path = os.path.join(self.directory,self.library_pack_name)
        deco_path = os.path.join(library_pack_path,"decorations")
        mat_path = os.path.join(library_pack_path,"materials")
        os.makedirs(deco_path)
        os.makedirs(mat_path)
        for library in libraries:
            if library.library_type == 'DECORATIONS':
                shutil.copytree(os.path.dirname(library.library_path),os.path.join(deco_path,library.name))
            if library.library_type == 'MATERIALS':         
                shutil.copytree(os.path.dirname(library.library_path),os.path.join(mat_path,library.name))

        lib = wm_props.library_packages.add()
        lib.name = self.library_pack_name
        lib.package_path = library_pack_path
        lib.enabled = True
        hb_utils.load_libraries(context)
        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.prop(self,'library_pack_name',text="Name")
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Decoration Libraries",icon='SCENE_DATA')  
        for lib in self.asset_libraries:
            if lib.library_type == 'DECORATIONS':
                col.prop(lib,'enabled',text=lib.name)
        col.separator()
        col.label(text="Material Libraries",icon='MATERIAL_DATA') 
        for lib in self.asset_libraries:
            if lib.library_type == 'MATERIALS':
                col.prop(lib,'enabled',text=lib.name)                       

class home_builder_OT_update_library_path(bpy.types.Operator):
    bl_idname = "home_builder.update_library_path"
    bl_label = "Update Library Path"
    bl_description = "Change the active library category"

    asset_type: bpy.props.StringProperty(name="Asset Type")
    asset_path: bpy.props.StringProperty(name="Asset Path")
    asset_folder: bpy.props.StringProperty(name="Asset Path")

    def execute(self, context):
        wm_props = context.window_manager.home_builder
        scene_props = context.scene.home_builder

        sel_library = None

        for library in wm_props.asset_libraries:
            if library.library_path == self.asset_path:
                sel_library = library
                break

        prefs = context.preferences
        asset_lib = prefs.filepaths.asset_libraries.get("home_builder_library")  

        if scene_props.library_tabs == 'PRODUCTS':
            wm_props.active_product_library_name = sel_library.name

        if scene_props.library_tabs == 'BUILD':
            if scene_props.build_tabs == 'STARTERS':
                wm_props.active_starter_library_name = sel_library.name
            if scene_props.build_tabs == 'INSERTS':
                wm_props.active_insert_library_name = sel_library.name
            if scene_props.build_tabs == 'PARTS':
                wm_props.active_part_library_name = sel_library.name
            if scene_props.build_tabs == 'LIBRARY':
                wm_props.active_build_library_name = sel_library.name

        if scene_props.library_tabs == 'DECORATIONS':
            wm_props.active_decorations_library_name = sel_library.name
            
        if scene_props.library_tabs == 'MATERIALS':
            wm_props.active_materials_library_name = sel_library.name 
        
        asset_lib.path = os.path.join(self.asset_path)
        bpy.ops.asset.library_refresh()
        return {'FINISHED'}

class home_builder_OT_show_library_material_pointers(bpy.types.Operator):
    bl_idname = "home_builder.show_library_material_pointers"
    bl_label = "Library Material Pointers"
    bl_description = "Show the material pointers for the library"

    library_name: bpy.props.StringProperty(name="Library Name")

    def invoke(self,context,event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=550)

    def execute(self, context):  
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        scene_props = context.scene.home_builder
        box = layout.box()
        box.operator('home_builder.add_material_pointer',text="Add Pointer",icon='ADD').library_name = self.library_name

        col = box.column(align=True)
        for pointer in scene_props.material_pointers:
            if pointer.library_name == self.library_name or self.library_name == "":
                row = col.row()
                row.label(text=pointer.name,icon='DOT')
                row.label(text=pointer.category_name,icon='FILEBROWSER')
                row.label(text=pointer.material_name,icon='MATERIAL')
                if pointer.is_custom:
                    row.operator('home_builder.delete_material_pointer',text="",icon='X',emboss=False).material_pointer_name = pointer.name
                else:
                    row.label(text="",icon='BLANK1')            
        

class home_builder_OT_assign_material_to_pointer(bpy.types.Operator):
    bl_idname = "home_builder.assign_material_to_pointer"
    bl_label = "Assign Material to Pointer"
    bl_description = "This assigns a material to the pointer and will update all of the materials in the scene"

    material_name: bpy.props.StringProperty(name="Material Name")
    library_name: bpy.props.StringProperty(name="Library Name")
    pointer_name: bpy.props.StringProperty(name="Pointer Name")

    def execute(self, context):  
        wm_props = context.window_manager.home_builder
        library = wm_props.get_active_library(context)

        scene_props = context.scene.home_builder
        for pointer in scene_props.material_pointers:
            if pointer.name == self.pointer_name:
                pointer.material_name = self.material_name
                pointer.category_name = library.name
                pointer.library_path = os.path.join(library.library_path)
                bpy.ops.home_builder.update_materials_for_pointer(pointer_name=self.pointer_name)                
        return {'FINISHED'}


class home_builder_OT_update_materials_for_pointer(bpy.types.Operator):
    bl_idname = "home_builder.update_materials_for_pointer"
    bl_label = "Update Materials for Pointer"
    bl_description = "This updates all of the materials in the scene from the pointers"

    pointer_name: bpy.props.StringProperty(name="Pointer Name")

    def get_material(self,library_path,material_name):
        if material_name in bpy.data.materials:
            return bpy.data.materials[material_name]

        if os.path.exists(library_path):

            with bpy.data.libraries.load(library_path) as (data_from, data_to):
                for mat in data_from.materials:
                    if mat == material_name:
                        data_to.materials = [mat]
                        break    
            
            for mat in data_to.materials:
                return mat

    def execute(self, context):  
        scene_props = context.scene.home_builder
        selected_pointer = None
        for pointer in scene_props.material_pointers:
            if pointer.name == self.pointer_name:
                selected_pointer = pointer

        for obj in bpy.data.objects:
            scene_props = bpy.context.scene.home_builder  
            for index, p in enumerate(obj.pyclone.pointers):
                if p.pointer_name == self.pointer_name:
                    if index + 1 <= len(obj.material_slots):
                        slot = obj.material_slots[index]
                        slot.material = self.get_material(selected_pointer.library_path,selected_pointer.material_name)    

        return {'FINISHED'}


class home_builder_OT_add_material_pointer(bpy.types.Operator):
    bl_idname = "home_builder.add_material_pointer"
    bl_label = "Add Material Pointer"
    bl_description = "This will add a new material pointer"
    bl_options = {'UNDO'}
    
    #READONLY
    material_pointer_name: bpy.props.StringProperty(name="Material Pointer Name",default="New Pointer")
    library_name: bpy.props.StringProperty(name="Library Name",default="")

    def execute(self,context):
        scene_props = context.scene.home_builder
        material_pointers = scene_props.material_pointers
        pointer = material_pointers.add()
        pointer.name = self.material_pointer_name
        pointer.library_name = self.library_name
        pointer.is_custom = True
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=350)
        
    def draw(self,context):
        layout = self.layout
        row = layout.row()
        row.label(text="Material Pointer Name")
        layout.prop(self,'material_pointer_name',text="")


class home_builder_OT_delete_material_pointer(bpy.types.Operator):
    bl_idname = "home_builder.delete_material_pointer"
    bl_label = "Delete Material Pointer"
    bl_description = "This will add a delete the material pointer"
    bl_options = {'UNDO'}
    
    #READONLY
    material_pointer_name: bpy.props.StringProperty(name="Material Pointer Name",default="New Pointer")

    def execute(self,context):
        scene_props = context.scene.home_builder
        material_pointers = scene_props.material_pointers
        for i, p in enumerate(material_pointers):
            if p.name == self.material_pointer_name:
                material_pointers.remove(i)
                break        
        return {'FINISHED'}


class home_builder_OT_display_hook_modifiers_in_edit_mode(bpy.types.Operator):
    bl_idname = "home_builder.display_hook_modifiers_in_edit_mode"
    bl_label = "Display Hook Modifiers in Edit Mode"
    bl_description = "This turn on the option to display hook modifers in edit mode"
    bl_options = {'UNDO'}
    
    def execute(self,context):
        for obj in bpy.data.objects:
            for mod in obj.modifiers:
                if mod.type == 'HOOK':
                    mod.show_in_editmode = True
                    mod.show_on_cage = True
        return {'FINISHED'}

class home_builder_OT_disconnect_constraint(bpy.types.Operator):
    bl_idname = "home_builder.disconnect_constraint"
    bl_label = "Disconnect Constraint"
    bl_description = "This disconnects the constraint to allow you to move the object"
    
    obj_name: bpy.props.StringProperty(name="Base Point Name")

    def execute(self, context):
        obj = bpy.data.objects[self.obj_name]
        loc = obj.matrix_world.translation
        obj.constraints.clear()
        obj.location = loc
        return {'FINISHED'}


class home_builder_OT_disconnect_cabinet_constraint(bpy.types.Operator):
    bl_idname = "home_builder.disconnect_cabinet_constraint"
    bl_label = "Disconnect Cabinet Constraint"
    bl_description = "This disconnects the cabinet constraint to allow you to move the object"
    
    obj_name: bpy.props.StringProperty(name="Base Point Name")

    def execute(self, context):
        obj = bpy.data.objects[self.obj_name]
        if obj.parent and 'IS_WALL_BP' in obj.parent:
            wall_bp = obj.parent
            loc = obj.matrix_world.translation
            obj.constraints.clear()
            obj.parent = None
            obj.location = loc
            bpy.ops.object.select_all(action='DESELECT')
            wall_bp.hide_viewport = False
            obj.hide_viewport = False
            wall_bp.select_set(True)
            obj.select_set(True)
            context.view_layer.objects.active = wall_bp
            bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
        else:
            loc = obj.matrix_world.translation
            obj.constraints.clear()
            obj.location = loc
        return {'FINISHED'}



class home_builder_OT_disconnect_wall_constraint(bpy.types.Operator):
    bl_idname = "home_builder.disconnect_wall_constraint"
    bl_label = "Disconnect Constraint"
    bl_description = "This disconnects the constraint to allow you to move the object"
    
    obj_name: bpy.props.StringProperty(name="Base Point Name")

    def execute(self, context):
        obj = bpy.data.objects[self.obj_name]
        wall = pc_types.Assembly(obj)
        prev_wall_bp = pc_utils.get_connected_left_wall_bp(wall)
        if prev_wall_bp:
            prev_wall = pc_types.Assembly(prev_wall_bp)
            r_angle = prev_wall.get_prompt("Right Angle")
            r_angle.set_value(0)
            prev_wall.obj_x.home_builder.connected_object = None
        loc = obj.matrix_world.translation
        obj.constraints.clear()
        obj.location = loc
        return {'FINISHED'}
    

class home_builder_OT_add_geo_node_dimension(bpy.types.Operator):
    bl_idname = "home_builder.add_geo_node_dimension"
    bl_label = "Add Geo Node Dimension"

    is_place_first_point = True
    first_point = (0,0,0)
    hit_location = (0,0,0)

    def modal(self, context, event):
        context.area.tag_redraw()

        if self.is_place_first_point:
            self.dim.data.splines[0].bezier_points[0].co = self.hit_location
            self.dim.data.splines[0].bezier_points[1].co = self.hit_location
        else:
            self.dim.data.splines[0].bezier_points[0].co = self.first_point
            self.dim.data.splines[0].bezier_points[1].co = self.hit_location

        if event.type == 'MOUSEMOVE' or event.type in {"LEFT_CTRL", "RIGHT_CTRL"}:
            self.mouse_pos = Vector((event.mouse_region_x, event.mouse_region_y))
            pc_snap.main(self, event.ctrl, context,self.dim)
            
        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if self.is_place_first_point:
                self.is_place_first_point = False
                self.first_point = self.hit_location
            else:
                bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
                return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        if context.area.type == 'VIEW_3D':
            self.mouse_pos = Vector()
            self.hit_object = None
            
            dim = pc_types.GeoNodeDim()
            self.dim = dim.create_dimension()  

            # the arguments we pass the the callback
            args = (self, context)
            # Add the region OpenGL drawing callback
            # draw in view space with 'POST_VIEW' and 'PRE_VIEW'
            self._handle = bpy.types.SpaceView3D.draw_handler_add(pc_snap.draw_callback_px, args, 'WINDOW', 'POST_PIXEL')

            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "View3D not found, cannot run operator")
            return {'CANCELLED'}


class home_builder_OT_unit_settings(bpy.types.Operator):
    bl_idname = "home_builder.unit_settings"
    bl_label = "Change Units"
    bl_description = "This will show the unit settings"
    bl_options = {'UNDO'}
    
    def check(self, context):
        return True

    def invoke(self,context,event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=200)
        
    def draw(self, context):
        layout = self.layout
        unit = context.scene.unit_settings

        layout.use_property_split = True
        layout.use_property_decorate = False

        layout.prop(unit, "system")

        col = layout.column()
        col.prop(unit, "system_rotation", text="Rotation")
        subcol = col.column()
        subcol.enabled = unit.system != 'NONE'
        subcol.prop(unit, "length_unit", text="Length")
        subcol.prop(unit, "temperature_unit", text="Temperature")

    def execute(self, context):
        return {'FINISHED'}


class home_builder_OT_delete_assembly(bpy.types.Operator):
    bl_idname = "home_builder.delete_assembly"
    bl_label = "Delete Assembly"
    bl_description = "This deletes the assembly"
    
    obj_name: bpy.props.StringProperty(name="Object Name")

    def execute(self, context):
        obj_bp = bpy.data.objects[self.obj_name]
        pc_utils.delete_object_and_children(obj_bp)
        return {'FINISHED'}


class home_builder_OT_save_assembly_to_build_library(bpy.types.Operator):
    bl_idname = "home_builder.save_assembly_to_build_library"
    bl_label = "Save Assembly to Build Library"
    bl_description = "This will save the assembly to the build library"
    bl_options = {'UNDO'}

    assembly_bp_name: bpy.props.StringProperty(name="Collection Name")

    assembly = None
    assembly_name = ""

    @classmethod
    def poll(cls, context):
        assembly_bp = pc_utils.get_bp_by_tag(context.object,'IS_ASSEMBLY_BP')
        if assembly_bp:
            return True
        else:
            return False

    def check(self, context):    
        return True

    def invoke(self,context,event):
        assembly_bp = pc_utils.get_bp_by_tag(context.object,'IS_ASSEMBLY_BP')
        self.assembly = pc_types.Assembly(assembly_bp)
        self.assembly_name = self.assembly.obj_bp.name
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Assembly Name: " + self.assembly_name)

        file_exists = False
        directory_to_save_to = self.get_directory_to_save_to(context)
        files = os.listdir(directory_to_save_to) if os.path.exists(directory_to_save_to) else []
        if self.assembly_name + ".blend" in files or self.assembly_name + ".png" in files:
            file_exists = True

        if file_exists:
            layout.label(text="File already exists. Change name before saving.",icon="ERROR")
        if bpy.data.filepath != "" and bpy.data.is_dirty:
            layout.label(text="File is not saved. Save file before saving asset.",icon='ERROR')

    def select_assembly_objects(self,coll):
        for obj in coll.objects:
            obj.select_set(True)
        for child in coll.children:
            self.select_collection_objects(child)

    def create_assembly_thumbnail_script(self,source_dir,source_file,assembly_name,obj_list,view_rotation):
        file = codecs.open(os.path.join(bpy.app.tempdir,"thumb_temp.py"),'w',encoding='utf-8')
        file.write("import bpy\n")
        
        file.write("with bpy.data.libraries.load(r'" + source_file + "') as (data_from, data_to):\n")
        file.write("    data_to.objects = " + str(obj_list) + "\n")    

        file.write("for obj in data_to.objects:\n")
        file.write("    bpy.context.view_layer.active_layer_collection.collection.objects.link(obj)\n")
        file.write("    obj.select_set(True)\n")
        
        file.write("bpy.context.scene.camera.rotation_euler = " + str(view_rotation) + "\n")  
        file.write("bpy.ops.view3d.camera_to_view_selected()\n")

        file.write("render = bpy.context.scene.render\n")
        file.write("render.use_file_extension = True\n")
        file.write("render.filepath = r'" + os.path.join(source_dir,assembly_name) + "'\n")
        file.write("bpy.ops.render.render(write_still=True)\n")
        file.close()

        return os.path.join(bpy.app.tempdir,'thumb_temp.py')
        
    def create_assembly_save_script(self,source_dir,source_file,assembly_name,obj_list):
        file = codecs.open(os.path.join(bpy.app.tempdir,"save_temp.py"),'w',encoding='utf-8')
        file.write("import bpy\n")
        file.write("import os\n")

        file.write("for mat in bpy.data.materials:\n")
        file.write("    bpy.data.materials.remove(mat,do_unlink=True)\n")
        file.write("for obj in bpy.data.objects:\n")
        file.write("    bpy.data.objects.remove(obj,do_unlink=True)\n")               
        file.write("bpy.context.preferences.filepaths.save_version = 0\n")
        
        file.write("with bpy.data.libraries.load(r'" + source_file + "') as (data_from, data_to):\n")
        file.write("    data_to.objects = " + str(obj_list) + "\n")        

        file.write("parent_obj = None\n")
        file.write("for obj in data_to.objects:\n")
        file.write("    bpy.context.view_layer.active_layer_collection.collection.objects.link(obj)\n")
        file.write("    if obj.parent == None:\n")
        file.write("        parent_obj = obj\n")

        file.write("if parent_obj:\n")
        file.write("    parent_obj.location = (0,0,0)\n")
        file.write("    parent_obj.rotation_euler = (0,0,0)\n")

        file.write("for mat in bpy.data.materials:\n")
        file.write("    mat.asset_clear()\n")

        file.write("bpy.ops.wm.save_as_mainfile(filepath=r'" + os.path.join(source_dir,assembly_name) + ".blend')\n")
        file.close()
        return os.path.join(bpy.app.tempdir,'save_temp.py')

    def create_asset_script(self,asset_name,thumbnail_path):
        file = codecs.open(os.path.join(bpy.app.tempdir,"asset_temp.py"),'w',encoding='utf-8')
        file.write("import bpy\n")
        file.write("bpy.context.preferences.filepaths.save_version = 0\n")
        file.write("bpy.ops.mesh.primitive_cube_add()\n")
        file.write("obj = bpy.context.view_layer.objects.active\n")
        file.write("obj.name = '" + asset_name + "'\n")
        file.write("obj.asset_mark()\n")
        file.write("override = bpy.context.copy()\n")
        file.write("override['id'] = obj\n")
        file.write("test_path = r'" + thumbnail_path + "'\n")
        file.write("with bpy.context.temp_override(**override):\n")
        file.write("    bpy.ops.ed.lib_id_load_custom_preview(filepath=test_path)\n")
        file.write("bpy.ops.wm.save_mainfile()\n")
        file.close()
        return os.path.join(bpy.app.tempdir,'asset_temp.py')

    def create_empty_library_script(self,library_path):
        file = codecs.open(os.path.join(bpy.app.tempdir,"save_library_temp.py"),'w',encoding='utf-8')
        file.write("import bpy\n")

        file.write("for mat in bpy.data.materials:\n")
        file.write("    bpy.data.materials.remove(mat,do_unlink=True)\n")
        file.write("for obj in bpy.data.objects:\n")
        file.write("    bpy.data.objects.remove(obj,do_unlink=True)\n")               
        file.write("bpy.context.preferences.filepaths.save_version = 0\n")

        file.write("bpy.ops.wm.save_as_mainfile(filepath=r'" + library_path + "')\n")
        file.close()
        return os.path.join(bpy.app.tempdir,'save_library_temp.py')

    def get_children_list(self,obj_bp,obj_list):
        obj_list.append(obj_bp.name)
        for obj in obj_bp.children:
            self.get_children_list(obj,obj_list)
        return obj_list

    def get_directory_to_save_to(self,context):
        wm_props = context.window_manager.home_builder
        library = wm_props.get_active_library(context)
        custom_library_dir = hb_paths.get_build_library_path()
        return os.path.join(custom_library_dir,library.name,'assets')
        
    def get_thumbnail_path(self):
        return os.path.join(os.path.dirname(__file__),'thumbnail.blend')

    def execute(self, context):
        wm_props = context.window_manager.home_builder

        current_rotation = get_current_view_rotation(context)
        rotation = (current_rotation.to_euler().x,current_rotation.to_euler().y,current_rotation.to_euler().z)

        if bpy.data.filepath == "":
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(bpy.app.tempdir,"temp_blend.blend"))

        library = wm_props.get_active_library(context)

        directory_to_save_to = self.get_directory_to_save_to(context)
        if not os.path.exists(directory_to_save_to):
            os.makedirs(directory_to_save_to)

        obj_list = []
        obj_list = self.get_children_list(self.assembly.obj_bp,obj_list)

        if not os.path.exists(library.library_path):
            library_script_path = self.create_empty_library_script(library.library_path)
            create_library_command = [bpy.app.binary_path,"-b","--python",library_script_path]
            subprocess.call(create_library_command)

        thumbnail_script_path = self.create_assembly_thumbnail_script(directory_to_save_to, bpy.data.filepath, self.assembly_name, obj_list, rotation)
        save_script_path = self.create_assembly_save_script(directory_to_save_to, bpy.data.filepath, self.assembly_name, obj_list)
        asset_script_path = self.create_asset_script(self.assembly_name,os.path.join(directory_to_save_to,self.assembly_name + ".png"))

        tn_command = [bpy.app.binary_path,self.get_thumbnail_path(),"-b","--python",thumbnail_script_path]
        save_command = [bpy.app.binary_path,"-b","--python",save_script_path]
        asset_command = [bpy.app.binary_path,library.library_path,"-b","--python",asset_script_path]

        subprocess.call(tn_command)
        subprocess.call(save_command)
        subprocess.call(asset_command)

        os.remove(thumbnail_script_path)
        os.remove(save_script_path)
        os.remove(asset_script_path)

        bpy.ops.asset.library_refresh()
        return {'FINISHED'}


class home_builder_OT_save_decoration(bpy.types.Operator):
    bl_idname = "home_builder.save_decoration"
    bl_label = "Save Decoration"
    bl_description = "This will save the object to the decoration library"

    bp_name: bpy.props.StringProperty(name="Object Name")
    include_child_objects: bpy.props.BoolProperty(name="Include Child Objects")
    autosave: bpy.props.BoolProperty(name="Autosave",default=True)

    obj = None
    child_objects = []

    @classmethod
    def poll(cls, context):
        if context.object:
            return True
        else:
            return False

    def check(self, context):    
        return True

    def invoke(self,context,event):
        self.obj = context.object
        self.child_objects = []
        for child in self.obj.children_recursive:
            self.child_objects.append(child)
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout

        layout.label(text="Object Name: " + self.obj.name)
        if len(self.child_objects) > 0:
            layout.prop(self,'include_child_objects')
            if self.include_child_objects:
                layout.label(text="Including " + str(len(self.child_objects)) + " Child Objects")

        file_exists = False
        directory_to_save_to = self.get_directory_to_save_to(context)
        files = os.listdir(directory_to_save_to) if os.path.exists(directory_to_save_to) else []
        if self.obj.name + ".blend" in files or self.obj.name + ".png" in files:
            file_exists = True

        if file_exists:
            layout.label(text="File already exists. Change name before saving.",icon="ERROR")
        if bpy.data.filepath != "" and bpy.data.is_dirty:
            layout.label(text="File is not saved. File needs to be saved before saving asset.",icon='ERROR')
            layout.prop(self,'autosave',text="Use Autosave")

    def select_assembly_objects(self,coll):
        for obj in coll.objects:
            obj.select_set(True)
        for child in coll.children:
            self.select_collection_objects(child)

    def create_assembly_thumbnail_script(self,source_dir,source_file,assembly_name,obj_list,view_rotation):
        file = codecs.open(os.path.join(bpy.app.tempdir,"thumb_temp.py"),'w',encoding='utf-8')
        file.write("import bpy\n")
        
        file.write("with bpy.data.libraries.load(r'" + source_file + "') as (data_from, data_to):\n")
        file.write("    data_to.objects = " + str(obj_list) + "\n")    

        file.write("for obj in data_to.objects:\n")
        file.write("    bpy.context.view_layer.active_layer_collection.collection.objects.link(obj)\n")
        file.write("    obj.select_set(True)\n")
        
        file.write("bpy.context.scene.camera.rotation_euler = " + str(view_rotation) + "\n")  
        file.write("bpy.ops.view3d.camera_to_view_selected()\n")

        file.write("render = bpy.context.scene.render\n")
        file.write("render.use_file_extension = True\n")
        file.write("render.filepath = r'" + os.path.join(source_dir,assembly_name) + "'\n")
        file.write("bpy.ops.render.render(write_still=True)\n")
        file.close()

        return os.path.join(bpy.app.tempdir,'thumb_temp.py')
        
    def create_assembly_save_script(self,source_dir,source_file,assembly_name,obj_list):
        file = codecs.open(os.path.join(bpy.app.tempdir,"save_temp.py"),'w',encoding='utf-8')
        file.write("import bpy\n")
        file.write("import os\n")

        file.write("for mat in bpy.data.materials:\n")
        file.write("    bpy.data.materials.remove(mat,do_unlink=True)\n")
        file.write("for obj in bpy.data.objects:\n")
        file.write("    bpy.data.objects.remove(obj,do_unlink=True)\n")               
        file.write("bpy.context.preferences.filepaths.save_version = 0\n")
        
        file.write("with bpy.data.libraries.load(r'" + source_file + "') as (data_from, data_to):\n")
        file.write("    data_to.objects = " + str(obj_list) + "\n")        

        file.write("parent_obj = None\n")
        file.write("for obj in data_to.objects:\n")
        file.write("    if obj.parent == None:\n")
        file.write("        parent_obj = obj\n")
        file.write("    obj.asset_clear()\n")
        file.write("    bpy.context.view_layer.active_layer_collection.collection.objects.link(obj)\n")

        file.write("if parent_obj:\n")
        file.write("    parent_obj.location = (0,0,0)\n")

        file.write("for mat in bpy.data.materials:\n")
        file.write("    mat.asset_clear()\n")

        file.write("bpy.ops.wm.save_as_mainfile(filepath=r'" + os.path.join(source_dir,assembly_name) + ".blend')\n")
        file.close()
        return os.path.join(bpy.app.tempdir,'save_temp.py')

    def create_asset_script(self,asset_name,thumbnail_path):
        file = codecs.open(os.path.join(bpy.app.tempdir,"asset_temp.py"),'w',encoding='utf-8')
        file.write("import bpy\n")
        file.write("bpy.context.preferences.filepaths.save_version = 0\n")
        file.write("bpy.ops.mesh.primitive_cube_add()\n")
        file.write("obj = bpy.context.view_layer.objects.active\n")
        file.write("obj.name = '" + asset_name + "'\n")
        file.write("obj.asset_mark()\n")
        file.write("override = bpy.context.copy()\n")
        file.write("override['id'] = obj\n")
        file.write("test_path = r'" + thumbnail_path + "'\n")
        file.write("with bpy.context.temp_override(**override):\n")
        file.write("    bpy.ops.ed.lib_id_load_custom_preview(filepath=test_path)\n")
        file.write("bpy.ops.wm.save_mainfile()\n")
        file.close()
        return os.path.join(bpy.app.tempdir,'asset_temp.py')

    def create_empty_library_script(self,library_path):
        file = codecs.open(os.path.join(bpy.app.tempdir,"save_library_temp.py"),'w',encoding='utf-8')
        file.write("import bpy\n")

        file.write("for mat in bpy.data.materials:\n")
        file.write("    bpy.data.materials.remove(mat,do_unlink=True)\n")
        file.write("for obj in bpy.data.objects:\n")
        file.write("    bpy.data.objects.remove(obj,do_unlink=True)\n")               
        file.write("bpy.context.preferences.filepaths.save_version = 0\n")

        file.write("bpy.ops.wm.save_as_mainfile(filepath=r'" + library_path + "')\n")
        file.close()
        return os.path.join(bpy.app.tempdir,'save_library_temp.py')

    def get_thumbnail_path(self):
        return os.path.join(os.path.dirname(__file__),'thumbnail.blend')

    def get_directory_to_save_to(self,context):
        wm_props = context.window_manager.home_builder
        library = wm_props.get_active_library(context)
        custom_library_dir = hb_paths.get_decoration_library_path()
        return os.path.join(custom_library_dir,library.name,'assets')

    def execute(self, context):
        wm_props = context.window_manager.home_builder

        current_rotation = get_current_view_rotation(context)
        rotation = (current_rotation.to_euler().x,current_rotation.to_euler().y,current_rotation.to_euler().z)

        if bpy.data.filepath != "" and bpy.data.is_dirty and self.autosave:
            bpy.ops.wm.save_mainfile()

        if bpy.data.filepath == "":
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(bpy.app.tempdir,"temp_blend.blend"))

        library = wm_props.get_active_library(context)

        directory_to_save_to = self.get_directory_to_save_to(context)
        if not os.path.exists(directory_to_save_to):
            os.makedirs(directory_to_save_to)

        obj_list = []
        obj_list.append(self.obj.name)
        if self.include_child_objects:
            for child in self.obj.children_recursive:
                obj_list.append(child.name)

        if not os.path.exists(library.library_path):
            library_script_path = self.create_empty_library_script(library.library_path)
            create_library_command = [bpy.app.binary_path,"-b","--python",library_script_path]
            subprocess.call(create_library_command)

        thumbnail_script_path = self.create_assembly_thumbnail_script(directory_to_save_to, bpy.data.filepath, self.obj.name, obj_list, rotation)
        save_script_path = self.create_assembly_save_script(directory_to_save_to, bpy.data.filepath, self.obj.name, obj_list)
        asset_script_path = self.create_asset_script(self.obj.name,os.path.join(directory_to_save_to,self.obj.name + ".png"))

        tn_command = [bpy.app.binary_path,self.get_thumbnail_path(),"-b","--python",thumbnail_script_path]
        save_command = [bpy.app.binary_path,"-b","--python",save_script_path]
        asset_command = [bpy.app.binary_path,library.library_path,"-b","--python",asset_script_path]

        subprocess.call(tn_command)
        subprocess.call(save_command)
        subprocess.call(asset_command)

        os.remove(thumbnail_script_path)
        os.remove(save_script_path)
        os.remove(asset_script_path)

        bpy.ops.asset.library_refresh()
        return {'FINISHED'}


class home_builder_OT_save_material(bpy.types.Operator):
    bl_idname = "home_builder.save_material"
    bl_label = "Save Material"
    bl_description = "This will save the material to the material library"

    mat_name: bpy.props.StringProperty(name="Object Name")
    autosave: bpy.props.BoolProperty(name="Autosave",default=True)

    mat = None

    @classmethod
    def poll(cls, context):
        if context.object and context.object.active_material:
            return True
        else:
            return False

    def check(self, context):    
        return True

    def invoke(self,context,event):
        self.mat = context.object.active_material
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout

        layout.label(text="Material Name: " + self.mat.name)

        file_exists = False
        directory_to_save_to = self.get_directory_to_save_to(context)
        files = os.listdir(directory_to_save_to) if os.path.exists(directory_to_save_to) else []
        if self.mat.name + ".blend" in files or self.mat.name + ".png" in files:
            file_exists = True

        if file_exists:
            layout.label(text="File already exists. Change name before saving.",icon="ERROR")
        if bpy.data.filepath != "" and bpy.data.is_dirty:
            layout.label(text="File is not saved. File needs to be saved before saving asset.",icon='ERROR')
            layout.prop(self,'autosave',text="Use Autosave")

    def create_asset_script(self,asset_name,source_file,thumbnail_path):
        file = codecs.open(os.path.join(bpy.app.tempdir,"asset_temp.py"),'w',encoding='utf-8')
        file.write("import bpy\n")

        file.write("with bpy.data.libraries.load(r'" + source_file + "') as (data_from, data_to):\n")
        file.write("    for mat in data_from.materials:\n")
        file.write("        if mat == '" + asset_name + "':\n")
        file.write("            data_to.materials = [mat]\n")
        file.write("            break\n")
        file.write("for mat in data_to.materials:\n")
        file.write("    save_mat = mat\n")
        file.write("save_mat.asset_mark()\n")

        file.write("override = bpy.context.copy()\n")
        file.write("override['id'] = save_mat\n")
        file.write("test_path = r'" + thumbnail_path + "'\n")
        file.write("with bpy.context.temp_override(**override):\n")
        file.write("    bpy.ops.ed.lib_id_load_custom_preview(filepath=test_path)\n")    

        file.write("bpy.ops.wm.save_mainfile()\n")
        file.close()
        return os.path.join(bpy.app.tempdir,'asset_temp.py')

    def create_empty_library_script(self,library_path):
        file = codecs.open(os.path.join(bpy.app.tempdir,"save_library_temp.py"),'w',encoding='utf-8')
        file.write("import bpy\n")

        file.write("for mat in bpy.data.materials:\n")
        file.write("    bpy.data.materials.remove(mat,do_unlink=True)\n")
        file.write("for obj in bpy.data.objects:\n")
        file.write("    bpy.data.objects.remove(obj,do_unlink=True)\n")               
        file.write("bpy.context.preferences.filepaths.save_version = 0\n")

        file.write("bpy.ops.wm.save_as_mainfile(filepath=r'" + library_path + "')\n")
        file.close()
        return os.path.join(bpy.app.tempdir,'save_library_temp.py')

    def create_thumbnail_script(self,dir_to_save_to,asset_path,mat_name):
        file = codecs.open(os.path.join(bpy.app.tempdir,"thumb_temp.py"),'w',encoding='utf-8')
        file.write("import bpy\n")
        file.write("import os\n")
        file.write("import sys\n")

        file.write("path = r'" + os.path.join(dir_to_save_to,mat_name)  + "'\n")

        file.write("bpy.ops.object.select_all(action='DESELECT')\n")

        file.write("with bpy.data.libraries.load(r'" + asset_path + "') as (data_from, data_to):\n")
        file.write("    for mat in data_from.materials:\n")
        file.write("        if mat == '" + mat_name + "':\n")
        file.write("            data_to.materials = [mat]\n")
        file.write("            break\n")
        file.write("for mat in data_to.materials:\n")
        file.write("    bpy.ops.mesh.primitive_uv_sphere_add()\n")
        file.write("    obj = bpy.context.view_layer.objects.active\n")
        file.write("    bpy.ops.object.shade_smooth()\n")
        file.write("    obj.dimensions = (2,2,2)\n")
        file.write("    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n")
        # file.write("    mod = obj.modifiers.new('bevel','BEVEL')\n")
        # file.write("    mod.segments = 5\n")
        # file.write("    mod.width = .05\n")
        file.write("    bpy.ops.object.modifier_apply(modifier='bevel')\n")
        file.write("    bpy.ops.object.editmode_toggle()\n")
        file.write("    bpy.ops.mesh.select_all(action='SELECT')\n")
        file.write("    bpy.ops.uv.smart_project(angle_limit=66, island_margin=0)\n")
        file.write("    bpy.ops.object.editmode_toggle()\n")
        file.write("    bpy.ops.object.material_slot_add()\n")
        file.write("    for slot in obj.material_slots:\n")
        file.write("        slot.material = mat\n")

        file.write("bpy.ops.view3d.camera_to_view_selected()\n")

        #RENDER
        file.write("render = bpy.context.scene.render\n")
        file.write("render.use_file_extension = True\n")
        file.write("render.filepath = path\n")
        file.write("bpy.ops.render.render(write_still=True)\n")        
        file.close()
        return os.path.join(bpy.app.tempdir,'thumb_temp.py')    

    def get_thumbnail_path(self):
        return os.path.join(os.path.dirname(__file__),'thumbnail.blend')

    def get_directory_to_save_to(self,context):
        wm_props = context.window_manager.home_builder
        library = wm_props.get_active_library(context)
        custom_library_dir = hb_paths.get_material_library_path()
        return os.path.join(custom_library_dir,library.name,'assets')

    def execute(self, context):
        wm_props = context.window_manager.home_builder

        if bpy.data.filepath != "" and bpy.data.is_dirty and self.autosave:
            bpy.ops.wm.save_mainfile()

        if bpy.data.filepath == "":
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(bpy.app.tempdir,"temp_blend.blend"))

        library = wm_props.get_active_library(context)

        directory_to_save_to = self.get_directory_to_save_to(context)
        if not os.path.exists(directory_to_save_to):
            os.makedirs(directory_to_save_to)

        if not os.path.exists(library.library_path):
            library_script_path = self.create_empty_library_script(library.library_path)
            create_library_command = [bpy.app.binary_path,"-b","--python",library_script_path]
            subprocess.call(create_library_command)

        thumbnail_script_path = self.create_thumbnail_script(directory_to_save_to, bpy.data.filepath, self.mat.name)
        asset_script_path = self.create_asset_script(self.mat.name,bpy.data.filepath,os.path.join(directory_to_save_to,self.mat.name + ".png"))

        tn_command = [bpy.app.binary_path,self.get_thumbnail_path(),"-b","--python",thumbnail_script_path]
        asset_command = [bpy.app.binary_path,library.library_path,"-b","--python",asset_script_path]

        subprocess.call(tn_command)
        subprocess.call(asset_command)

        os.remove(thumbnail_script_path)
        os.remove(asset_script_path)

        bpy.ops.asset.library_refresh()
        return {'FINISHED'}


class home_builder_OT_create_new_library_category(bpy.types.Operator):
    bl_idname = "home_builder.create_new_library_category"
    bl_label = "Create New Library Category"
    bl_description = "This will create a new library category"
    bl_options = {'UNDO'}

    library_type: bpy.props.EnumProperty(name="Main Tabs",
                                         items=[('BUILD_LIBRARY',"Build Library","Build Library"),
                                                ('DECORATIONS',"Decoration","Decoration"),
                                                ('MATERIALS',"Material","Material")],
                                         default='BUILD_LIBRARY')

    category_name: bpy.props.StringProperty(name="Category Name")

    def check(self, context):    
        return True

    def invoke(self,context,event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        layout.prop(self,'category_name')

    def execute(self, context):
        wm_props = context.window_manager.home_builder

        drop_id = ""
        if self.library_type == 'BUILD_LIBRARY':
            library_path = hb_paths.get_build_library_path()
            drop_id = "home_builder.drop_build_library"
        if self.library_type == 'DECORATIONS':
            library_path = hb_paths.get_decoration_library_path()
            drop_id = 'home_builder.drop_decoration'
        if self.library_type == 'MATERIALS':
            library_path = hb_paths.get_material_library_path()
            drop_id = 'home_builder.drop_material'

        new_path = os.path.join(library_path,self.category_name)
        if not os.path.exists(new_path):
            os.makedirs(new_path)

        asset_lib = wm_props.asset_libraries.add()
        asset_lib.name = self.category_name
        asset_lib.library_type = self.library_type
        asset_lib.library_path = os.path.join(new_path,"library.blend")
        asset_lib.drop_id = drop_id

        bpy.ops.home_builder.update_library_path(asset_path=asset_lib.library_path)
        return {'FINISHED'}


class home_builder_OT_assign_material_dialog(bpy.types.Operator):
    bl_idname = "home_builder.assign_material_dialog"
    bl_label = "Assign Material Dialog"
    bl_description = "This is a dialog to assign materials to Home Builder objects"
    bl_options = {'UNDO'}
    
    #READONLY
    material_name: bpy.props.StringProperty(name="Material Name")
    object_name: bpy.props.StringProperty(name="Object Name")
    
    obj = None
    material = None
    
    def check(self, context):
        return True
    
    def invoke(self, context, event):
        self.material = bpy.data.materials[self.material_name]
        self.obj = bpy.data.objects[self.object_name]
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=480)
        
    def draw(self,context):
        scene_props = pc_utils.get_hb_scene_props(context.scene)
        # obj_props = home_builder_utils.get_object_props(self.obj)
        layout = self.layout
        box = layout.box()
        row = box.row()
        row.label(text=self.obj.name,icon='OBJECT_DATA')
        props = row.operator('home_builder.assign_material_to_all_slots',text="Override All",icon='DOWNARROW_HLT')
        props.object_name = self.obj.name
        props.material_name = self.material.name

        pointer_list = []

        # if len(scene_props.material_pointer_groups) - 1 >= obj_props.material_group_index:
        #     mat_group = scene_props.material_pointer_groups[obj_props.material_group_index]
        # else:
        #     mat_group = scene_props.material_pointer_groups[0]

        for index, mat_slot in enumerate(self.obj.material_slots):
            row = box.split(factor=.80)
            pointer = None

            if index + 1 <= len(self.obj.pyclone.pointers):
                pointer = self.obj.pyclone.pointers[index]

            # if mat_slot.name == "":
            #     row.label(text='No Material')
            # else:
            if pointer:
                row.prop(mat_slot,"name",text=pointer.name,icon='MATERIAL')
            else:
                row.prop(mat_slot,"name",text=" ",icon='MATERIAL')

            if pointer and pointer.pointer_name not in pointer_list and pointer.pointer_name != "":
                pointer_list.append(pointer.pointer_name)

            props = row.operator('home_builder.assign_material_to_slot',text="Override",icon='BACK')
            props.object_name = self.obj.name
            props.material_name = self.material.name
            props.index = index

        if len(pointer_list) > 0:
            box = layout.box()
            row = box.row()
            row.label(text="Update Material Pointers",icon='MATERIAL')
            for pointer in pointer_list:
                row = box.split(factor=.80)
                mat_pointer = scene_props.material_pointers[pointer] 
                row.label(text=pointer + ": " + mat_pointer.category_name + "/" + mat_pointer.material_name)    
                props = row.operator('home_builder.assign_material_to_pointer',text="Update All",icon='FILE_REFRESH')
                props.pointer_name = pointer
                props.material_name = self.material_name
        
    def execute(self,context):
        return {'FINISHED'}        


class home_builder_OT_assign_material_to_slot(bpy.types.Operator):
    bl_idname = "home_builder.assign_material_to_slot"
    bl_label = "Assign Material to Slot"
    bl_description = "This will assign a material to a material slot"
    bl_options = {'UNDO'}
    
    #READONLY
    material_name: bpy.props.StringProperty(name="Material Name")
    object_name: bpy.props.StringProperty(name="Object Name")
    
    index: bpy.props.IntProperty(name="Index")
    
    def execute(self,context):
        obj = bpy.data.objects[self.object_name]
        mat = bpy.data.materials[self.material_name]
        obj.material_slots[self.index].material = mat
        return {'FINISHED'}


class home_builder_OT_assign_material_to_all_slots(bpy.types.Operator):
    bl_idname = "home_builder.assign_material_to_all_slots"
    bl_label = "Assign Material to All Slots"
    bl_description = "This will assign a material to all material slots"
    bl_options = {'UNDO'}
    
    #READONLY
    material_name: bpy.props.StringProperty(name="Material Name")
    object_name: bpy.props.StringProperty(name="Object Name")
    
    def execute(self,context):
        obj = bpy.data.objects[self.object_name]
        mat = bpy.data.materials[self.material_name]
        for slot in obj.material_slots:
            slot.material = mat
        return {'FINISHED'}

class home_builder_OT_update_checkbox_prompt_in_scene(bpy.types.Operator):
    bl_idname = "home_builder.update_checkbox_prompt_in_scene"
    bl_label = "Update Checkbox Prompt in Scene"

    prompt_name: bpy.props.StringProperty(name="Prompt Name")
    prompt_value: bpy.props.BoolProperty(name="Prompt Value")

    def execute(self, context):
        for obj in bpy.data.objects:
            if 'IS_ASSEMBLY_BP' in obj:
                assembly = pc_types.Assembly(obj)
                prompt = assembly.get_prompt(self.prompt_name)
                if prompt:
                    prompt.set_value(self.prompt_value)
        return {'FINISHED'}        


class home_builder_OT_update_distance_prompt_in_scene(bpy.types.Operator):
    bl_idname = "home_builder.update_distance_prompt_in_scene"
    bl_label = "Update Distance Prompt in Scene"

    prompt_name: bpy.props.StringProperty(name="Prompt Name")
    prompt_value: bpy.props.FloatProperty(name="Prompt Value",subtype='DISTANCE')

    def execute(self, context):
        for obj in bpy.data.objects:
            if 'IS_ASSEMBLY_BP' in obj:
                assembly = pc_types.Assembly(obj)
                prompt = assembly.get_prompt(self.prompt_name)
                if prompt:
                    prompt.set_value(self.prompt_value)
        return {'FINISHED'}


class home_builder_OT_update_wall_height(bpy.types.Operator):
    bl_idname = "home_builder.update_wall_height"
    bl_label = "Update Wall Height"
    bl_description = "This will update all of the wall heights in the room"

    def execute(self, context):
        props = hb_utils.get_scene_props(context.scene)
        walls = []
        for obj in bpy.data.objects:
            wall_bp = pc_utils.get_bp_by_tag(obj,'IS_WALL_BP')
            if wall_bp and wall_bp not in walls:
                walls.append(wall_bp)

        for wall_bp in walls:
            wall = pc_types.Assembly(wall_bp)
            wall.obj_z.location.z = props.wall_height
        return {'FINISHED'}


class home_builder_OT_add_wall_length_dimension(bpy.types.Operator):
    bl_idname = "home_builder.add_wall_length_dimension"
    bl_label = "Add Wall Length Dimension"
    bl_description = "This will add a length dimension to the selected wall"
    
    wall_bp_name: bpy.props.StringProperty(name="Wall BP Name")

    def execute(self, context):
        wall_bp = pc_utils.get_bp_by_tag(context.object,'IS_WALL_BP')
        wall = pc_types.Assembly(wall_bp)

        dim = pc_types.GeoNodeDimension()
        dim.create()
        dim.set_input("Leader Length",wall.obj_y.location.y + pc_unit.inch(3))
        dim.obj.rotation_euler.x = 0
        dim.obj.select_set(False)
        dim.obj.color = (0,0,0,1)
        dim.obj.show_in_front = True
        dim.obj.parent = wall.obj_bp
        dim.obj.location = (0,0,0)
        dim.obj.location.z += wall.obj_z.location.z
        dim.obj.data.splines[0].bezier_points[0].co = (0,0,0)
        dim.obj.data.splines[0].bezier_points[1].co = (wall.obj_x.location.x,0,0)   
        dim.update()
        return {'FINISHED'}


class home_builder_OT_update_wall_thickness(bpy.types.Operator):
    bl_idname = "home_builder.update_wall_thickness"
    bl_label = "Update Wall Thickness"
    bl_description = "This will update all of the thickness of all of the walls in the room"

    def execute(self, context):
        props = hb_utils.get_scene_props(context.scene)
        walls = []
        for obj in bpy.data.objects:
            wall_bp = pc_utils.get_bp_by_tag(obj,'IS_WALL_BP')
            if wall_bp and wall_bp not in walls:
                walls.append(wall_bp)

        for wall_bp in walls:
            wall = pc_types.Assembly(wall_bp)
            wall.obj_y.location.y = props.wall_thickness
        return {'FINISHED'}


class home_builder_OT_open_browser_window(bpy.types.Operator):
    bl_idname = "home_builder.open_browser_window"
    bl_label = "Open Browser Window"
    bl_description = "This will open a path in your OS file browser"

    path: bpy.props.StringProperty(name="Path",description="Path to Open")

    def execute(self, context):
        import subprocess
        if 'Windows' in str(bpy.app.build_platform):
            subprocess.Popen(r'explorer ' + self.path)
        elif 'Darwin' in str(bpy.app.build_platform):
            subprocess.Popen(['open' , os.path.normpath(self.path)])
        else:
            subprocess.Popen(['xdg-open' , os.path.normpath(self.path)])
        return {'FINISHED'}


class home_builder_OT_edit_part(bpy.types.Operator):
    bl_idname = "home_builder.edit_part"
    bl_label = "Edit Part"

    def execute(self, context):
        obj_bps = []
        for obj in context.selected_objects:
            obj_bp = pc_utils.get_assembly_bp(obj)
            if obj_bp is not None and obj_bp not in obj_bps:
                obj_bps.append(obj_bp)

        for obj_bp in obj_bps:
            for child in obj_bp.children:
                if child.type == 'MESH':
                    pc_utils.apply_hook_modifiers(context,child)

        bpy.ops.object.editmode_toggle()
        return {'FINISHED'}


class home_builder_OT_save_library_settings(bpy.types.Operator):
    bl_idname = "home_builder.save_library_settings"
    bl_label = "Save Library Settings"

    def execute(self, context):
        bpy.ops.home_builder.update_library_xml()
        hb_utils.load_libraries_from_xml(context)
        hb_utils.load_libraries(context)
        return {'FINISHED'}


class home_builder_OT_set_scale_with_two_points(bpy.types.Operator):
    bl_idname = "home_builder.set_scale_with_two_points"
    bl_label = "Set Scale with Two Points"
    bl_options = {'UNDO'}
    
    #READONLY
    drawing_plane = None
    empty_image = None

    first_point = (0,0,0)
    second_point = (0,0,0)
    region = None
    
    header_text = "Select the First Point"

    known_distance: bpy.props.FloatProperty(name="Know Distance",
                                            description="Enter in a known distance on the drawing then select the two points.",
                                            subtype='DISTANCE')
    
    @classmethod
    def poll(cls, context):
        if context.object:
            if context.object.type == 'EMPTY' and context.object.empty_display_type == 'IMAGE':
                return True
            else:
                return False
        else:
            return False
            
    def cancel_drop(self,context,event):
        context.window.cursor_set('DEFAULT')
        pc_utils.delete_obj_list([self.drawing_plane])
        return {'FINISHED'}
        
    def __del__(self):
        if bpy.context.area:
            bpy.context.area.header_text_set()
        
    def invoke(self,context,event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=200)
            
    def draw(self, context):
        layout = self.layout
        layout.prop(self,'known_distance')

    def create_drawing_plane(self,context):
        bpy.ops.mesh.primitive_plane_add()
        plane = context.active_object
        plane.location = (0,0,0)
        self.drawing_plane = context.active_object
        self.drawing_plane.display_type = 'WIRE'
        self.drawing_plane.dimensions = (100,100,1)

    def event_is_cancel(self,event):
        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
            return True
        elif event.type == 'ESC' and event.value == 'PRESS':
            return True
        else:
            return False
            
    def modal(self, context, event):
        context.window.cursor_set('PAINT_BRUSH')
        context.area.tag_redraw()

        selected_point, selected_obj, selected_normal = pc_utils.get_selection_point(context,self.region,event)

        bpy.ops.object.select_all(action='DESELECT')
        if selected_obj:
            if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                if self.first_point != (0,0,0):
                    self.second_point = selected_point
                    
                    distance = pc_utils.calc_distance(self.first_point,self.second_point)
                    diff = self.known_distance / distance

                    self.empty_image.empty_display_size = self.empty_image.empty_display_size*diff

                    return self.cancel_drop(context,event)
                else:
                    self.first_point = selected_point

        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}
            
        if self.event_is_cancel(event):
            return self.cancel_drop(context,event)
            
        return {'RUNNING_MODAL'}
        
    def execute(self,context):
        self.region = pc_utils.get_3d_view_region(context)
        self.first_point = (0,0,0)
        self.second_point = (0,0,0)
        self.empty_image = context.active_object
        self.create_drawing_plane(context)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    

classes = (
    home_builder_OT_about_home_builder,
    home_builder_OT_update_library_xml,
    home_builder_OT_todo,
    home_builder_OT_load_library,
    home_builder_OT_add_external_library,
    home_builder_OT_delete_external_library,
    home_builder_OT_create_new_external_library,
    home_builder_OT_update_library_path,
    home_builder_OT_show_library_material_pointers,
    home_builder_OT_assign_material_to_pointer,
    home_builder_OT_update_materials_for_pointer,
    home_builder_OT_disconnect_constraint,
    home_builder_OT_disconnect_cabinet_constraint,
    home_builder_OT_disconnect_wall_constraint,
    home_builder_OT_unit_settings,
    home_builder_OT_delete_assembly,
    home_builder_OT_save_assembly_to_build_library,
    home_builder_OT_save_decoration,
    home_builder_OT_save_material,
    home_builder_OT_create_new_library_category,
    home_builder_OT_assign_material_dialog,
    home_builder_OT_assign_material_to_slot,
    home_builder_OT_assign_material_to_all_slots,
    home_builder_OT_add_material_pointer,
    home_builder_OT_delete_material_pointer,
    home_builder_OT_display_hook_modifiers_in_edit_mode,
    home_builder_OT_update_checkbox_prompt_in_scene,
    home_builder_OT_update_distance_prompt_in_scene,
    home_builder_OT_update_wall_height,
    home_builder_OT_update_wall_thickness,
    home_builder_OT_add_wall_length_dimension,
    home_builder_OT_open_browser_window,
    home_builder_OT_edit_part,
    home_builder_OT_save_library_settings,
    home_builder_OT_set_scale_with_two_points,
    home_builder_OT_add_geo_node_dimension,
)

register, unregister = bpy.utils.register_classes_factory(classes)        
