import bpy
import os
import math
from . import library_cabinet
from . import library_appliance
from . import library_cabinet_starters
from . import library_cabinet_inserts
from . import types_cabinet_inserts
from . import types_cabinet
from . import utils_placement
from . import utils_cabinet
from . import material_pointers_cabinet
from . import paths_cabinet
from pc_lib import pc_utils, pc_types, pc_unit, pc_placement_utils
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d
from . import const_cabinets as const

def add_insert_to_opening(insert,opening):
    insert.obj_bp.parent = opening.obj_bp
    insert.obj_x.location.x = 0
    insert.obj_y.location.y = 0
    insert.obj_z.location.z = 0
    # o_left_depth = opening.get_prompt('Left Depth').get_var('o_left_depth')
    # o_right_depth = opening.get_prompt('Right Depth').get_var('o_right_depth')
    o_back_inset = opening.get_prompt('Back Inset').get_var('o_back_inset')
    i_back_inset = insert.get_prompt('Back Inset')
    i_back_inset.set_formula('o_back_inset',[o_back_inset])
    # i_left_depth = insert.get_prompt('Left Depth')
    # i_right_depth = insert.get_prompt('Right Depth')
    # i_back_inset = insert.get_prompt('Back Inset')
    # i_left_depth.set_formula('o_left_depth',[o_left_depth])
    # i_right_depth.set_formula('o_right_depth',[o_right_depth])
    # i_back_inset.set_formula('o_back_inset',[o_back_inset])
    
    # props = utils_cabinet.get_object_props(insert.obj_bp)
    # props.insert_opening = opening.obj_bp

    opening.obj_bp["IS_FILLED"] = True
    # home_builder_utils.copy_drivers(opening.obj_bp,self.insert.obj_bp)
    pc_utils.copy_drivers(opening.obj_x,insert.obj_x)
    pc_utils.copy_drivers(opening.obj_y,insert.obj_y)
    pc_utils.copy_drivers(opening.obj_z,insert.obj_z)
    pc_utils.copy_drivers(opening.obj_prompts,insert.obj_prompts)
    for child in opening.obj_bp.children:
        child.hide_viewport = True


class Cabinet_Drop(bpy.types.Operator):

    cabinet = None
    drawing_plane = None
    calculators = []
    exclude_objects = []

    def delete_reference_object(self):
        ''' This deletes the cube object that is created for
            reference during the placement operation.
        '''
        for obj in self.cabinet.obj_bp.children:
            if "IS_REFERENCE" in obj:
                pc_utils.delete_object_and_children(obj)

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

    def get_calculators(self,obj):
        for calculator in obj.pyclone.calculators:
            self.calculators.append(calculator)
        for child in obj.children:
            self.get_calculators(child)

    def set_child_properties(self,obj):
        pc_utils.update_id_props(obj,self.cabinet.obj_bp)
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
        if obj.type == 'MESH' and 'IS_OPENING_MESH' not in obj:
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


class hb_sample_cabinets_OT_drop_cabinet(Cabinet_Drop):
    '''
    Drop Operator Requires Class to be Defined in library_cabinet module
    Required Prompts
        Cabinet Type - {'Base','Tall','Upper'} - If Upper Assembly will be placed above floor
        Corner Type - {'','Blind','Inside','Outside'} - Determines how cabinet should be placed on walls
        Left Finished End - Drop Op sets this to True if connected to cabinet
        Right Finished End - Drop Op sets this to True if connected to cabinet
        Left Adjustment Width - Drop Op sets this to 2 inches if placed next to Blind Cabinet
        Right Adjustment Width - Drop Op sets this to 2 inches if placed next to Blind Cabinet
        if Corner Type == 'Blind'
        Blind Panel Location - Drop Op Sets this to 0 if placed in left corner and 1 if placed in right corner
    '''
    bl_idname = "hb_sample_cabinets.drop_cabinet"
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

    # drawing_plane = None

    next_wall = None
    current_wall = None
    previous_wall = None

    placement = ''
    placement_obj = None

    assembly = None
    obj = None
    # exclude_objects = []

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
        scene_props = utils_cabinet.get_scene_props(context.scene)
        asset_file_handle = context.asset_file_handle
        self.cabinet = eval("library_cabinet." + asset_file_handle.name.replace(" ","_") + "()")
        self.cabinet.draw()
        self.cabinet.set_name(asset_file_handle.name.replace(" ","_"))
        self.set_child_properties(self.cabinet.obj_bp)
        self.get_calculators(self.cabinet.obj_bp)

        cabinet_type = self.cabinet.get_prompt("Cabinet Type")
        if cabinet_type.get_value() == 'Upper':
            self.height_above_floor = scene_props.height_above_floor - self.cabinet.obj_z.location.z

        for cal in self.calculators:
            cal.calculate()

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

        if pc_placement_utils.event_is_place_asset(event):
            self.confirm_placement(context)
            return self.finish(context,event.shift)
            
        if pc_placement_utils.event_is_cancel_command(event):
            return self.cancel_drop(context)

        if pc_placement_utils.event_is_pass_through(event):
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def cancel_drop(self,context):
        pc_utils.delete_object_and_children(self.cabinet.obj_bp)
        pc_utils.delete_object_and_children(self.drawing_plane)
        if self.placement_obj:
            pc_utils.delete_object_and_children(self.placement_obj)           
        return {'CANCELLED'}
 
    def finish(self,context,is_recursive=False):
        context.window.cursor_set('DEFAULT')
        if self.drawing_plane:
            pc_utils.delete_obj_list([self.drawing_plane])
        if self.placement_obj:
            pc_utils.delete_object_and_children(self.placement_obj)            
        self.set_placed_properties(self.cabinet.obj_bp) 
        bpy.ops.object.select_all(action='DESELECT')
        context.area.tag_redraw()
        #Reset Object Base Point Name for Duplicate Command
        self.obj_bp_name = ""
        # if is_recursive:
        #     bpy.ops.home_builder.place_cabinet(filepath=self.filepath)
        return {'FINISHED'}        


class hb_sample_cabinets_OT_drop_appliance(bpy.types.Operator):
    bl_idname = "hb_sample_cabinets.drop_appliance"
    bl_label = "Place Appliance"
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

    is_built_in_appliance = False

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
        self.get_appliance(context)

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

    def position_built_in_appliance(self,mouse_location,selected_obj,event,cursor_z,selected_normal):
        opening_bp = pc_utils.get_bp_by_tag(selected_obj,const.OPENING_TAG)
        wall_bp = pc_utils.get_bp_by_tag(selected_obj,const.WALL_TAG)
        if opening_bp:
            if "IS_FILLED" not in opening_bp:
                opening = pc_types.Assembly(opening_bp)
                for child in opening.obj_bp.children:
                    if child.type == 'MESH':
                        child.select_set(True)
                self.cabinet.obj_bp.parent = opening.obj_bp
                self.cabinet.obj_bp.location = (0,0,0)
                self.cabinet.obj_bp.rotation_euler = (0,0,0)
                self.cabinet.obj_x.location.x = opening.obj_x.location.x
                self.cabinet.obj_y.location.y = opening.obj_y.location.y
                self.cabinet.obj_z.location.z = opening.obj_z.location.z
                return opening
        elif wall_bp:
            # self.cabinet.obj_bp.parent = wall_bp
            self.cabinet.obj_bp.matrix_world[0][3] = mouse_location[0]
            self.cabinet.obj_bp.matrix_world[1][3] = mouse_location[1]
            self.cabinet.obj_bp.matrix_world[2][3] = mouse_location[2]
            self.cabinet.obj_bp.rotation_euler.z = wall_bp.rotation_euler.z
            self.cabinet.obj_x.location.x = pc_unit.inch(30)
            self.cabinet.obj_y.location.y = 0
            self.cabinet.obj_z.location.z = pc_unit.inch(35)           
            # placement_obj.parent = wall.obj_bp
            # placement_obj.matrix_world[0][3] = mouse_location[0]
            # placement_obj.matrix_world[1][3] = mouse_location[1] 
            # cabinet.obj_bp.location.y = 0               
            # self.cabinet.obj_bp.parent = wall_bp
            # self.cabinet.obj_bp.location.x
        else:
            self.cabinet.obj_bp.matrix_world[0][3] = mouse_location[0]
            self.cabinet.obj_bp.matrix_world[1][3] = mouse_location[1]
            self.cabinet.obj_bp.matrix_world[2][3] = mouse_location[2]         
            self.cabinet.obj_x.location.x = pc_unit.inch(30)
            self.cabinet.obj_y.location.y = 0
            self.cabinet.obj_z.location.z = pc_unit.inch(35)  
            
    def get_appliance(self,context):
        asset_file_handle = context.asset_file_handle     
        self.cabinet = eval("library_appliance." + asset_file_handle.name.replace(" ","_") + "()")
        self.cabinet.draw()
        self.set_child_properties(self.cabinet.obj_bp)

    def set_child_properties(self,obj):
        pc_utils.update_id_props(obj,self.cabinet.obj_bp)
        # # home_builder_utils.assign_current_material_index(obj)
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

    def confirm_placement(self,context,opening):
        if self.cabinet.is_built_in_appliance:
            if opening:
                opening.obj_bp["IS_FILLED"] = True
                # home_builder_utils.copy_drivers(opening.obj_bp,self.insert.obj_bp)
                pc_utils.copy_drivers(opening.obj_x,self.cabinet.obj_x)
                pc_utils.copy_drivers(opening.obj_y,self.cabinet.obj_y)
                pc_utils.copy_drivers(opening.obj_z,self.cabinet.obj_z)
                pc_utils.copy_drivers(opening.obj_prompts,self.cabinet.obj_prompts)
        else:
            if self.placement == 'LEFT':
                self.cabinet.obj_bp.parent = self.selected_cabinet.obj_bp.parent
                constraint_obj = self.cabinet.obj_x
                constraint = self.selected_cabinet.obj_bp.constraints.new('COPY_LOCATION')
                constraint.target = constraint_obj
                constraint.use_x = True
                constraint.use_y = True
                constraint.use_z = False

            if self.placement == 'RIGHT':
                self.cabinet.obj_bp.parent = self.selected_cabinet.obj_bp.parent
                constraint_obj = self.selected_cabinet.obj_x
                constraint = self.cabinet.obj_bp.constraints.new('COPY_LOCATION')
                constraint.target = constraint_obj
                constraint.use_x = True
                constraint.use_y = True
                constraint.use_z = False

        if hasattr(self.cabinet,'pre_draw'):
            self.cabinet.draw()
        self.set_child_properties(self.cabinet.obj_bp)
        for cal in self.calculators:
            cal.calculate()
        self.refresh_data(False)

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

        selected_point, selected_obj, selected_normal = pc_utils.get_selection_point(context,self.region,event,exclude_objects=self.exclude_objects)

        ## cursor_z added to allow for multi level placement
        cursor_z = context.scene.cursor.location.z
        opening = None
        if self.cabinet.is_built_in_appliance:
            opening = self.position_built_in_appliance(selected_point,selected_obj,event,cursor_z,selected_normal)
        else:
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

        if pc_placement_utils.event_is_place_asset(event):
            self.confirm_placement(context,opening)
            return self.finish(context,event.shift)
            
        if pc_placement_utils.event_is_cancel_command(event):
            return self.cancel_drop(context)

        if pc_placement_utils.event_is_pass_through(event):
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
        #Reset Object Base Point Name for Duplicate Command
        self.obj_bp_name = ""        
        # if is_recursive:
        #     bpy.ops.home_builder.place_cabinet(filepath=self.filepath)
        return {'FINISHED'}        


