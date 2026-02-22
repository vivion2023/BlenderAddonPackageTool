# 主面板
import bpy
import math

from ..core.app import get_app
from ....common.types.framework import reg_order


class BasePanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RoboticTwin"


CLASS_LABELS = {
    "bolts": "bolts (ID: 0)",
    "cross": "cross (ID: 1)",
    "gear": "gear (ID: 2)",
    "nuts": "nuts (ID: 3)",
    "pinion": "pinion (ID: 4)",
}


@reg_order(0)
class RT_MT_ClassSelectMenu(bpy.types.Menu):
    bl_idname = "RT_MT_class_select_menu"
    bl_label = "检测类别"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        for class_key in CLASS_LABELS.keys():
            layout.prop_enum(scene, "rt_class_flags", class_key)
        layout.separator()
        layout.operator("robotic_twin.classes_select_all", text="全选", icon='CHECKMARK')
        layout.operator("robotic_twin.classes_clear", text="清空", icon='X')


@reg_order(0)
class RT_PT_ConnectionPanel(BasePanel, bpy.types.Panel):
    """连接面板"""
    bl_idname = "RT_PT_connection"
    bl_label = "连接管理"
    
    def draw(self, context):
        layout = self.layout
        app = get_app()
        
        row = layout.row()
        if app.is_connected():
            row.alert = False
            row.label(text="已连接" if not app.is_registered() else "已注册", icon='CHECKMARK')
        else:
            row.alert = True
            row.label(text="未连接", icon='UNLINKED')
        
        if app.is_connected():
            layout.operator("robotic_twin.ws_disconnect", text="断开连接", icon='CANCEL')
        else:
            layout.operator("robotic_twin.ws_connect", text="连接服务器", icon='LINKED')
        
        if app.ws_manager:
            box = layout.box()
            box.label(text=f"地址: {app.ws_manager.ip_address}:{app.ws_manager.port}")


@reg_order(1)
class RT_PT_RobotControlPanel(BasePanel, bpy.types.Panel):
    """运动控制面板"""
    bl_idname = "RT_PT_robot_control"
    bl_label = "运动控制"
    
    def draw(self, context):
        layout = self.layout
        app = get_app()
        
        box = layout.box()
        box.label(text="当前关节角度", icon='BONE_DATA')
        
        angles = app.robot_controller.get_joint_angles_degrees()
        col = box.column(align=True)
        for i, angle in enumerate(angles):
            row = col.row(align=True)
            row.label(text=f"Axis {i+1}: {angle:.1f}°")
        
        layout.separator()
        row = layout.row(align=True)
        row.operator("robotic_twin.set_joints", text="设置角度")
        row.operator("robotic_twin.reset_zero", text="归零")
        
        layout.separator()
        row = layout.row()
        row.enabled = app.is_connected()
        row.operator("robotic_twin.send_move", text="发送到服务器")


@reg_order(2)
class RT_PT_AxisBindingPanel(BasePanel, bpy.types.Panel):
    """轴绑定面板"""
    bl_idname = "RT_PT_axis_binding"
    bl_label = "轴绑定"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "axis_selection", text="选择轴")
        layout.prop(context.scene, "rotation_axis", text="旋转轴方向")
        
        row = layout.row(align=True)
        row.operator("robotic_twin.bind_axis", text="绑定")
        row.operator("robotic_twin.unbind_axis", text="取消绑定")
        
        # 显示当前选中骨骼的绑定信息
        if context.mode == 'POSE' and context.active_pose_bone:
            bone = context.active_pose_bone.bone
            box = layout.box()
            box.label(text=f"骨骼: {bone.name}", icon='BONE_DATA')
            if "robot_axis" in bone:
                box.label(text=f"绑定轴: {bone['robot_axis']}")
                box.label(text=f"旋转方向: {bone.get('rotation_axis', 'Z')}")
            else:
                box.label(text="未绑定", icon='INFO')


@reg_order(3)
class RT_PT_DetectionPanel(BasePanel, bpy.types.Panel):
    """目标检测面板"""
    bl_idname = "RT_PT_detection"
    bl_label = "目标检测"
    
    def draw(self, context):
        layout = self.layout
        app = get_app()
        scene = context.scene

        box = layout.box()
        box.label(text="检测参数", icon='PREFERENCES')
        box.prop(scene, "rt_model_type", text="Model")
        box.prop(scene, "rt_confidence", text="Confidence")
        box.prop(scene, "rt_iou", text="IOU")
        selected = sorted(list(getattr(scene, "rt_class_flags", set()) or set()))
        if not selected:
            class_summary = "全部类别"
        else:
            labels = [CLASS_LABELS.get(k, k) for k in selected]
            class_summary = labels[0] if len(labels) == 1 else f"{labels[0]} + {len(labels) - 1}"
        box.label(text=f"Classes: {class_summary}", icon='OUTLINER_DATA_POINTCLOUD')
        box.prop_menu_enum(scene, "rt_class_flags", text="选择类别", icon='DOWNARROW_HLT')
        row = box.row(align=True)
        row.operator("robotic_twin.classes_select_all", text="全选")
        row.operator("robotic_twin.classes_clear", text="清空")
        box.prop(scene, "rt_debug_payload", text="发送前打印 payload")
        box.label(text="Classes 不选=检测全部类别", icon='INFO')
        
        # 发送图像按钮
        row = layout.row()
        row.scale_y = 1.2
        row.enabled = app.is_connected() and context.scene.camera is not None
        row.operator("robotic_twin.send_image", text="发送图像", icon='CAMERA_DATA')
        
        # 实时目标检测按钮
        layout.separator()
        row = layout.row()
        row.scale_y = 1.2
        row.enabled = app.is_connected() and context.scene.camera is not None
        row.operator("robotic_twin.realtime_detection", text="实时目标检测", icon='PLAY')
        
        if not app.is_connected():
            layout.separator()
            box = layout.box()
            box.label(text="需要连接服务器", icon='ERROR')
        
        if context.scene.camera is None:
            layout.separator()
            box = layout.box()
            box.label(text="场景中没有相机", icon='ERROR')
