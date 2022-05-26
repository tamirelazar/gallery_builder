import bpy
from . import utils_cabinet

class HOME_BUILDER_MT_cabinet_settings(bpy.types.Menu):
    bl_label = "Cabinet Libraries"

    def draw(self, context):
        layout = self.layout
        layout.popover(panel="HOME_BUILDER_PT_cabinet_sizes",text="Cabinet Sizes",icon='DRIVER_DISTANCE')
        layout.popover(panel="HOME_BUILDER_PT_cabinet_construction",text="Cabinet Construction",icon='MODIFIER_DATA')
        layout.popover(panel="HOME_BUILDER_PT_cabinet_materials",text="Cabinet Materials",icon='MATERIAL_DATA')
        layout.popover(panel="HOME_BUILDER_PT_cabinet_sizes",text="Cabinet Fronts",icon='SNAP_FACE')
        layout.popover(panel="HOME_BUILDER_PT_cabinet_sizes",text="Cabinet Moldings",icon='IPO_CONSTANT')
        layout.separator()
        layout.operator('hb_sample_cabinets.build_library',text="Build Cabinet Library")


class HOME_BUILDER_PT_cabinet_sizes(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_label = "Cabinet Sizes"
    bl_region_type = 'HEADER'
    bl_ui_units_x = 20

    def draw(self, context):
        props = utils_cabinet.get_scene_props(context.scene)

        layout = self.layout

        box = layout.box()
        box.label(text="Standard Cabinet Sizes:")

        row = box.row(align=True)
        row.label(text="Base:")
        row.prop(props,'base_cabinet_height',text="Height")
        row.prop(props,'base_cabinet_depth',text="Depth")

        row = box.row(align=True)
        row.label(text="Tall:")    
        row.prop(props,'tall_cabinet_height',text="Height")    
        row.prop(props,'tall_cabinet_depth',text="Depth")
        
        row = box.row(align=True)
        row.label(text="Upper:")    
        row.prop(props,'upper_cabinet_height',text="Height")        
        row.prop(props,'upper_cabinet_depth',text="Depth")
        
        row = box.row(align=True)
        row.label(text="Sink:")       
        row.prop(props,'sink_cabinet_height',text="Height")     
        row.prop(props,'sink_cabinet_depth',text="Depth")
        
        row = box.row(align=True)
        row.label(text="Suspended:")
        row.prop(props,'suspended_cabinet_height',text="Height")
        row.prop(props,'suspended_cabinet_depth',text="Depth")
        
        row = box.row(align=True)
        row.label(text="Width:")  
        row.prop(props,'width_1_door',text="1 Door")
        row.prop(props,'width_2_door',text="2 Door")
        row.prop(props,'width_drawer',text="Drawer")

        row = box.row(align=True)
        row.label(text="Blind Widths:")  
        row.prop(props,'base_width_blind',text="Base")
        row.prop(props,'tall_width_blind',text="Tall")
        row.prop(props,'upper_width_blind',text="Upper")
        
        row = box.row(align=True)
        row.label(text="Inside Corner Widths:")     
        row.prop(props,'base_inside_corner_size',text="Base")
        row.prop(props,'tall_inside_corner_size',text="Tall")             
        
        row = box.row(align=True)
        row.label(text="Stacked Heights:")     
        row.prop(props,'upper_stacked_cabinet_height',text="Upper")
        row.prop(props,'stacked_top_cabinet_height',text="Top")  

        box = layout.box()
        box.label(text="Upper Cabinet Placement:")
        row = box.row(align=True)
        row.label(text="Height Above Floor:")    
        row.prop(props,'upper_stacked_cabinet_height',text="To Top of Cabinet")         


class HOME_BUILDER_PT_cabinet_construction(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_label = "Cabinet Construction"
    bl_region_type = 'HEADER'
    bl_ui_units_x = 20

    def draw(self, context):
        props = utils_cabinet.get_scene_props(context.scene)

        layout = self.layout

        box = layout.box()
        box.label(text="Cabinet Base Assembly:")
        row = box.row(align=True)
        row.label(text="Base Assembly Size:")       
        row.prop(props,'toe_kick_height',text="Height")       
        row.prop(props,'toe_kick_setback',text="Setback")       

        box = layout.box()
        box.label(text="Cabinet Countertop:")
        row = box.row(align=True)
        row.label(text="Overhang:")       
        row.prop(props,'countertop_front_overhang',text="Front")       
        row.prop(props,'countertop_rear_overhang',text="Rear")      
        row.prop(props,'countertop_front_overhang',text="Side")  

        box = layout.box()
        box.label(text="Cabinet Handles:")
        row = box.row(align=True)
        row.label(text="Center Pulls on Drawers:")        
        row.prop(props,'center_pulls_on_drawer_front',text="")        
        if not props.center_pulls_on_drawer_front:
            row = box.row(align=True)
            row.label(text="Drawer Pull Vertical Location:")        
            row.prop(props,'pull_vertical_location_drawers',text="From Top of Drawer")       

        row = box.row(align=True)
        row.label(text="Horizontal Location:")        
        row.prop(props,'pull_dim_from_edge',text="")       
        row = box.row(align=True)
        row.label(text="Base Vertical Location:")        
        row.prop(props,'pull_vertical_location_base',text="From Top of Door")                   
        row = box.row(align=True)
        row.label(text="Tall Vertical Location:")        
        row.prop(props,'pull_vertical_location_tall',text="From Bottom of Door")   
        row = box.row(align=True)
        row.label(text="Upper Vertical Location:")        
        row.prop(props,'pull_vertical_location_upper',text="From Bottom of Door")           


class HOME_BUILDER_PT_cabinet_materials(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_label = "Cabinet Materials"
    bl_region_type = 'HEADER'
    bl_ui_units_x = 16

    def draw(self, context):
        props = utils_cabinet.get_scene_props(context.scene)

        layout = self.layout
        box = layout.box()

        row = box.row()
        row.label(text="Countertop Thickness")
        row.prop(props,'countertop_thickness',text="")  

        row = box.row()
        row.label(text="Cabinet Carcass Thickness")
        row.prop(props,'cabinet_part_thickness',text="") 

        row = box.row()
        row.label(text="Cabinet Front Thickness")
        row.prop(props,'cabinet_front_thickness',text="") 

        row = box.row()
        row.label(text="Closet Shelf Thickness")
        row.prop(props,'closet_shelf_thickness',text="") 

        row = box.row()
        row.label(text="Closet Panel Thickness")
        row.prop(props,'closet_panel_thickness',text="") 


classes = (
    HOME_BUILDER_MT_cabinet_settings,
    HOME_BUILDER_PT_cabinet_sizes,
    HOME_BUILDER_PT_cabinet_construction,
    HOME_BUILDER_PT_cabinet_materials,
)

register, unregister = bpy.utils.register_classes_factory(classes)          