class hb_sample_cabinets_OT_drop_cabinet_fill_wall(Cabinet_Drop):
    bl_idname = "hb_sample_cabinets.drop_cabinet_fill_wall"
    bl_label = "Drop Cabinet Fill Wall"
    bl_options = {'UNDO'}
    
    filepath: bpy.props.StringProperty(name="Filepath",default="Error")

    obj_bp_name: bpy.props.StringProperty(name="Obj Base Point Name")

    mouse_x = 0
    mouse_y = 0

    selected_cabinet = None

    next_wall = None
    current_wall = None
    previous_wall = None

    starting_point = ()
    placement = ''

    assembly = None
    obj = None

    class_name = ""

    region = None

    def reset_selection(self):
        self.current_wall = None
        self.selected_cabinet = None    
        self.next_wall = None
        self.previous_wall = None  
        self.placement = ''
        # self.placement_obj = None

    def reset_properties(self):
        self.cabinet = None
        self.selected_cabinet = None
        self.calculators = []
        self.drawing_plane = None
        self.next_wall = None
        self.current_wall = None
        self.previous_wall = None
        self.starting_point = ()
        self.placement = ''
        self.assembly = None
        self.obj = None
        self.exclude_objects = []
        self.class_name = ""

    def execute(self, context):
        self.region = pc_utils.get_3d_view_region(context)
        self.reset_properties()
        self.create_drawing_plane(context)
        self.get_cabinet(context)
        self.placement_obj = utils_placement.create_placement_obj(context)
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def get_cabinet(self,context):
        asset_file_handle = context.asset_file_handle

        self.cabinet = eval("library_cabinet_starters." + asset_file_handle.name.replace(" ","_") + "()")

        if hasattr(self.cabinet,'pre_draw'):
            self.cabinet.pre_draw()
        else:
            self.cabinet.draw()

        self.cabinet.set_name(asset_file_handle.name)
        self.set_child_properties(self.cabinet.obj_bp)
        self.get_calculators(self.cabinet.obj_bp)

    def confirm_placement(self,context, override_height):
        if self.current_wall:
            self.cabinet.opening_qty = max(int(math.ceil(self.cabinet.obj_x.location.x / pc_unit.inch(38))),1)

        if self.placement == 'LEFT':
            self.cabinet.obj_bp.parent = self.selected_cabinet.obj_bp.parent
            constraint_obj = self.cabinet.obj_x
            constraint = self.selected_cabinet.obj_bp.constraints.new('COPY_LOCATION')
            constraint.target = constraint_obj
            constraint.use_x = True
            constraint.use_y = True
            constraint.use_z = False

        if self.placement == 'RIGHT':
            self.cabinet.obj_bp.parent = self.selected_cabinet.obj_bp.parent
            constraint_obj = self.selected_cabinet.obj_x
            constraint = self.cabinet.obj_bp.constraints.new('COPY_LOCATION')
            constraint.target = constraint_obj
            constraint.use_x = True
            constraint.use_y = True
            constraint.use_z = False

        if hasattr(self.cabinet,'pre_draw'):
            self.cabinet.draw()

        if override_height != 0:
            for i in range(1,9):
                opening_height_prompt = self.cabinet.get_prompt("Opening " + str(i) + " Height")
                if opening_height_prompt:
                    for index, height in enumerate(const.PANEL_HEIGHTS):
                        if not override_height >= float(height[0])/1000:
                            opening_height_prompt.set_value(float(const.PANEL_HEIGHTS[index - 1][0])/1000)
                            break

        self.set_child_properties(self.cabinet.obj_bp)
        for cal in self.calculators:
            cal.calculate()
        self.refresh_data(False)

    def modal(self, context, event):
        
        bpy.ops.object.select_all(action='DESELECT')

        context.view_layer.update()
        #EMPTY MUST BE VISIBLE TO CALCULATE CORRECT SIZE FOR HEIGHT COLLISION
        self.cabinet.obj_z.empty_display_size = .001
        self.cabinet.obj_z.hide_viewport = False

        for calculator in self.calculators:
            calculator.calculate()

        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y
        self.reset_selection()

        ## selected_normal added in to pass this info on from ray cast to position_cabinet
        selected_point, selected_obj, selected_normal = pc_utils.get_selection_point(context,self.region,event,exclude_objects=self.exclude_objects)

        ## cursor_z added to allow for multi level placement
        cursor_z = context.scene.cursor.location.z

        self.placement, self.selected_cabinet, self.current_wall, override_height = utils_placement.position_closet(self.cabinet,
                                                                                                    selected_point,
                                                                                                    selected_obj,
                                                                                                    cursor_z,
                                                                                                    selected_normal,
                                                                                                    self.placement_obj,
                                                                                                    0)

        if pc_placement_utils.event_is_place_asset(event):
            self.confirm_placement(context,override_height)

            return self.finish(context,event.shift)
            
        if pc_placement_utils.event_is_cancel_command(event):
            return self.cancel_drop(context)

        if pc_placement_utils.event_is_pass_through(event):
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def cancel_drop(self,context):
        pc_utils.delete_object_and_children(self.cabinet.obj_bp)
        pc_utils.delete_object_and_children(self.drawing_plane)
        if self.placement_obj:
            pc_utils.delete_object_and_children(self.placement_obj)        
        return {'CANCELLED'}

    def finish(self,context,is_recursive):
        context.window.cursor_set('DEFAULT')
        if self.drawing_plane:
            pc_utils.delete_obj_list([self.drawing_plane])
        if self.placement_obj:
            pc_utils.delete_obj_list([self.placement_obj])
        self.set_placed_properties(self.cabinet.obj_bp) 
        self.delete_reference_object()
        bpy.ops.object.select_all(action='DESELECT')
        context.area.tag_redraw()
        #Reset Object Base Point Name for Duplicate Command
        self.obj_bp_name = ""        
        ## keep placing until event_is_cancel_command
        # if is_recursive:
        #     bpy.ops.home_builder.place_closet(filepath=self.filepath)
        return {'FINISHED'}


