# 机器人控制相关操作符
import bpy
import math
from bpy.props import FloatVectorProperty

from ..core.app import get_app


class ROBOT_OT_SetJoints(bpy.types.Operator):
    """设置机器人关节角度"""
    bl_idname = "robotic_twin.set_joints"
    bl_label = "设置关节角度"
    bl_options = {'REGISTER', 'UNDO'}
    
    joint_angles: FloatVectorProperty(
        name="关节角度", size=6,
        default=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        min=-360.0, max=360.0
    )
    
    def invoke(self, context, event):
        app = get_app()
        current = app.robot_controller.get_joint_angles_degrees()
        self.joint_angles = tuple(current)
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        for i in range(6):
            row = layout.row()
            split = row.split(factor=0.3)
            split.label(text=f"Axis {i+1}")
            split.prop(self, "joint_angles", index=i, text="")
    
    def execute(self, context):
        app = get_app()
        radians = [math.radians(d) for d in self.joint_angles]
        if app.robot_controller.set_joint_angles(radians):
            self.report({'INFO'}, "Joint angles set")
            return {'FINISHED'}
        self.report({'ERROR'}, "Failed to set joints")
        return {'CANCELLED'}


class ROBOT_OT_ResetToZero(bpy.types.Operator):
    """复位机器人到零位"""
    bl_idname = "robotic_twin.reset_zero"
    bl_label = "复位到零位"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        app = get_app()
        if app.robot_controller.reset_to_zero():
            self.report({'INFO'}, "Reset to zero position")
            return {'FINISHED'}
        self.report({'ERROR'}, "Failed to reset")
        return {'CANCELLED'}


class ROBOT_OT_SendMoveCommand(bpy.types.Operator):
    """发送当前关节角度到服务器"""
    bl_idname = "robotic_twin.send_move"
    bl_label = "发送运动指令"
    
    @classmethod
    def poll(cls, context):
        app = get_app()
        return app.is_connected()
    
    def execute(self, context):
        app = get_app()
        import uuid
        from ..protocol.message import Message, MessageType
        
        joint_angles = app.get_joint_angles()
        payload = {
            "command_id": str(uuid.uuid4()),
            "command_type": "move_joint",
            "motion_data": {
                "joint_angles": joint_angles,
                "joint_names": app.robot_controller.get_joint_names()
            }
        }
        
        msg = Message.create(MessageType.MOTION_COMMAND, payload, app.ws_manager.client_id)
        if app.ws_manager.send_message(msg):
            self.report({'INFO'}, "Motion command sent")
            return {'FINISHED'}
        self.report({'ERROR'}, "Failed to send")
        return {'CANCELLED'}


class ROBOT_OT_BindAxis(bpy.types.Operator):
    """绑定骨骼到轴"""
    bl_idname = "robotic_twin.bind_axis"
    bl_label = "绑定轴"
    
    @classmethod
    def poll(cls, context):
        return context.mode == 'POSE' and context.active_pose_bone is not None
    
    def execute(self, context):
        active_bone = context.active_pose_bone
        if not active_bone:
            self.report({'ERROR'}, "Please select a bone")
            return {'CANCELLED'}
        
        selected_axis = context.scene.axis_selection
        rotation_axis = context.scene.rotation_axis
        
        # 将绑定信息存储到骨骼的自定义属性中
        bone = active_bone.bone
        bone["robot_axis"] = selected_axis
        bone["rotation_axis"] = rotation_axis
        
        # 设置为轴角模式，当前姿态即为初始状态（角度0）
        axis_values = {'X': (1, 0, 0), 'Y': (0, 1, 0), 'Z': (0, 0, 1)}.get(rotation_axis, (0, 0, 1))
        active_bone.rotation_mode = 'AXIS_ANGLE'
        active_bone.rotation_axis_angle = (0, axis_values[0], axis_values[1], axis_values[2])
        
        self.report({'INFO'}, f"bone: '{bone.name}' bound to {selected_axis}, axis: {rotation_axis}")
        return {'FINISHED'}


class ROBOT_OT_UnbindAxis(bpy.types.Operator):
    """取消骨骼的轴绑定"""
    bl_idname = "robotic_twin.unbind_axis"
    bl_label = "取消绑定"
    
    @classmethod
    def poll(cls, context):
        if context.mode != 'POSE' or context.active_pose_bone is None:
            return False
        # 只有已绑定的骨骼才能取消绑定
        bone = context.active_pose_bone.bone
        return "robot_axis" in bone
    
    def execute(self, context):
        bone = context.active_pose_bone.bone
        bone_name = bone.name
        
        # 删除自定义属性
        if "robot_axis" in bone:
            del bone["robot_axis"]
        if "rotation_axis" in bone:
            del bone["rotation_axis"]
        
        self.report({'INFO'}, f"bone: '{bone_name}' unbound")
        return {'FINISHED'}
