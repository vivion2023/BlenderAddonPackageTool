# 机器人控制相关操作符
import bpy
import math
import os
import tempfile
import json
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
        
        # 获取当前各轴角度（弧度）
        joint_angles = app.robot_controller.get_joint_angles()
        joint_names = app.robot_controller.get_joint_names()
        
        # 使用 MessageBuilder 构建运动指令消息
        msg = app.ws_manager.message_builder.build_motion_command(
            joint_angles=joint_angles,
            joint_names=joint_names
        )
        
        if app.ws_manager.send_message(msg):
            # 显示发送的角度信息（转换为度数便于查看）
            angles_deg = [math.degrees(a) for a in joint_angles]
            angles_str = ", ".join([f"{a:.1f}°" for a in angles_deg])
            self.report({'INFO'}, f"Motion command sent: [{angles_str}]")
            return {'FINISHED'}
        
        self.report({'ERROR'}, "Failed to send motion command")
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


class ROBOT_OT_SendImage(bpy.types.Operator):
    """发送相机拍摄的图像到服务器"""
    bl_idname = "robotic_twin.send_image"
    bl_label = "发送图像"
    
    @classmethod
    def poll(cls, context):
        app = get_app()
        # 需要连接且场景中有相机
        return app.is_connected() and context.scene.camera is not None
    
    def execute(self, context):
        app = get_app()
        scene = context.scene
        camera = scene.camera

        model_type = (getattr(scene, "rt_model_type", "yolov8") or "yolov8").strip()
        confidence = float(getattr(scene, "rt_confidence", 0.5))
        iou = float(getattr(scene, "rt_iou", 0.45))
        classes_text = (getattr(scene, "rt_classes", "") or "").strip()
        debug_payload = bool(getattr(scene, "rt_debug_payload", False))
        classes = None
        if classes_text:
            parsed = [item.strip() for item in classes_text.split(",") if item.strip()]
            classes = parsed or None
        
        if not camera:
            self.report({'ERROR'}, "场景中没有相机")
            return {'CANCELLED'}

        try:
            render = scene.render
            width = int(render.resolution_x * render.resolution_percentage / 100)
            height = int(render.resolution_y * render.resolution_percentage / 100)
            if width <= 0 or height <= 0:
                self.report({'ERROR'}, "渲染分辨率无效")
                return {'CANCELLED'}

            old_path = render.filepath
            old_format = render.image_settings.file_format
            old_quality = getattr(render.image_settings, "quality", 90)

            tmp_file = tempfile.NamedTemporaryFile(prefix="rt_frame_", suffix=".jpg", delete=False)
            tmp_path = tmp_file.name
            tmp_file.close()

            try:
                render.filepath = tmp_path
                render.image_settings.file_format = 'JPEG'
                render.image_settings.quality = 85
                bpy.ops.render.render(write_still=True)

                if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                    self.report({'ERROR'}, "渲染输出为空")
                    return {'CANCELLED'}

                with open(tmp_path, "rb") as f:
                    image_data = f.read()
            finally:
                render.filepath = old_path
                render.image_settings.file_format = old_format
                render.image_settings.quality = old_quality
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass

            # 构建并发送 image_frame（服务端按该消息触发检测并回 model_command）
            msg = app.ws_manager.message_builder.build_image_frame(
                image_data=image_data,
                width=width,
                height=height,
                model_type=model_type,
                confidence=confidence,
                iou=iou,
                classes=classes,
            )

            if debug_payload:
                msg_dict = msg.to_dict()
                payload_preview = dict(msg_dict.get("payload", {}))
                if "data" in payload_preview:
                    del payload_preview["data"]
                print("[SendImage] payload preview:")
                print(json.dumps(payload_preview, ensure_ascii=False, indent=2))
            
            if app.ws_manager.send_message(msg):
                # 计算图像大小 (KB)
                size_kb = len(image_data) / 1024
                self.report({'INFO'}, f"图像已发送并触发检测 ({width}x{height}, {size_kb:.1f}KB)")
                return {'FINISHED'}
            
            self.report({'ERROR'}, "发送图像失败")
            return {'CANCELLED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"捕获图像失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