class hb_sample_cabinets_OT_drop_cabinet_corner(Cabinet_Drop):
    bl_idname = "hb_sample_cabinets.drop_cabinet_corner"
    bl_label = "Drop Cabinet Corner"
    bl_options = {'UNDO'}
    
    filepath: bpy.props.StringProperty(name="Filepath",default="Error")

    obj_bp_name: bpy.props.StringProperty(name="Obj Base Point Name")

    mouse_x = 0
    mouse_y = 0

    selected_cabinet = None

    next_wall = None
    current_wall = None
    previous_wall = None

    height_above_floor = 0

    starting_point = ()
    placement = ''

    assembly = None
    obj = None

    class_name = ""

    region = None

    def reset_selection(self):
        self.current_wall = None
        self.selected_cabinet = None    
        self.next_wall = None
        self.previous_wall = None  
        self.placement = ''
        # self.placement_obj = None

    def reset_properties(self):
        self.cabinet = None
        self.selected_cabinet = None
        self.calculators = []
        self.drawing_plane = None
        self.next_wall = None
        self.current_wall = None
        self.previous_wall = None
        self.starting_point = ()
        self.placement = ''
        self.assembly = None
        self.obj = None
        self.exclude_objects = []
        self.class_name = ""

    def execute(self, context):
        self.region = pc_utils.get_3d_view_region(context)
        self.reset_properties()
        self.create_drawing_plane(context)
        self.get_cabinet(context)
        self.placement_obj = utils_placement.create_placement_obj(context)
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def get_cabinet(self,context):
        scene_props = utils_cabinet.get_scene_props(context.scene)

        asset_file_handle = context.asset_file_handle

        self.cabinet = eval("library_cabinet_starters." + asset_file_handle.name.replace(" ","_") + "()")

        if hasattr(self.cabinet,'pre_draw'):
            self.cabinet.pre_draw()
        else:
            self.cabinet.draw()

        if self.cabinet.is_hanging:
            self.height_above_floor = scene_props.height_above_floor - self.cabinet.obj_z.location.z
            print('HAF',self.height_above_floor)

        self.cabinet.set_name(asset_file_handle.name)
        self.set_child_properties(self.cabinet.obj_bp)
        self.get_calculators(self.cabinet.obj_bp)

    def confirm_placement(self,context, override_height):
        if self.placement == 'LEFT':
            self.cabinet.obj_bp.parent = self.selected_cabinet.obj_bp.parent
            constraint_obj = self.cabinet.obj_x
            constraint = self.selected_cabinet.obj_bp.constraints.new('COPY_LOCATION')
            constraint.target = constraint_obj
            constraint.use_x = True
            constraint.use_y = True
            constraint.use_z = False

        if self.placement == 'RIGHT':
            self.cabinet.obj_bp.parent = self.selected_cabinet.obj_bp.parent
            constraint_obj = self.selected_cabinet.obj_x
            constraint = self.cabinet.obj_bp.constraints.new('COPY_LOCATION')
            constraint.target = constraint_obj
            constraint.use_x = True
            constraint.use_y = True
            constraint.use_z = False

        if hasattr(self.cabinet,'pre_draw'):
            self.cabinet.draw()

        if override_height != 0:
            for i in range(1,9):
                opening_height_prompt = self.cabinet.get_prompt("Opening " + str(i) + " Height")
                if opening_height_prompt:
                    for index, height in enumerate(const.PANEL_HEIGHTS):
                        if not override_height >= float(height[0])/1000:
                            opening_height_prompt.set_value(float(const.PANEL_HEIGHTS[index - 1][0])/1000)
                            break

        self.set_child_properties(self.cabinet.obj_bp)
        for cal in self.calculators:
            cal.calculate()
        self.refresh_data(False)

    def modal(self, context, event):
        
        bpy.ops.object.select_all(action='DESELECT')

        context.view_layer.update()
        #EMPTY MUST BE VISIBLE TO CALCULATE CORRECT SIZE FOR HEIGHT COLLISION
        self.cabinet.obj_z.empty_display_size = .001
        self.cabinet.obj_z.hide_viewport = False

        for calculator in self.calculators:
            calculator.calculate()

        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y
        self.reset_selection()

        ## selected_normal added in to pass this info on from ray cast to position_cabinet
        selected_point, selected_obj, selected_normal = pc_utils.get_selection_point(context,self.region,event,exclude_objects=self.exclude_objects)

        ## cursor_z added to allow for multi level placement
        cursor_z = context.scene.cursor.location.z

        self.placement, self.selected_cabinet, self.selected_wall, override_height = utils_placement.position_corner_unit(self.cabinet,
                                                                                                        selected_point,
                                                                                                        selected_obj,
                                                                                                        cursor_z,
                                                                                                        selected_normal,
                                                                                                        self.placement_obj,
                                                                                                        self.height_above_floor)

        if pc_placement_utils.event_is_place_asset(event):
            self.confirm_placement(context,override_height)

            return self.finish(context,event.shift)
            
        if pc_placement_utils.event_is_cancel_command(event):
            return self.cancel_drop(context)

        if pc_placement_utils.event_is_pass_through(event):
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def cancel_drop(self,context):
        pc_utils.delete_object_and_children(self.cabinet.obj_bp)
        pc_utils.delete_object_and_children(self.drawing_plane)
        if self.placement_obj:
            pc_utils.delete_object_and_children(self.placement_obj)        
        return {'CANCELLED'}

    def finish(self,context,is_recursive):
        context.window.cursor_set('DEFAULT')
        if self.drawing_plane:
            pc_utils.delete_obj_list([self.drawing_plane])
        if self.placement_obj:
            pc_utils.delete_obj_list([self.placement_obj])
        self.set_placed_properties(self.cabinet.obj_bp) 
        self.delete_reference_object()
        bpy.ops.object.select_all(action='DESELECT')
        context.area.tag_redraw()
        #Reset Object Base Point Name for Duplicate Command
        self.obj_bp_name = ""        
        ## keep placing until event_is_cancel_command
        # if is_recursive:
        #     bpy.ops.home_builder.place_closet(filepath=self.filepath)
        return {'FINISHED'}


class hb_sample_cabinets_OT_drop_cabinet_insert(bpy.types.Operator):
    bl_idname = "hb_sample_cabinets.drop_cabinet_insert"
    bl_label = "Drop Cabinet Insert"
    bl_options = {'UNDO'}
    
    filepath: bpy.props.StringProperty(name="Filepath",default="Error")

    obj_bp_name: bpy.props.StringProperty(name="Obj Base Point Name",default="")
    snap_cursor_to_cabinet: bpy.props.BoolProperty(name="Snap Cursor to Base Point",default=False)

    insert = None

    calculators = []

    exclude_objects = []

    region = None

    def reset_selection(self):
        pass

    def reset_properties(self):
        self.insert = None
        self.calculators = []
        self.exclude_objects = []

    def execute(self, context):
        self.region = pc_utils.get_3d_view_region(context)
        self.reset_properties()
        custom_drop_id = self.get_insert(context)
        if custom_drop_id:
            eval("bpy.ops." + custom_drop_id + "()")
            return {'FINISHED'}

        if self.snap_cursor_to_cabinet:
            if self.obj_bp_name != "":
                obj_bp = bpy.data.objects[self.obj_bp_name]
            else:
                obj_bp = self.insert.obj_bp            
            region = context.region
            co = location_3d_to_region_2d(region,context.region_data,obj_bp.matrix_world.translation)
            region_offset = Vector((region.x,region.y))
            context.window.cursor_warp(*(co + region_offset))  

        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def position_insert(self,mouse_location,selected_obj,event,cursor_z,selected_normal):
        opening_bp = pc_utils.get_bp_by_tag(selected_obj,const.OPENING_TAG)
        if opening_bp:
            if "IS_FILLED" not in opening_bp:
                opening = pc_types.Assembly(opening_bp)
                for child in opening.obj_bp.children:
                    if child.type == 'MESH':
                        child.select_set(True)
                self.insert.obj_bp.parent = opening.obj_bp
                self.insert.obj_x.location.x = opening.obj_x.location.x
                self.insert.obj_y.location.y = opening.obj_y.location.y
                self.insert.obj_z.location.z = opening.obj_z.location.z
                return opening

    def add_exclude_objects(self,obj):
        self.exclude_objects.append(obj)
        for child in obj.children:
            self.add_exclude_objects(child)

    def get_custom_drop_operator(self,asset_file_handle):
        for tag in asset_file_handle.asset_data.tags:
            if "drop_id:" in tag.name:
                drop_id = tag.name.split(":")[-1]
                return drop_id

    def get_insert(self,context):

        if self.obj_bp_name in bpy.data.objects:
            obj_bp = bpy.data.objects[self.obj_bp_name]
            self.insert = pc_types.Assembly(obj_bp)
        else:        
            asset_file_handle = context.asset_file_handle
            custom_drop_id = self.get_custom_drop_operator(asset_file_handle)
            if custom_drop_id:
                # eval("bpy.ops." + custom_drop_id + "()")
                return custom_drop_id

            self.insert = eval("library_cabinet_inserts." + asset_file_handle.name.replace(" ","_") + "()")

            if hasattr(self.insert,'pre_draw'):
                self.insert.pre_draw()
            else:
                self.insert.draw()

            self.insert.set_name(asset_file_handle.name)
            self.insert.obj_bp[const.INSERT_TAG] = True

        self.add_exclude_objects(self.insert.obj_bp)
        self.set_child_properties(self.insert.obj_bp)
        self.get_calculators(self.insert.obj_bp)

    def get_calculators(self,obj):
        for calculator in obj.pyclone.calculators:
            self.calculators.append(calculator)
        for child in obj.children:
            self.get_calculators(child)

    def set_child_properties(self,obj):
        #Dont Update Id Props when duplicating
        if self.obj_bp_name == "":
            pc_utils.update_id_props(obj,self.insert.obj_bp)
        # home_builder_utils.assign_current_material_index(obj)
        if obj.type == 'EMPTY':
            obj.hide_viewport = True    
        if obj.type == 'MESH':
            obj.display_type = 'WIRE'            
        for child in obj.children:
            self.set_child_properties(child)

    def set_placed_properties(self,obj):
        if obj.type == 'MESH' and 'IS_OPENING_MESH' not in obj:
            obj.display_type = 'TEXTURED'          
        for child in obj.children:
            self.set_placed_properties(child) 

    def confirm_placement(self,context,opening):
        if opening:
            self.insert.obj_bp.parent = opening.obj_bp
            # self.insert.obj_bp.parent = opening.obj_bp.parent
            # self.insert.obj_bp.location = opening.obj_bp.location
            # self.insert.obj_bp.rotation_euler = (0,0,0)
            self.insert.obj_x.location.x = 0
            self.insert.obj_y.location.y = 0
            self.insert.obj_z.location.z = 0
            o_left_depth_prompt = opening.get_prompt('Left Depth')
            o_right_depth_prompt = opening.get_prompt('Right Depth')
            o_back_inset_prompt = opening.get_prompt('Back Inset')
            i_left_depth = self.insert.get_prompt('Left Depth')
            i_right_depth = self.insert.get_prompt('Right Depth')
            i_back_inset = self.insert.get_prompt('Back Inset')
            if o_left_depth_prompt and i_left_depth:
                o_left_depth = o_left_depth_prompt.get_var('o_left_depth')
                i_left_depth.set_formula('o_left_depth',[o_left_depth])
            if o_right_depth_prompt and i_right_depth:
                o_right_depth = o_right_depth_prompt.get_var('o_right_depth')
                i_right_depth.set_formula('o_right_depth',[o_right_depth])
            if o_back_inset_prompt and i_back_inset:
                o_back_inset = o_back_inset_prompt.get_var('o_back_inset')
                i_back_inset.set_formula('o_back_inset',[o_back_inset])                        
       
            # o_left_depth = opening.get_prompt('Left Depth').get_var('o_left_depth')
            # o_right_depth = opening.get_prompt('Right Depth').get_var('o_right_depth')
            # o_back_inset = opening.get_prompt('Back Inset').get_var('o_back_inset')
            # i_left_depth = self.insert.get_prompt('Left Depth')
            # i_right_depth = self.insert.get_prompt('Right Depth')
            # i_back_inset = self.insert.get_prompt('Back Inset')
            # i_left_depth.set_formula('o_left_depth',[o_left_depth])
            # i_right_depth.set_formula('o_right_depth',[o_right_depth])
            # i_back_inset.set_formula('o_back_inset',[o_back_inset])
            
            # props = home_builder_utils.get_object_props(self.insert.obj_bp)
            # props.insert_opening = opening.obj_bp

            opening.obj_bp["IS_FILLED"] = True
            # home_builder_utils.copy_drivers(opening.obj_bp,self.insert.obj_bp)
            pc_utils.copy_drivers(opening.obj_x,self.insert.obj_x)
            pc_utils.copy_drivers(opening.obj_y,self.insert.obj_y)
            pc_utils.copy_drivers(opening.obj_z,self.insert.obj_z)
            pc_utils.copy_drivers(opening.obj_prompts,self.insert.obj_prompts)
            for child in opening.obj_bp.children:
                child.hide_viewport = True

        self.delete_reference_object()

        if hasattr(self.insert,'pre_draw'):
            self.insert.draw()
        self.set_child_properties(self.insert.obj_bp)
        for cal in self.calculators:
            cal.calculate()
        self.refresh_data(False)
        if self.obj_bp_name == "" and hasattr(self.insert,'update_prompts_after_placement'):
            self.insert.update_prompts_after_placement(context)

    def modal(self, context, event):
        
        bpy.ops.object.select_all(action='DESELECT')

        #EMPTY MUST BE VISIBLE TO CALCULATE CORRECT SIZE FOR HEIGHT COLLISION
        self.insert.obj_z.empty_display_size = .001
        self.insert.obj_z.hide_viewport = False

        for calculator in self.calculators:
            calculator.calculate()

        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y
        self.reset_selection()
        context.view_layer.update()

        ## selected_normal added in to pass this info on from ray cast to position_cabinet
        selected_point, selected_obj, selected_normal = pc_utils.get_selection_point(context,self.region,event,exclude_objects=self.exclude_objects)

        ## cursor_z added to allow for multi level placement
        cursor_z = context.scene.cursor.location.z

        opening = self.position_insert(selected_point,selected_obj,event,cursor_z,selected_normal)

        if self.obj_bp_name == "" and hasattr(self.insert,'update_prompts_after_placement'):
            self.insert.update_prompts_after_placement(context)

        if pc_placement_utils.event_is_place_asset(event):
            self.confirm_placement(context,opening)

            return self.finish(context,event.shift)
            
        if pc_placement_utils.event_is_cancel_command(event):
            return self.cancel_drop(context)

        if pc_placement_utils.event_is_pass_through(event):
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def position_object(self,selected_point,selected_obj):
        self.insert.obj_bp.location = selected_point

    def cancel_drop(self,context):
        pc_utils.delete_object_and_children(self.insert.obj_bp)
        return {'CANCELLED'}

    def refresh_data(self,hide=True):
        ''' For some reason matrix world doesn't evaluate correctly
            when placing cabinets next to this if object is hidden
            For now set x, y, z object to not be hidden.
        '''
        self.insert.obj_x.hide_viewport = hide
        self.insert.obj_y.hide_viewport = hide
        self.insert.obj_z.hide_viewport = hide
        self.insert.obj_x.empty_display_size = .001
        self.insert.obj_y.empty_display_size = .001
        self.insert.obj_z.empty_display_size = .001
 
    def delete_reference_object(self):
        for obj in self.insert.obj_bp.children:
            if "IS_REFERENCE" in obj:
                pc_utils.delete_object_and_children(obj)

    def finish(self,context,is_recursive):
        context.window.cursor_set('DEFAULT')
        self.set_placed_properties(self.insert.obj_bp) 
        bpy.ops.object.select_all(action='DESELECT')
        context.area.tag_redraw()
        #Reset Object Base Point Name for Duplicate Command
        self.obj_bp_name = ""
        # if is_recursive and self.obj_bp_name == "":
        #     bpy.ops.home_builder.place_closet_insert(filepath=self.filepath)
        return {'FINISHED'}


