import bpy
from bpy.types import PropertyGroup
from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    FloatProperty,
    EnumProperty,
    PointerProperty,
)

class ArtworkProperties(PropertyGroup):
    name: StringProperty(
        name="Artwork Name",
        description="Name of the artwork",
        default=""
    )
    
    artist: StringProperty(
        name="Artist",
        description="Name of the artist",
        default=""
    )
    
    year: IntProperty(
        name="Year",
        description="Year the artwork was created",
        default=2024,
        min=1,
        max=9999
    )
    
    width: FloatProperty(
        name="Width",
        description="Width of the artwork in meters",
        default=1.0,
        min=0.01,
        unit='LENGTH'
    )
    
    height: FloatProperty(
        name="Height",
        description="Height of the artwork in meters",
        default=1.0,
        min=0.01,
        unit='LENGTH'
    )

class AssetLibrary(PropertyGroup):
    name: StringProperty(name="Library Name")
    enabled: BoolProperty(name="Library Enabled", default=True)
    path: StringProperty(name="Library Path", subtype='DIR_PATH')

class SceneProperties(PropertyGroup):
    library_tabs: EnumProperty(
        name="Library Tabs",
        items=[
            ('ARTWORK', "Artwork", "Place artwork in the gallery"),
            ('WALLS', "Walls", "Place and edit walls"),
            ('LIGHTING', "Lighting", "Adjust gallery lighting"),
        ],
        default='ARTWORK'
    )
    
    active_artwork: PointerProperty(
        name="Active Artwork",
        type=ArtworkProperties
    )
    
    wall_height: FloatProperty(
        name="Wall Height",
        description="Default height for new walls",
        default=3.0,
        min=0.1,
        unit='LENGTH'
    )

class ObjectProperties(PropertyGroup):
    is_artwork: BoolProperty(
        name="Is Artwork",
        description="Identifies if this object is an artwork",
        default=False
    )
    
    artwork_data: PointerProperty(
        type=ArtworkProperties,
        name="Artwork Data"
    )

def register():
    bpy.utils.register_class(ArtworkProperties)
    bpy.utils.register_class(AssetLibrary)
    bpy.utils.register_class(SceneProperties)
    bpy.utils.register_class(ObjectProperties)
    
    bpy.types.WindowManager.gallery_builder = PointerProperty(type=SceneProperties)
    bpy.types.Scene.gallery_builder = PointerProperty(type=SceneProperties)
    bpy.types.Object.gallery_builder = PointerProperty(type=ObjectProperties)

def unregister():
    del bpy.types.WindowManager.gallery_builder
    del bpy.types.Scene.gallery_builder
    del bpy.types.Object.gallery_builder
    
    bpy.utils.unregister_class(ObjectProperties)
    bpy.utils.unregister_class(SceneProperties)
    bpy.utils.unregister_class(AssetLibrary)
    bpy.utils.unregister_class(ArtworkProperties) 