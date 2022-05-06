import bpy
import os
import math
from . import library_cabinet
from . import utils_placement
from pc_lib import pc_utils, pc_types, pc_unit
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d
from . import const_cabinets as const

# class hb_sample_cabinets_OT_drop_cabinet_library(bpy.types.Operator):
#     bl_idname = "hb_sample_cabinets.drop_cabinet_library"
#     bl_label = "Drop Cabinet Library"

#     product = None

#     def draw_cabinet(self,context):
#         workspace = context.workspace
#         wm = context.window_manager
#         asset = wm.home_builder.home_builder_library_assets[workspace.home_builder.home_builder_library_index]
#         self.product = eval("library_cabinet." + asset.file_data.name.replace(" ","_") + "()")
#         self.product.draw()

#     def execute(self, context):
#         self.draw_cabinet(context)
#         return {'FINISHED'}

class hb_sample_cabinets_OT_drop_cabinet_library(bpy.types.Operator):
    bl_idname = "hb_sample_cabinets.drop_cabinet_library"
    bl_label = "Place Cabinet"
    bl_options = {'UNDO'}
    
    filepath: bpy.props.StringProperty(name="Filepath",default="Error")

    obj_bp_name: bpy.props.StringProperty(name="Obj Base Point Name")
    snap_cursor_to_cabinet: bpy.props.BoolProperty(name="Snap Cursor to Cabinet",default=False)
    
    region = None

    mouse_x = 0
    mouse_y = 0

    cabinet = None
    selected_cabinet = None
    height_above_floor = 0

    calculators = []

    drawing_plane = None

    next_wall = None
    current_wall = None
    previous_wall = None

    placement = ''
    placement_obj = None

    assembly = None
    obj = None
    exclude_objects = []

    def reset_selection(self):
        self.current_wall = None
        self.selected_cabinet = None    
        self.next_wall = None
        self.previous_wall = None  
        self.placement = ''

    def reset_properties(self):
        self.cabinet = None
        self.selected_cabinet = None
        self.calculators = []
        self.drawing_plane = None
        self.next_wall = None
        self.current_wall = None
        self.previous_wall = None
        self.placement = ''
        self.assembly = None
        self.obj = None
        self.exclude_objects = []

    def execute(self, context):
        self.region = pc_utils.get_3d_view_region(context)
        self.reset_properties()
        self.create_drawing_plane(context)
        self.get_cabinet(context)

        if self.snap_cursor_to_cabinet:
            if self.obj_bp_name != "":
                obj_bp = bpy.data.objects[self.obj_bp_name]
            else:
                obj_bp = self.cabinet.obj_bp            
            region = context.region
            co = location_3d_to_region_2d(region,context.region_data,obj_bp.matrix_world.translation)
            region_offset = Vector((region.x,region.y))
            context.window.cursor_warp(*(co + region_offset))  

        self.placement_obj = utils_placement.create_placement_obj(context)

        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def get_cabinet(self,context):
        workspace = context.workspace
        wm = context.window_manager
        asset = wm.home_builder.home_builder_library_assets[workspace.home_builder.home_builder_library_index]
        self.cabinet = eval("library_cabinet." + asset.file_data.name.replace(" ","_") + "()")
        self.cabinet.draw()
        self.set_child_properties(self.cabinet.obj_bp)

    # def get_cabinet(self,context):
    #     if self.obj_bp_name in bpy.data.objects:
    #         obj_bp = bpy.data.objects[self.obj_bp_name]
    #         self.cabinet = data_cabinets.Cabinet(obj_bp)
    #     else:
    #         directory, file = os.path.split(self.filepath)
    #         filename, ext = os.path.splitext(file)
    #         self.cabinet = eval("cabinet_library." + filename.replace(" ","_") + "()")

    #         if hasattr(self.cabinet,'pre_draw'):
    #             self.cabinet.pre_draw()
    #         else:
    #             self.cabinet.draw()

    #         self.cabinet.set_name(filename)
    #     self.set_child_properties(self.cabinet.obj_bp)

    #     self.height_above_floor = self.cabinet.obj_bp.location.z

    def set_child_properties(self,obj):
        if "IS_DRAWERS_BP" in obj and obj["IS_DRAWERS_BP"]:
            assembly = pc_types.Assembly(obj)
            calculator = assembly.get_calculator('Front Height Calculator')
            if calculator:
                calculator.calculate()
                self.calculators.append(calculator)

        if "IS_VERTICAL_SPLITTER_BP" in obj and obj["IS_VERTICAL_SPLITTER_BP"]:
            assembly = pc_types.Assembly(obj)
            calculator = assembly.get_calculator('Opening Height Calculator')
            if calculator:
                calculator.calculate()
                self.calculators.append(calculator)

        # home_builder_utils.update_id_props(obj,self.cabinet.obj_bp)
        # home_builder_utils.assign_current_material_index(obj)
        if obj.type == 'EMPTY':
            obj.hide_viewport = True    
        if obj.type == 'MESH':
            obj.display_type = 'WIRE'            
        if obj.name != self.drawing_plane.name:
            self.exclude_objects.append(obj)    
        for child in obj.children:
            self.set_child_properties(child)

    def set_placed_properties(self,obj):
        if obj.type == 'MESH':
            obj.display_type = 'TEXTURED'          
        for child in obj.children:
            self.set_placed_properties(child) 

    def create_drawing_plane(self,context):
        bpy.ops.mesh.primitive_plane_add()
        plane = context.active_object
        plane.location = (0,0,0)
        self.drawing_plane = context.active_object
        self.drawing_plane.display_type = 'WIRE'
        self.drawing_plane.dimensions = (100,100,1)

    def confirm_placement(self,context):
        if self.placement == 'LEFT' and self.selected_cabinet:
            self.cabinet.obj_bp.parent = self.selected_cabinet.obj_bp.parent
            constraint_obj = self.cabinet.obj_x
            constraint = self.selected_cabinet.obj_bp.constraints.new('COPY_LOCATION')
            constraint.target = constraint_obj
            constraint.use_x = True
            constraint.use_y = True
            constraint.use_z = False
            for carcass in self.cabinet.carcasses:
                if self.cabinet.obj_z.location.z == self.selected_cabinet.obj_z.location.z:
                    rfe = carcass.get_prompt('Right Finished End')
                    rfe.set_value(False)

            for carcass in self.selected_cabinet.carcasses:
                if self.cabinet.obj_z.location.z == self.selected_cabinet.obj_z.location.z:
                    lfe = carcass.get_prompt('Left Finished End')
                    lfe.set_value(False)                

        if self.placement == 'RIGHT' and self.selected_cabinet:
            self.cabinet.obj_bp.parent = self.selected_cabinet.obj_bp.parent
            constraint_obj = self.selected_cabinet.obj_x
            constraint = self.cabinet.obj_bp.constraints.new('COPY_LOCATION')
            constraint.target = constraint_obj
            constraint.use_x = True
            constraint.use_y = True
            constraint.use_z = False
            for carcass in self.cabinet.carcasses:
                if self.cabinet.obj_z.location.z == self.selected_cabinet.obj_z.location.z:
                    lfe = carcass.get_prompt('Left Finished End')
                    lfe.set_value(False)

            for carcass in self.selected_cabinet.carcasses:
                if self.cabinet.obj_z.location.z == self.selected_cabinet.obj_z.location.z:
                    rfe = carcass.get_prompt('Right Finished End')
                    rfe.set_value(False)               

        if hasattr(self.cabinet,'pre_draw'):
            self.cabinet.draw()
        self.set_child_properties(self.cabinet.obj_bp)
        for cal in self.calculators:
            cal.calculate()

        self.refresh_data(False)

        if self.placement == 'WALL_LEFT':
            if self.cabinet.corner_type == 'Blind':
                blind_panel_location = self.cabinet.carcasses[0].get_prompt("Blind Panel Location")
                blind_panel_location.set_value(0)

        if self.placement == 'WALL_RIGHT':
            if self.cabinet.corner_type == 'Blind':
                blind_panel_location = self.cabinet.carcasses[0].get_prompt("Blind Panel Location")
                blind_panel_location.set_value(1)

        if self.placement == 'BLIND_LEFT':
            right_filler = self.cabinet.get_prompt("Right Adjustment Width")
            right_filler.set_value(pc_unit.inch(2))
            self.cabinet.add_right_filler() 

        if self.placement == 'BLIND_RIGHT':
            left_filler = self.cabinet.get_prompt("Left Adjustment Width")
            left_filler.set_value(pc_unit.inch(2))
            self.cabinet.add_left_filler() 

        # if self.current_wall:
        #     props = home_builder_utils.get_scene_props(context.scene)
        #     cabinet_type = self.cabinet.get_prompt("Cabinet Type")
        #     self.cabinet.obj_bp.location.z = 0
        #     if cabinet_type and cabinet_type.get_value() == 'Upper':
        #         self.cabinet.obj_bp.location.z += props.height_above_floor - self.cabinet.obj_z.location.z

    def modal(self, context, event):
        context.area.tag_redraw()
        bpy.ops.object.select_all(action='DESELECT')

        #EMPTY MUST BE VISIBLE TO CALCULATE CORRECT SIZE FOR HEIGHT COLLISION
        self.cabinet.obj_z.empty_display_size = .001
        self.cabinet.obj_z.hide_viewport = False

        # for calculator in self.calculators:
        #     calculator.calculate()

        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y
        self.reset_selection()

        context.view_layer.update()
        ## selected_normal added in to pass this info on from ray cast to position_cabinet
        # selected_point, selected_obj, selected_normal = pc_utils.get_selection_point(context,event,exclude_objects=self.exclude_objects)
        # selected_point, selected_obj, selected_normal = pc_utils.get_selection_point(context,self.region,event)
        selected_point, selected_obj, selected_normal = pc_utils.get_selection_point(context,self.region,event,exclude_objects=self.exclude_objects)

        ## cursor_z added to allow for multi level placement
        cursor_z = context.scene.cursor.location.z

        self.placement, self.selected_cabinet, self.current_wall = utils_placement.position_cabinet(self.cabinet,
                                                                                                    selected_point,
                                                                                                    selected_obj,
                                                                                                    cursor_z,
                                                                                                    selected_normal,
                                                                                                    self.placement_obj,
                                                                                                    self.height_above_floor)

        if event.type == 'LEFT_ARROW' and event.value == 'PRESS':
            self.cabinet.obj_bp.rotation_euler.z -= math.radians(90)
        if event.type == 'RIGHT_ARROW' and event.value == 'PRESS':
            self.cabinet.obj_bp.rotation_euler.z += math.radians(90)   

        if utils_placement.event_is_place_asset(event):
            self.confirm_placement(context)
            return self.finish(context,event.shift)
            
        if utils_placement.event_is_cancel_command(event):
            return self.cancel_drop(context)

        if utils_placement.event_is_pass_through(event):
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def cancel_drop(self,context):
        pc_utils.delete_object_and_children(self.cabinet.obj_bp)
        pc_utils.delete_object_and_children(self.drawing_plane)
        if self.placement_obj:
            pc_utils.delete_object_and_children(self.placement_obj)           
        return {'CANCELLED'}

    def refresh_data(self,hide=True):
        ''' For some reason matrix world doesn't evaluate correctly
            when placing cabinets next to this if object is hidden
            For now set x, y, z object to not be hidden.
        '''
        self.cabinet.obj_x.hide_viewport = hide
        self.cabinet.obj_y.hide_viewport = hide
        self.cabinet.obj_z.hide_viewport = hide
        self.cabinet.obj_x.empty_display_size = .001
        self.cabinet.obj_y.empty_display_size = .001
        self.cabinet.obj_z.empty_display_size = .001
 
    def finish(self,context,is_recursive=False):
        context.window.cursor_set('DEFAULT')
        if self.drawing_plane:
            pc_utils.delete_obj_list([self.drawing_plane])
        if self.placement_obj:
            pc_utils.delete_object_and_children(self.placement_obj)            
        self.set_placed_properties(self.cabinet.obj_bp) 
        bpy.ops.object.select_all(action='DESELECT')
        context.area.tag_redraw()
        if is_recursive:
            bpy.ops.home_builder.place_cabinet(filepath=self.filepath)
        return {'FINISHED'}        

classes = (
    hb_sample_cabinets_OT_drop_cabinet_library,
)

register, unregister = bpy.utils.register_classes_factory(classes)

if __name__ == "__main__":
    register()                            