class hb_sample_cabinets_OT_drop_adj_shelf(bpy.types.Operator):
    bl_idname = "hb_sample_cabinets.drop_adj_shelf"
    bl_label = "Place Adj Shelf"
    bl_options = {'UNDO'}
    
    filepath: bpy.props.StringProperty(name="Filepath",default="Error")

    part = None

    exclude_objects = []

    region = None

    def reset_properties(self):
        self.part = None
        self.exclude_objects = []

    def execute(self, context):
        self.region = pc_utils.get_3d_view_region(context)
        self.reset_properties()
        self.create_part(context)
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def position_part(self,mouse_location,selected_obj,event,cursor_z,selected_normal):
        if selected_obj is not None:
            self.drop = True
        else:
            self.drop = False

        opening_bp = pc_utils.get_bp_by_tag(selected_obj,const.OPENING_TAG)

        if opening_bp:
            if "IS_FILLED" not in opening_bp:
                opening = pc_types.Assembly(opening_bp)
                for child in opening.obj_bp.children:
                    if child.type == 'MESH':
                        if child not in self.exclude_objects:
                            child.select_set(True)
                z_rot = opening_bp.matrix_world.to_euler()[2]
                self.part.obj_bp.rotation_euler.z = z_rot
                self.part.obj_bp.location.x = opening.obj_bp.matrix_world[0][3]
                self.part.obj_bp.location.y = opening.obj_bp.matrix_world[1][3]
                self.part.obj_bp.location.z = self.get_32mm_position(mouse_location) 
                self.part.obj_x.location.x = opening.obj_x.location.x
                self.part.obj_y.location.y = opening.obj_y.location.y
                return opening

    def create_part(self,context):
        path = os.path.join(paths_cabinet.get_assembly_path(),"Part.blend")
        self.part = pc_types.Assembly(filepath=path)
        self.part.obj_z.location.z = pc_unit.inch(.75)

        self.exclude_objects.append(self.part.obj_bp)
        for obj in self.part.obj_bp.children:
            self.exclude_objects.append(obj)

        self.part.set_name("Single Shelf")
        self.part.obj_bp[const.CLOSET_SINGLE_ADJ_SHELF_TAG] = True
        self.part.obj_bp['PROMPT_ID'] = 'hb_sample_cabinets.single_adj_shelf_prompts'
        self.set_child_properties(self.part.obj_bp)

    def set_child_properties(self,obj):
        pc_utils.update_id_props(obj,self.part.obj_bp)
        # home_builder_utils.assign_current_material_index(obj)
        if obj.type == 'EMPTY':
            obj.hide_viewport = True    
        if obj.type == 'MESH':
            obj.display_type = 'WIRE'            
        for child in obj.children:
            self.set_child_properties(child)

    def set_placed_properties(self,obj):
        if obj.type == 'MESH' and obj.hide_render == False:
            obj.display_type = 'TEXTURED'          
        for child in obj.children:
            self.set_placed_properties(child) 

    def get_32mm_position(self,selected_point):
        number_of_holes =  math.floor((selected_point[2] / pc_unit.millimeter(32)))
        return number_of_holes * pc_unit.millimeter(32)

    def confirm_placement(self,context,opening):
        z_loc = self.part.obj_bp.matrix_world[2][3]
        if opening:
            self.part.obj_bp.parent = opening.obj_bp.parent
            self.part.obj_bp.location.x = opening.obj_bp.location.x
            self.part.obj_bp.location.y = opening.obj_bp.location.y
            self.part.obj_bp.matrix_world[2][3] = z_loc
            self.part.obj_x.location.x = opening.obj_x.location.x
            self.part.obj_y.location.y = opening.obj_y.location.y

            pc_utils.copy_drivers(opening.obj_x,self.part.obj_x)
            pc_utils.copy_drivers(opening.obj_y,self.part.obj_y)
            pc_utils.copy_drivers(opening.obj_prompts,self.part.obj_prompts)
            material_pointers_cabinet.assign_double_sided_pointers(self.part)
            material_pointers_cabinet.assign_materials_to_assembly(self.part)

        self.refresh_data(False)

    def modal(self, context, event):
        
        bpy.ops.object.select_all(action='DESELECT')

        context.view_layer.update()
        #EMPTY MUST BE VISIBLE TO CALCULATE CORRECT SIZE FOR HEIGHT COLLISION
        self.part.obj_z.empty_display_size = .001
        self.part.obj_z.hide_viewport = False

        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y

        ## selected_normal added in to pass this info on from ray cast to position_cabinet
        selected_point, selected_obj, selected_normal = pc_utils.get_selection_point(context,self.region,event,exclude_objects=self.exclude_objects)

        ## cursor_z added to allow for multi level placement
        cursor_z = context.scene.cursor.location.z

        opening = self.position_part(selected_point,selected_obj,event,cursor_z,selected_normal)

        if pc_placement_utils.event_is_place_asset(event):
            self.confirm_placement(context,opening)

            return self.finish(context,event.shift)
            
        if pc_placement_utils.event_is_cancel_command(event):
            return self.cancel_drop(context)

        if pc_placement_utils.event_is_pass_through(event):
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def cancel_drop(self,context):
        pc_utils.delete_object_and_children(self.part.obj_bp)
        return {'CANCELLED'}

    def refresh_data(self,hide=True):
        ''' For some reason matrix world doesn't evaluate correctly
            when placing cabinets next to this if object is hidden
            For now set x, y, z object to not be hidden.
        '''
        self.part.obj_x.hide_viewport = hide
        self.part.obj_y.hide_viewport = hide
        self.part.obj_z.hide_viewport = hide
        self.part.obj_x.empty_display_size = .001
        self.part.obj_y.empty_display_size = .001
        self.part.obj_z.empty_display_size = .001
 
    def delete_reference_object(self):
        for obj in self.part.obj_bp.children:
            if "IS_REFERENCE" in obj:
                pc_utils.delete_object_and_children(obj)

    def finish(self,context,is_recursive):
        context.window.cursor_set('DEFAULT')
        self.set_placed_properties(self.part.obj_bp) 
        bpy.ops.object.select_all(action='DESELECT')
        context.area.tag_redraw()
        # if is_recursive:
        #     bpy.ops.home_builder.place_closet_part(filepath=self.filepath)
        return {'FINISHED'}


