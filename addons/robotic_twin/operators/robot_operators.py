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
        active_bone.bone.name = selected_axis
        self.report({'INFO'}, f"Bone bound to {selected_axis}")
        return {'FINISHED'}
