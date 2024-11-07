# Renamed from hb_utils.py
import bpy
import os
import xml.etree.ElementTree as ET
from . import pyclone_utils

def get_library_path():
    """Returns the path to the asset library"""
    return os.path.join(os.path.dirname(__file__),'library')

def get_wm_props(window_manager):
    """Returns gallery builder window manager properties"""
    return window_manager.gallery_builder

def get_scene_props(scene):
    """Returns gallery builder scene properties"""
    return scene.gallery_builder

def get_object_props(obj):
    """Returns gallery builder object properties"""
    return obj.gallery_builder

def get_driver_functions():
    """Returns the driver functions used in the addon"""
    return pyclone_utils.get_driver_functions()

def load_custom_driver_functions():
    """Loads custom driver functions"""
    pyclone_utils.register_driver_functions()

def load_libraries(context):
    """Loads all asset libraries"""
    wm_props = get_wm_props(context.window_manager)
    if len(wm_props.asset_libraries) == 0:
        library_path = get_library_path()
        for library in os.listdir(library_path):
            lib = wm_props.asset_libraries.add()
            lib.name = library

def load_libraries_from_xml(context):
    """Loads library data from XML files"""
    wm_props = get_wm_props(context.window_manager)
    library_path = get_library_path()
    for library in os.listdir(library_path):
        if library not in wm_props.asset_libraries:
            lib = wm_props.asset_libraries.add()
            lib.name = library
            
        xml_file = os.path.join(library_path, library, "library.xml")
        if os.path.exists(xml_file):
            tree = ET.parse(xml_file)
            root = tree.getroot()
            for child in root:
                if child.tag == "categories":
                    for category in child:
                        if category.tag == "category":
                            pass  # TODO: Implement category loading

addon_version = (0, 0, 0)