class hb_sample_cabinets_OT_drop_cleat(bpy.types.Operator):
    bl_idname = "hb_sample_cabinets.drop_cleat"
    bl_label = "Drop Cleat"
    bl_options = {'UNDO'}
    
    filepath: bpy.props.StringProperty(name="Filepath",default="Error")

    part = None

    exclude_objects = []

    region = None

    def reset_properties(self):
        self.part = None

    def execute(self, context):
        self.region = pc_utils.get_3d_view_region(context)
        self.reset_properties()
        self.create_part(context)
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def position_part(self,mouse_location,selected_obj,event,cursor_z,selected_normal):

        if selected_obj is not None:
            self.drop = True
        else:
            self.drop = False

        opening_bp = pc_utils.get_bp_by_tag(selected_obj,const.OPENING_TAG)

        if opening_bp:
            opening = pc_types.Assembly(opening_bp)
            for child in opening.obj_bp.children:
                if child.type == 'MESH':
                    if child not in self.exclude_objects:
                        child.select_set(True)

            sel_opening_world_loc = (opening.obj_bp.matrix_world[0][3],
                                     opening.obj_bp.matrix_world[1][3],
                                     opening.obj_bp.matrix_world[2][3])
            
            sel_opening_z_world_loc = (opening.obj_z.matrix_world[0][3],
                                       opening.obj_z.matrix_world[1][3],
                                       opening.obj_z.matrix_world[2][3])

            dist_to_bp = pc_utils.calc_distance(mouse_location,sel_opening_world_loc)
            dist_to_z = pc_utils.calc_distance(mouse_location,sel_opening_z_world_loc)

            position = ''
            if dist_to_bp < dist_to_z:
                position = 'BOTTOM'
                self.part.obj_bp.location.z = 0
                self.part.obj_y.location.y = pc_unit.inch(4)
            else:
                position = 'TOP'
                self.part.obj_y.location.y = -pc_unit.inch(4)
                self.part.obj_bp.location.z = opening.obj_z.location.z

            self.part.obj_bp.parent = opening.obj_bp
            self.part.obj_bp.location.x = 0
            self.part.obj_bp.rotation_euler.x = math.radians(90)
            self.part.obj_bp.location.y = opening.obj_y.location.y
            self.part.obj_x.location.x = opening.obj_x.location.x
            return opening, position
        return None, None

    def create_part(self,context):
        path = os.path.join(paths_cabinet.get_assembly_path(),"Part.blend")
        self.part = pc_types.Assembly(filepath=path)
        self.part.obj_z.location.z = pc_unit.inch(.75)
        self.part.add_prompt("Cleat Inset",'DISTANCE',pc_unit.inch(0))

        self.exclude_objects.append(self.part.obj_bp)
        for obj in self.part.obj_bp.children:
            self.exclude_objects.append(obj)

        self.part.set_name("Cleat")
        self.part.obj_bp[const.CLOSET_CLEAT_TAG] = True
        self.part.obj_bp['IS_CUTPART_BP'] = True
        self.part.obj_bp['PROMPT_ID'] = 'hb_sample_cabinets.cleat_prompts'
        self.set_child_properties(self.part.obj_bp)

    def set_child_properties(self,obj):
        pc_utils.update_id_props(obj,self.part.obj_bp)
        # home_builder_utils.assign_current_material_index(obj)
        if obj.type == 'EMPTY':
            obj.hide_viewport = True    
        if obj.type == 'MESH':
            obj.display_type = 'WIRE'            
        for child in obj.children:
            self.set_child_properties(child)

    def set_placed_properties(self,obj):
        if obj.type == 'MESH' and obj.hide_render == False:
            obj.display_type = 'TEXTURED'          
        for child in obj.children:
            self.set_placed_properties(child) 

    def confirm_placement(self,context,opening,placement):
        z_loc = self.part.obj_bp.matrix_world[2][3]
        if opening:
            self.part.obj_bp.location.x = opening.obj_bp.location.x
            self.part.obj_bp.location.y = opening.obj_bp.location.y
            self.part.obj_bp.matrix_world[2][3] = z_loc
            self.part.obj_x.location.x = opening.obj_x.location.x
            cleat_inset = self.part.get_prompt('Cleat Inset').get_var('cleat_inset')

            depth_var = opening.obj_y.pyclone.get_var('location.y','depth_var')
            self.part.loc_y('depth_var-cleat_inset',[depth_var,cleat_inset])    

            if placement == 'TOP':
                z_loc_var = opening.obj_z.pyclone.get_var('location.z','z_loc_var')
                self.part.loc_z('z_loc_var',[z_loc_var])
            
            pc_utils.copy_drivers(opening.obj_x,self.part.obj_x)
            pc_utils.copy_drivers(opening.obj_prompts,self.part.obj_prompts)
            material_pointers_cabinet.assign_double_sided_pointers(self.part)
            material_pointers_cabinet.assign_materials_to_assembly(self.part)

        self.refresh_data(False)

    def modal(self, context, event):
        bpy.ops.object.select_all(action='DESELECT')

        context.view_layer.update()
        #EMPTY MUST BE VISIBLE TO CALCULATE CORRECT SIZE FOR HEIGHT COLLISION
        self.part.obj_z.empty_display_size = .001
        self.part.obj_z.hide_viewport = False

        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y

        ## selected_normal added in to pass this info on from ray cast to position_cabinet
        selected_point, selected_obj, selected_normal = pc_utils.get_selection_point(context,self.region,event,exclude_objects=self.exclude_objects)

        ## cursor_z added to allow for multi level placement
        cursor_z = context.scene.cursor.location.z

        opening, placement = self.position_part(selected_point,selected_obj,event,cursor_z,selected_normal)

        if utils_placement.event_is_place_asset(event):
            self.confirm_placement(context,opening,placement)

            return self.finish(context,event.shift)
            
        if utils_placement.event_is_cancel_command(event):
            return self.cancel_drop(context)

        if utils_placement.event_is_pass_through(event):
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def cancel_drop(self,context):
        pc_utils.delete_object_and_children(self.part.obj_bp)
        return {'CANCELLED'}

    def refresh_data(self,hide=True):
        ''' For some reason matrix world doesn't evaluate correctly
            when placing cabinets next to this if object is hidden
            For now set x, y, z object to not be hidden.
        '''
        self.part.obj_x.hide_viewport = hide
        self.part.obj_y.hide_viewport = hide
        self.part.obj_z.hide_viewport = hide
        self.part.obj_x.empty_display_size = .001
        self.part.obj_y.empty_display_size = .001
        self.part.obj_z.empty_display_size = .001
 
    def delete_reference_object(self):
        for obj in self.part.obj_bp.children:
            if "IS_REFERENCE" in obj:
                pc_utils.delete_object_and_children(obj)

    def finish(self,context,is_recursive):
        context.window.cursor_set('DEFAULT')
        self.set_placed_properties(self.part.obj_bp) 
        bpy.ops.object.select_all(action='DESELECT')
        context.area.tag_redraw()
        if is_recursive:
            bpy.ops.home_builder.place_closet_cleat(filepath=self.filepath)
        return {'FINISHED'}


