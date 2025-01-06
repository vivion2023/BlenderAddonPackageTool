import bpy

from .config import __addon_name__
from .i18n.dictionary import dictionary
from ...common.class_loader import auto_load
from ...common.class_loader.auto_load import add_properties, remove_properties
from ...common.i18n.dictionary import common_dictionary
from ...common.i18n.i18n import load_dictionary

# Add-on info
bl_info = {
    "name": "机器人孪生",
    "author": "[yingshuming]",
    "blender": (3, 5, 0),
    "version": (0, 0, 1),
    "description": "This is a template for building addons",
    "warning": "",
    "doc_url": "[documentation url]",
    "tracker_url": "[contact email]",
    "support": "COMMUNITY",
    "category": "3D View"
}

_addon_properties = {}

def register_axis_properties():
    axis_items = [
        ('axis_1', 'Axis 1', 'First axis'),
        ('axis_2', 'Axis 2', 'Second axis'),
        ('axis_3', 'Axis 3', 'Third axis'),
        ('axis_4', 'Axis 4', 'Fourth axis'),
        ('axis_5', 'Axis 5', 'Fifth axis'),
        ('axis_6', 'Axis 6', 'Sixth axis'),
    ]
    bpy.types.Scene.axis_selection = bpy.props.EnumProperty(
        items=axis_items,
        name="Axis Selection",
        default='axis_1'
    )

def register():
    # Register axis properties
    register_axis_properties()

    # Register classes
    auto_load.init()
    auto_load.register()
    add_properties(_addon_properties)

    # Internationalization
    load_dictionary(dictionary)
    try:
        bpy.app.translations.register(__addon_name__, common_dictionary)
    except ValueError:
        # 如果已经注册过，就先取消注册再重新注册
        bpy.app.translations.unregister(__addon_name__)
        bpy.app.translations.register(__addon_name__, common_dictionary)

    print("{} addon is installed.".format(__addon_name__))

def unregister():
    # Internationalization
    try:
        bpy.app.translations.unregister(__addon_name__)
    except ValueError:
        pass  # 如果已经取消注册了就忽略错误
    
    # Remove axis properties
    if hasattr(bpy.types.Scene, "axis_selection"):
        del bpy.types.Scene.axis_selection

    # Unregister classes
    auto_load.unregister()
    remove_properties(_addon_properties)
    
    print("{} addon is uninstalled.".format(__addon_name__))
