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
    "version": (0, 1, 0),
    "description": "Blender 与视觉引导系统通信的数字孪生插件",
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
    
    # 旋转轴方向属性
    rotation_axis_items = [
        ('X', 'X', '绕X轴旋转'),
        ('Y', 'Y', '绕Y轴旋转'),
        ('Z', 'Z', '绕Z轴旋转'),
    ]
    bpy.types.Scene.rotation_axis = bpy.props.EnumProperty(
        items=rotation_axis_items,
        name="Rotation Axis",
        description="骨骼旋转的坐标轴方向",
        default='Z'
    )

    # 轴值属性
    bpy.types.Scene.axis_values = bpy.props.FloatVectorProperty(
        name="轴值",
        size=6,
        description="6个轴的值",
        default=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        min=-360.0,
        max=360.0,
        subtype='NONE',
        unit='ROTATION'
    )


def register_detection_properties():
    bpy.types.Scene.rt_model_type = bpy.props.EnumProperty(
        name="模型类型",
        description="检测模型类型",
        items=[
            ("yolov8", "YOLOv8", "YOLOv8 通用检测模型"),
            ("simpleSample", "小样本工业零件", "小样本工业零件检测模型"),
        ],
        default="simpleSample",
    )
    bpy.types.Scene.rt_confidence = bpy.props.FloatProperty(
        name="置信度",
        description="检测置信度阈值",
        default=0.5,
        min=0.0,
        max=1.0,
    )
    bpy.types.Scene.rt_iou = bpy.props.FloatProperty(
        name="IOU",
        description="检测 IOU 阈值",
        default=0.45,
        min=0.0,
        max=1.0,
    )
    bpy.types.Scene.rt_class_flags = bpy.props.EnumProperty(
        name="检测类别",
        description="检测类别（多选）；留空表示检测全部类别",
        items=[
            ("bolts", "bolts (ID: 0)", "bolt class", 'NONE', 1 << 0),
            ("cross", "cross (ID: 1)", "cross class", 'NONE', 1 << 1),
            ("gear", "gear (ID: 2)", "gear class", 'NONE', 1 << 2),
            ("nuts", "nuts (ID: 3)", "nuts class", 'NONE', 1 << 3),
            ("pinion", "pinion (ID: 4)", "pinion class", 'NONE', 1 << 4),
        ],
        options={'ENUM_FLAG'},
        default=set(),
    )
    bpy.types.Scene.rt_debug_payload = bpy.props.BoolProperty(
        name="发送前打印 payload",
        description="发送图像前在控制台打印 payload（不含 data）",
        default=False,
    )

def register():
    # Register axis properties
    register_axis_properties()
    register_detection_properties()

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
    # 清理应用资源
    try:
        from .core.app import cleanup_app
        cleanup_app()
    except Exception as e:
        print(f"Error cleaning up app: {e}")
    
    # 清理传输层
    try:
        from .transport.websocket_manager import cleanup_websocket_manager
        cleanup_websocket_manager()
    except Exception as e:
        print(f"Error cleaning up WebSocket: {e}")
    
    # Internationalization
    try:
        bpy.app.translations.unregister(__addon_name__)
    except ValueError:
        pass  # 如果已经取消注册了就忽略错误
    
    # Remove properties
    for prop in [
        "axis_selection",
        "axis_values",
        "rotation_axis",
        "rt_model_type",
        "rt_confidence",
        "rt_iou",
        "rt_class_flags",
        "rt_debug_payload",
    ]:
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)

    # Unregister classes
    auto_load.unregister()
    remove_properties(_addon_properties)
    
    print("{} addon is uninstalled.".format(__addon_name__))