class hb_sample_cabinets_OT_drop_back(bpy.types.Operator):
    bl_idname = "hb_sample_cabinets.drop_back"
    bl_label = "Drop Back"
    bl_options = {'UNDO'}
    
    filepath: bpy.props.StringProperty(name="Filepath",default="Error")

    part = None

    exclude_objects = []

    region = None

    def reset_properties(self):
        self.part = None

    def execute(self, context):
        self.region = pc_utils.get_3d_view_region(context)
        self.reset_properties()
        self.create_part(context)
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def position_part(self,mouse_location,selected_obj,event,cursor_z,selected_normal):
        if selected_obj is not None:
            self.drop = True
        else:
            self.drop = False

        opening_bp = pc_utils.get_bp_by_tag(selected_obj,const.OPENING_TAG)

        if opening_bp:
            opening = pc_types.Assembly(opening_bp)
            for child in opening.obj_bp.children:
                if child.type == 'MESH':
                    if child not in self.exclude_objects:
                        child.select_set(True)

            self.part.obj_bp.parent = opening.obj_bp
            self.part.obj_bp.location.x = 0
            self.part.obj_bp.location.y = opening.obj_y.location.y
            self.part.obj_bp.location.z = 0
            self.part.obj_bp.rotation_euler.x = math.radians(-90)
            self.part.obj_bp.rotation_euler.y = math.radians(-90)
            self.part.obj_x.location.x = opening.obj_z.location.z
            self.part.obj_y.location.y = opening.obj_x.location.x
            self.part.obj_z.location.z = -pc_unit.inch(.75)
            return opening

        return None

    def create_part(self,context):
        path = os.path.join(paths_cabinet.get_assembly_path(),"Part.blend")
        self.part = pc_types.Assembly(filepath=path)
        self.part.obj_z.location.z = pc_unit.inch(.75)
        self.part.add_prompt('Back Inset','DISTANCE',value=pc_unit.inch(.25))

        self.exclude_objects.append(self.part.obj_bp)
        for obj in self.part.obj_bp.children:
            self.exclude_objects.append(obj)

        self.part.set_name("Back")
        self.part.obj_bp[const.CLOSET_BACK_TAG] = True
        self.part.obj_bp['IS_CUTPART_BP'] = True
        self.part.obj_bp['PROMPT_ID'] = 'hb_sample_cabinets.back_prompts'
        self.set_child_properties(self.part.obj_bp)

    def set_child_properties(self,obj):
        pc_utils.update_id_props(obj,self.part.obj_bp)
        # home_builder_utils.assign_current_material_index(obj)
        if obj.type == 'EMPTY':
            obj.hide_viewport = True    
        if obj.type == 'MESH':
            obj.display_type = 'WIRE'            
        for child in obj.children:
            self.set_child_properties(child)

    def set_placed_properties(self,obj):
        if obj.type == 'MESH' and obj.hide_render == False:
            obj.display_type = 'TEXTURED'          
        for child in obj.children:
            self.set_placed_properties(child) 

    def confirm_placement(self,context,opening):
        if opening:

            height_var = opening.obj_z.pyclone.get_var('location.z','height_var')
            self.part.dim_x('height_var',[height_var])
            
            width_var = opening.obj_x.pyclone.get_var('location.x','width_var')
            self.part.dim_y('width_var',[width_var])            
     
            back_inset = self.part.get_prompt('Back Inset').get_var('back_inset')

            depth_var = opening.obj_y.pyclone.get_var('location.y','depth_var')
            self.part.loc_y('depth_var-back_inset',[depth_var,back_inset])    

            opening_back_inset = opening.get_prompt("Back Inset")
            opening_back_inset.set_value(pc_unit.inch(1))

            pc_utils.copy_drivers(opening.obj_prompts,self.part.obj_prompts)
            material_pointers_cabinet.assign_double_sided_pointers(self.part)
            material_pointers_cabinet.assign_materials_to_assembly(self.part)

        self.refresh_data(False)

    def modal(self, context, event):
        bpy.ops.object.select_all(action='DESELECT')

        context.view_layer.update()
        #EMPTY MUST BE VISIBLE TO CALCULATE CORRECT SIZE FOR HEIGHT COLLISION
        self.part.obj_z.empty_display_size = .001
        self.part.obj_z.hide_viewport = False

        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y

        ## selected_normal added in to pass this info on from ray cast to position_cabinet
        selected_point, selected_obj, selected_normal = pc_utils.get_selection_point(context,self.region,event,exclude_objects=self.exclude_objects)

        ## cursor_z added to allow for multi level placement
        cursor_z = context.scene.cursor.location.z

        opening = self.position_part(selected_point,selected_obj,event,cursor_z,selected_normal)

        if utils_placement.event_is_place_asset(event):
            self.confirm_placement(context,opening)

            return self.finish(context,event.shift)
            
        if utils_placement.event_is_cancel_command(event):
            return self.cancel_drop(context)

        if utils_placement.event_is_pass_through(event):
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def cancel_drop(self,context):
        pc_utils.delete_object_and_children(self.part.obj_bp)
        return {'CANCELLED'}

    def refresh_data(self,hide=True):
        ''' For some reason matrix world doesn't evaluate correctly
            when placing cabinets next to this if object is hidden
            For now set x, y, z object to not be hidden.
        '''
        self.part.obj_x.hide_viewport = hide
        self.part.obj_y.hide_viewport = hide
        self.part.obj_z.hide_viewport = hide
        self.part.obj_x.empty_display_size = .001
        self.part.obj_y.empty_display_size = .001
        self.part.obj_z.empty_display_size = .001
 
    def delete_reference_object(self):
        for obj in self.part.obj_bp.children:
            if "IS_REFERENCE" in obj:
                pc_utils.delete_object_and_children(obj)

    def finish(self,context,is_recursive):
        context.window.cursor_set('DEFAULT')
        self.set_placed_properties(self.part.obj_bp) 
        bpy.ops.object.select_all(action='DESELECT')
        context.area.tag_redraw()
        # if is_recursive:
        #     bpy.ops.home_builder.place_closet_back(filepath=self.filepath)
        return {'FINISHED'}


class hb_sample_cabinets_OT_drop_single_fixed_shelf_part(bpy.types.Operator):
    bl_idname = "hb_sample_cabinets.drop_single_fixed_shelf_part"
    bl_label = "Drop Single Fixed Shelf Part"
    bl_options = {'UNDO'}
    
    filepath: bpy.props.StringProperty(name="Filepath",default="Error")

    part = None
    insert = None

    is_fixed = True

    exclude_objects = []

    region = None

    def reset_properties(self):
        self.part = None
        self.exclude_objects = []

    def execute(self, context):
        self.region = pc_utils.get_3d_view_region(context)
        self.reset_properties()
        self.create_part(context)
        self.create_dimension()
        # path, file_name = os.path.split(self.filepath)
        # if 'Fixed' in file_name:
        #     self.is_fixed = True
        # else:
        #     self.is_fixed = False
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def create_dimension(self):
        self.dim = pc_types.Dimension()
        self.dim.create_dimension()
        self.dim.obj_bp.rotation_euler.y = 0
        self.dim.obj_y.location.y = pc_unit.inch(5)
        self.dim.obj_bp.parent = None
        self.dim.obj_x.location.x = self.part.obj_bp.location.z
        self.dim.obj_bp.rotation_euler.y = math.radians(-90)
        self.dim.obj_bp.rotation_euler.z = math.radians(90)
        self.dim.obj_bp.location.z = 0
        self.dim.obj_bp.hide_viewport = False
        self.dim.obj_x.hide_viewport = False
        self.dim.obj_y.hide_viewport = False
        self.dim.obj_z.hide_viewport = False
        self.dim.get_prompt("Font Size").set_value(.1)
        self.dim.get_prompt("Arrow Height").set_value(pc_unit.inch(3))
        self.dim.get_prompt("Arrow Length").set_value(pc_unit.inch(4))
        self.dim.get_prompt("Line Thickness").set_value(pc_unit.inch(.25))
        for child in self.dim.obj_bp.children:
            child.show_in_front = True
        self.dim.update_dim_text()        

    def position_dimension(self,opening):
        self.dim.obj_bp.parent = opening.obj_bp
        self.dim.obj_bp.location.z = -opening.obj_bp.matrix_world[2][3]
        # self.dim.obj_bp.matrix_world[2][3] = 0
        self.dim.obj_x.location.x = self.part.obj_bp.location.z
        self.dim.update_dim_text()

    def position_part(self,mouse_location,selected_obj,event,cursor_z,selected_normal):
        if selected_obj is not None:
            self.drop = True
        else:
            self.drop = False

        opening_bp = pc_utils.get_bp_by_tag(selected_obj,const.OPENING_TAG)

        if opening_bp:
            if "IS_FILLED" not in opening_bp:
                opening = pc_types.Assembly(opening_bp)
                for child in opening.obj_bp.children:
                    if child.type == 'MESH':
                        if child not in self.exclude_objects:
                            child.select_set(True)
                z_rot = opening_bp.matrix_world.to_euler()[2]
                self.part.obj_bp.rotation_euler.z = z_rot
                self.part.obj_bp.location.x = opening.obj_bp.matrix_world[0][3]
                self.part.obj_bp.location.y = opening.obj_bp.matrix_world[1][3]
                self.part.obj_bp.location.z = self.get_32mm_position(mouse_location) 
                self.part.obj_x.location.x = opening.obj_x.location.x
                self.part.obj_y.location.y = opening.obj_y.location.y
                self.position_dimension(opening)
                return opening

    def create_part(self,context):
        path = os.path.join(paths_cabinet.get_assembly_path(),"Part.blend")
        self.part = pc_types.Assembly(filepath=path)
        self.part.obj_z.location.z = pc_unit.inch(.75)

        self.exclude_objects.append(self.part.obj_bp)
        for obj in self.part.obj_bp.children:
            self.exclude_objects.append(obj)

        self.part.set_name("Single Shelf")
        self.part.obj_bp.hide_viewport = True
        self.part.obj_x.hide_viewport = True
        self.part.obj_y.hide_viewport = True
        self.part.obj_z.hide_viewport = True
        # self.part.obj_bp['PROMPT_ID'] = "hb_closet_parts.single_fixed_shelf_prompts"
        # self.part.obj_bp[const.CLOSET_SINGLE_FIXED_SHELF_TAG] = True

    def set_child_properties(self,obj):
        if self.insert:
            pc_utils.update_id_props(obj,self.insert.obj_bp)
        else:
            pc_utils.update_id_props(obj,self.part.obj_bp)
        # home_builder_utils.assign_current_material_index(obj)
        if obj.type == 'EMPTY':
            obj.hide_viewport = True    
        if obj.type == 'MESH':
            obj.display_type = 'WIRE'            
        for child in obj.children:
            self.set_child_properties(child)

    def set_placed_properties(self,obj):
        if obj.type == 'MESH' and obj.hide_render == False:
            obj.display_type = 'TEXTURED'          
        for child in obj.children:
            self.set_placed_properties(child) 

    def get_32mm_position(self,selected_point):
        number_of_holes =  math.floor((selected_point[2] / pc_unit.millimeter(32)))
        return number_of_holes * pc_unit.millimeter(32)

    def modal(self, context, event):
        bpy.ops.object.select_all(action='DESELECT')

        context.view_layer.update()
        #EMPTY MUST BE VISIBLE TO CALCULATE CORRECT SIZE FOR HEIGHT COLLISION
        self.part.obj_z.empty_display_size = .001
        self.part.obj_z.hide_viewport = False

        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y

        ## selected_normal added in to pass this info on from ray cast to position_cabinet
        selected_point, selected_obj, selected_normal = pc_utils.get_selection_point(context,self.region,event,exclude_objects=self.exclude_objects)

        ## cursor_z added to allow for multi level placement
        cursor_z = context.scene.cursor.location.z

        opening = self.position_part(selected_point,selected_obj,event,cursor_z,selected_normal)

        if utils_placement.event_is_place_asset(event):
            return self.finish(context,opening,event.shift)
            
        if utils_placement.event_is_cancel_command(event):
            return self.cancel_drop(context)

        if utils_placement.event_is_pass_through(event):
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def cancel_drop(self,context):
        pc_utils.delete_object_and_children(self.part.obj_bp)
        pc_utils.delete_object_and_children(self.dim.obj_bp)
        return {'CANCELLED'}

    def refresh_data(self,hide=True):
        ''' For some reason matrix world doesn't evaluate correctly
            when placing cabinets next to this if object is hidden
            For now set x, y, z object to not be hidden.
        '''
        self.part.obj_x.hide_viewport = hide
        self.part.obj_y.hide_viewport = hide
        self.part.obj_z.hide_viewport = hide
        self.part.obj_x.empty_display_size = .001
        self.part.obj_y.empty_display_size = .001
        self.part.obj_z.empty_display_size = .001
 
    def delete_reference_object(self):
        for obj in self.part.obj_bp.children:
            if "IS_REFERENCE" in obj:
                pc_utils.delete_object_and_children(obj)

    def finish(self,context,opening,is_recursive):
        hb_props = utils_cabinet.get_scene_props(context.scene)
        context.window.cursor_set('DEFAULT')
        self.set_placed_properties(self.part.obj_bp) 
        bpy.ops.object.select_all(action='DESELECT')
        context.area.tag_redraw()
        if self.is_fixed:
            world_opening_z = opening.obj_z.matrix_world[2][3]
            sel_loc = self.part.obj_bp.location.z
            top_opening_height = world_opening_z - sel_loc
            self.insert = types_cabinet_inserts.Vertical_Splitter()
            # self.insert.pre_draw()
            self.insert.draw()
            self.insert.obj_bp["PROMPT_ID"] = "hb_closet_parts.single_fixed_shelf_prompts"
            self.insert.set_name("Splitter Shelf")
            add_insert_to_opening(self.insert,opening)
            calculator = self.insert.get_calculator("Opening Calculator")
            opening_1_height = calculator.get_calculator_prompt("Opening 1 Height")
            opening_1_height.equal = False
            value = top_opening_height*1000
            for index, height in enumerate(const.OPENING_HEIGHTS):
                if not value >= float(height[0]):
                    target_height = float(const.OPENING_HEIGHTS[index - 1][0])
                    opening_1_height.set_value(target_height/1000)
                    break
            calculator.calculate()
            self.set_child_properties(self.insert.obj_bp)
            self.set_placed_properties(self.insert.obj_bp)
            pc_utils.delete_object_and_children(self.part.obj_bp)
        else:
            self.part.obj_bp['IS_ADJ_SHELF'] = True
            self.part.obj_bp['IS_CUTPART_BP'] = True
            # props = home_builder_utils.get_object_props(self.part.obj_bp)
            # props.ebl2 = True
            # props.part_name = "Adj Shelf"
            self.part.add_prompt("Is Locked Shelf",'CHECKBOX',False)
            self.part.add_prompt("Adj Shelf Setback",'DISTANCE',hb_props.adj_shelf_setback)
            self.part.add_prompt("Fixed Shelf Setback",'DISTANCE',hb_props.fixed_shelf_setback)
            # l_depth = self.part.add_prompt("Left Depth",'DISTANCE',0)
            # r_depth = self.part.add_prompt("Right Depth",'DISTANCE',0)            
            z_loc = self.part.obj_bp.matrix_world[2][3]
            self.part.obj_bp.parent = opening.obj_bp
            self.part.obj_bp.location.x = opening.obj_bp.location.x
            self.part.obj_bp.location.y = opening.obj_bp.location.y
            self.part.obj_bp.matrix_world[2][3] = z_loc
            self.part.obj_x.location.x = opening.obj_x.location.x
            self.part.obj_y.location.y = opening.obj_y.location.y
            pc_utils.copy_drivers(opening.obj_x,self.part.obj_x)
            pc_utils.copy_drivers(opening.obj_y,self.part.obj_y)
            pc_utils.copy_drivers(opening.obj_prompts,self.part.obj_prompts)
            self.set_child_properties(self.part.obj_bp)
            self.set_placed_properties(self.part.obj_bp)
            material_pointers_cabinet.assign_double_sided_pointers(self.part)
            material_pointers_cabinet.assign_materials_to_assembly(self.part)
        pc_utils.delete_object_and_children(self.dim.obj_bp)
        # if is_recursive:
        #     bpy.ops.home_builder.place_closet_part(filepath=self.filepath)
        return {'FINISHED'}


class hb_sample_cabinets_OT_place_molding(bpy.types.Operator):
    bl_idname = "hb_sample_cabinets.place_molding"
    bl_label = "Place Molding"
    bl_options = {'UNDO'}
    
    filepath: bpy.props.StringProperty(name="Filepath",default="Error")

    curve = None
    profile = None

    exclude_objects = []

    is_base_molding = False

    def reset_properties(self):
        self.curve = None
        self.profile = None
        self.exclude_objects = []

    def execute(self, context):
        self.region = pc_utils.get_3d_view_region(context)
        self.reset_properties()
        self.get_profile(context)
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def get_profile(self,context):
        wm_props = context.window_manager.home_builder
        library = wm_props.get_active_library(context)
        asset_file_handle = context.asset_file_handle
        asset_name = asset_file_handle.name
        if "CR" in asset_name:
            self.is_base_molding = False
        else:
            self.is_base_molding = True
        self.profile = pc_utils.get_object_by_name(os.path.join(library.library_path,"library.blend"),asset_name)

    def create_curve(self):
        bpy.ops.curve.primitive_bezier_curve_add(enter_editmode=False)
        obj_curve = bpy.context.active_object
        obj_curve[const.IS_MOLDING_TAG] = True
        obj_curve.modifiers.new("Edge Split",type='EDGE_SPLIT')     
        obj_curve.data.splines.clear()   
        obj_curve.data.bevel_mode = 'OBJECT'
        obj_curve.location = (0,0,0)
        obj_curve.data.dimensions = '2D'
        obj_curve.data.bevel_object = self.profile
        obj_curve.data.use_fill_caps = True
        return obj_curve

    def position_part(self,mouse_location,selected_obj,event,cursor_z,selected_normal):
        bpy.ops.object.select_all(action='DESELECT')
        wall_bp = pc_utils.get_bp_by_tag(selected_obj,'IS_WALL_BP')
        closet_bp = pc_utils.get_bp_by_tag(selected_obj,const.CLOSET_TAG)
        cabinet_bp = pc_utils.get_bp_by_tag(selected_obj,const.CABINET_TAG)
        if closet_bp:
            for child in closet_bp.children_recursive:
                if child.type == 'MESH':
                    child.select_set(True)
            return closet_bp
        elif cabinet_bp:
            for child in cabinet_bp.children_recursive:
                if child.type == 'MESH':
                    child.select_set(True)
            return cabinet_bp
        elif wall_bp:
            for child in wall_bp.children:
                if child.type == 'MESH':
                    child.select_set(True)
            return wall_bp

    def add_exclude_objects(self,obj):
        self.exclude_objects.append(obj)
        for child in obj.children:
            self.add_exclude_objects(child)

    def create_part(self,context,selected_obj):
        
        if 'IS_WALL_BP' in selected_obj:
            curve_obj = self.create_curve()
            self.assign_curve_to_wall(selected_obj,curve_obj)

        if const.CLOSET_TAG in selected_obj:
            if self.is_base_molding:
                self.assign_base_curve_to_closet(selected_obj)
            else:
                self.assign_crown_curve_to_closet(selected_obj)
    
        if const.CABINET_TAG in selected_obj:
            curve_obj = self.create_curve()
            self.assign_curve_to_cabinet(selected_obj,curve_obj)

    def assign_active_curve_properties(self,obj_curve):
        bpy.ops.object.editmode_toggle()
        bpy.ops.curve.select_all(action='SELECT')
        bpy.ops.curve.handle_type_set(type='VECTOR')
        bpy.ops.object.editmode_toggle()

        bpy.ops.pc_material.add_material_slot(object_name=obj_curve.name)

        for pointer in obj_curve.pyclone.pointers:
            pointer.name == 'Molding'
            pointer.pointer_name = "Molding"       

        material_pointers_cabinet.assign_materials_to_object(obj_curve)

    def assign_curve_to_wall(self,selected_obj,curve_obj):
        wall = pc_types.Assembly(selected_obj)
        curve_obj.parent = selected_obj
        spline = curve_obj.data.splines.new('BEZIER')

        if not self.is_base_molding:
            profile_height = self.profile.dimensions.y
            curve_obj.location.z = wall.obj_z.location.z - profile_height

        spline.bezier_points.add(count=1)   
        spline.bezier_points[0].co = (0,0,0)
        spline.bezier_points[1].co = (wall.obj_x.location.x,0,0)          

        self.assign_active_curve_properties(curve_obj)

    def assign_curve_to_cabinet(self,selected_obj,curve_obj):
        cabinet = types_cabinet.Cabinet(selected_obj)
        curve_obj.parent = selected_obj

        if not self.is_base_molding:
            curve_obj.location.z = cabinet.obj_z.location.z
            for carcass in cabinet.carcasses:
                lfe_p = carcass.get_prompt("Left Finished End")
                rfe_p = carcass.get_prompt("Right Finished End")

            if lfe_p and rfe_p:
                lfe = lfe_p.get_value()
                rfe = rfe_p.get_value()
                width = cabinet.obj_x.location.x
                depth = cabinet.obj_y.location.y
                spline = curve_obj.data.splines.new('BEZIER')       

                if lfe:
                    spline.bezier_points.add(count=2)   
                    spline.bezier_points[0].co = (0,0,0)
                    spline.bezier_points[1].co = (0,depth,0)
                    spline.bezier_points[2].co = (width,depth,0)
                else:
                    spline.bezier_points.add(count=1)   
                    spline.bezier_points[0].co = (0,depth,0)
                    spline.bezier_points[1].co = (width,depth,0)

                if rfe:
                    spline.bezier_points.add(count=1) 
                    if lfe:
                        spline.bezier_points[3].co = (width,0,0)
                    else:
                        spline.bezier_points[2].co = (width,0,0) 

        else:
            lfe_p = None
            rfe_p = None
            for carcass in cabinet.carcasses:
                curve_obj.name = "Base Molding"
                
                c_type = carcass.get_prompt("Cabinet Type")
                cabinet_type = "Base"
                if c_type:
                    cabinet_type = c_type.get_value()
                if cabinet_type not in ("Base","Tall"):
                    continue   
                toe_kick_setback_p = carcass.get_prompt("Toe Kick Setback")
                lfe_p = carcass.get_prompt("Left Finished End")
                rfe_p = carcass.get_prompt("Right Finished End")
                if toe_kick_setback_p and lfe_p and rfe_p:
                    break
 
            if lfe_p and rfe_p and toe_kick_setback_p:
                toe_kick_setback = toe_kick_setback_p.get_value()
                lfe = lfe_p.get_value()
                rfe = rfe_p.get_value()
                width = cabinet.obj_x.location.x
                depth = cabinet.obj_y.location.y
                spline = curve_obj.data.splines.new('BEZIER')

                if lfe:
                    spline.bezier_points.add(count=2)   
                    spline.bezier_points[0].co = (0,0,0)
                    spline.bezier_points[1].co = (0,depth+toe_kick_setback,0)
                    spline.bezier_points[2].co = (width,depth+toe_kick_setback,0)
                else:
                    spline.bezier_points.add(count=1)   
                    spline.bezier_points[0].co = (0,depth+toe_kick_setback,0)
                    spline.bezier_points[1].co = (width,depth+toe_kick_setback,0)

                if rfe:
                    spline.bezier_points.add(count=1) 
                    if lfe:
                        spline.bezier_points[3].co = (width,0,0)
                    else:
                        spline.bezier_points[2].co = (width,0,0)     

        self.assign_active_curve_properties(curve_obj)

    def assign_crown_curve_to_closet(self,selected_obj):
        closet = pc_types.Assembly(selected_obj)
        
        pt = closet.get_prompt("Panel Thickness").get_value()
        start_x = 0
        for i in range(1,10):
            width_p = closet.get_prompt("Opening " + str(i) + " Width")
            if width_p:
                curve_obj = self.create_curve()
                curve_obj.parent = closet.obj_bp
                spline = curve_obj.data.splines.new('BEZIER')

                width = width_p.get_value()
                
                next_width_p = closet.get_prompt("Opening " + str(i + 1) + " Width")
                next_height_p = closet.get_prompt("Opening " + str(i + 1) + " Height")
                next_depth_p = closet.get_prompt("Opening " + str(i + 1) + " Depth")

                prev_depth_p = closet.get_prompt("Opening " + str(i - 1) + " Depth")       
                prev_height_p = closet.get_prompt("Opening " + str(i - 1) + " Height")
                depth = closet.get_prompt("Opening " + str(i) + " Depth").get_value()
                height = closet.get_prompt("Opening " + str(i) + " Height").get_value()

                next_floor = closet.get_prompt("Opening " + str(i + 1) + " Floor Mounted")  
                prev_floor = closet.get_prompt("Opening " + str(i - 1) + " Floor Mounted")                 
                floor = closet.get_prompt("Opening " + str(i) + " Floor Mounted").get_value()

                hanging_height = closet.obj_z.location.z

                if floor:
                    curve_obj.location.z = height
                else:
                    curve_obj.location.z = hanging_height
                current_index = 0

                no_back_left_point = False
                #BACK LEFT
                if prev_depth_p:
                    prev_depth = prev_depth_p.get_value()
                    prev_height = prev_height_p.get_value()
                    if prev_depth >= depth:
                        no_back_left_point = True
                    else:
                        if prev_height < height:
                            spline.bezier_points[current_index].co = (start_x,0,0)  
                        else:
                            spline.bezier_points[current_index].co = (start_x,-prev_depth,0)  
                else:
                    spline.bezier_points[current_index].co = (start_x,0,0)  

                #FRONT LEFT

                move_x = 0
                if not no_back_left_point:
                    spline.bezier_points.add(count=1)
                    current_index += 1              
                else:
                    move_x = pt  

                spline.bezier_points[current_index].co = (start_x+move_x,-depth,0)  

                #FRONT RIGHT
                spline.bezier_points.add(count=1)  
                current_index += 1  
                spline.bezier_points[current_index].co = (start_x+width+(pt*2),-depth,0)  

                #BACK RIGHT
                if next_width_p:
                    next_depth = next_depth_p.get_value()
                    next_height = next_height_p.get_value()
                    if next_depth >= depth:
                        pass
                    else:
                        spline.bezier_points.add(count=1)  
                        current_index += 1 
                        if next_height < height:
                            spline.bezier_points[current_index].co = (start_x+width+(pt*2),0,0)  
                        else:
                            spline.bezier_points[current_index].co = (start_x+width+(pt*2),-next_depth,0) 
                else:
                    #LAST RETURN
                    spline.bezier_points.add(count=1)  
                    current_index += 1
                    spline.bezier_points[current_index].co = (start_x+width+(pt*2),0,0)  

                start_x += width + pt

            self.assign_active_curve_properties(curve_obj)

    def assign_base_curve_to_closet(self,selected_obj):
        closet = pc_types.Assembly(selected_obj)
        
        pt = closet.get_prompt("Panel Thickness").get_value()
        start_x = 0
        for i in range(1,10):
            width_p = closet.get_prompt("Opening " + str(i) + " Width")
            if width_p:
                width = width_p.get_value()
                floor = closet.get_prompt("Opening " + str(i) + " Floor Mounted").get_value()
                if not floor:
                    start_x += width + pt
                    continue #DONT ADD MOLDING TO HANGING UNITS
                
                curve_obj = self.create_curve()
                curve_obj.parent = closet.obj_bp

                spline = curve_obj.data.splines.new('BEZIER')
            
                next_width_p = closet.get_prompt("Opening " + str(i + 1) + " Width")
                next_depth_p = closet.get_prompt("Opening " + str(i + 1) + " Depth")
                next_floor = closet.get_prompt("Opening " + str(i + 1) + " Floor Mounted")  
                prev_floor = closet.get_prompt("Opening " + str(i - 1) + " Floor Mounted") 
                prev_depth_p = closet.get_prompt("Opening " + str(i - 1) + " Depth")       
                depth = closet.get_prompt("Opening " + str(i) + " Depth").get_value()
                
                current_index = 0
                no_back_left_point = False

                #BACK LEFT
                if prev_depth_p:
                    if not prev_floor.get_value():
                        #PREVIOUS OPENING IS FLOOR
                        spline.bezier_points[current_index].co = (start_x,0,0)  
                    else:
                        prev_depth = prev_depth_p.get_value()
                        if prev_depth >= depth:
                            no_back_left_point = True
                        else:
                            spline.bezier_points[current_index].co = (start_x,-prev_depth,0)  
                else:
                    #FIRST POINT
                    spline.bezier_points[current_index].co = (start_x,0,0)  

                #FRONT LEFT
                move_x = 0
                if not no_back_left_point:
                    spline.bezier_points.add(count=1)
                    current_index += 1    
                else:
                    move_x = pt
                
                spline.bezier_points[current_index].co = (start_x+move_x,-depth,0)  

                #FRONT RIGHT
                spline.bezier_points.add(count=1)  
                current_index += 1  
                spline.bezier_points[current_index].co = (start_x+width+(pt*2),-depth,0)  

                #BACK RIGHT
                if next_width_p:
                    next_depth = next_depth_p.get_value()
                    if not next_floor.get_value():
                        spline.bezier_points.add(count=1)  
                        current_index += 1                        
                        spline.bezier_points[current_index].co = (start_x+width+(pt*2),0,0)  
                    else:
                        if next_depth >= depth:
                            pass
                        else:
                            spline.bezier_points.add(count=1)  
                            current_index += 1 
                            spline.bezier_points[current_index].co = (start_x+width+(pt*2),-next_depth,0)  
                else:
                    #LAST RETURN
                    spline.bezier_points.add(count=1)  
                    current_index += 1
                    spline.bezier_points[current_index].co = (start_x+width+(pt*2),0,0)  

                start_x += width + pt

            self.assign_active_curve_properties(curve_obj) 

    def set_child_properties(self,obj):
        pc_utils.update_id_props(obj,self.part.obj_bp)
        if obj.type == 'EMPTY':
            obj.hide_viewport = True    
        if obj.type == 'MESH':
            obj.display_type = 'WIRE'            
        for child in obj.children:
            self.set_child_properties(child)

    def set_placed_properties(self,obj):
        if obj.type == 'MESH' and obj.hide_render == False:
            obj.display_type = 'TEXTURED'          
        for child in obj.children:
            self.set_placed_properties(child) 

    def modal(self, context, event):
        bpy.ops.object.select_all(action='DESELECT')

        context.view_layer.update()

        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y

        ## selected_normal added in to pass this info on from ray cast to position_cabinet
        selected_point, selected_obj, selected_normal = pc_utils.get_selection_point(context,self.region,event,exclude_objects=self.exclude_objects)

        ## cursor_z added to allow for multi level placement
        cursor_z = context.scene.cursor.location.z

        obj = self.position_part(selected_point,selected_obj,event,cursor_z,selected_normal)

        if utils_placement.event_is_place_asset(event):
            return self.finish(context,obj,event.shift)
            
        if utils_placement.event_is_cancel_command(event):
            return self.cancel_drop(context)

        if utils_placement.event_is_pass_through(event):
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def cancel_drop(self,context):
        return {'CANCELLED'}

    def finish(self,context,obj,is_recursive):
        if obj:
            self.create_part(context,obj)
        if is_recursive:
            return {'RUNNING_MODAL'}
        context.window.cursor_set('DEFAULT')
        bpy.ops.object.select_all(action='DESELECT')
        context.area.tag_redraw()
        return {'FINISHED'}

classes = (
    hb_sample_cabinets_OT_drop_cabinet,
    hb_sample_cabinets_OT_drop_appliance,
    hb_sample_cabinets_OT_drop_cabinet_fill_wall,
    hb_sample_cabinets_OT_drop_cabinet_corner,
    hb_sample_cabinets_OT_drop_cabinet_insert,
    hb_sample_cabinets_OT_drop_adj_shelf,
    hb_sample_cabinets_OT_drop_cleat,
    hb_sample_cabinets_OT_drop_back,
    hb_sample_cabinets_OT_drop_single_fixed_shelf_part,
    hb_sample_cabinets_OT_place_molding,
)

register, unregister = bpy.utils.register_classes_factory(classes)

if __name__ == "__main__":
    register()                            