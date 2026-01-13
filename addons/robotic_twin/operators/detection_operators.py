# 检测相关操作符
import bpy
import os
import json
from bpy.props import StringProperty, FloatProperty, EnumProperty

from ..core.app import get_app
from ..protocol.message import MessageType


class WS_OT_DetectImage(bpy.types.Operator):
    """发送图片进行检测"""
    bl_idname = "robotic_twin.detect_image"
    bl_label = "检测图片"
    bl_description = "发送图片到服务器进行目标检测"
    
    filepath: StringProperty(
        name="Image Path",
        description="Path to the image file",
        default="",
        subtype='FILE_PATH'
    )
    
    confidence: FloatProperty(
        name="Confidence",
        description="Detection confidence threshold",
        default=0.5,
        min=0.0,
        max=1.0
    )
    
    model_type: EnumProperty(
        name="Model",
        items=[
            ("yolov8n", "YOLOv8 Nano", "Fastest"),
            ("yolov8s", "YOLOv8 Small", "Balanced"),
            ("yolov8m", "YOLOv8 Medium", "More Accurate"),
        ],
        default="yolov8n"
    )
    
    @classmethod
    def poll(cls, context):
        app = get_app()
        return app.is_connected()

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        app = get_app()
        
        path = self.filepath
        if not path:
             self.report({'ERROR'}, "No file selected")
             return {'CANCELLED'}

        path = bpy.path.abspath(path)
        if not os.path.exists(path):
            self.report({'ERROR'}, f"Image not found: {path}")
            return {'CANCELLED'}
        
        try:
            with open(path, "rb") as f:
                image_data = f.read()
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read image: {e}")
            return {'CANCELLED'}
            
        # Register response handler
        # Note: This is a simple implementation. For production, we might need a more robust correlation mechanism using request_id
        def handle_result(msg_dict):
            if msg_dict.get("type") == MessageType.DETECTION_RESULT.value:
                payload = msg_dict.get("payload", {})
                success = payload.get("success", False)
                if success:
                    detections = payload.get("detections", [])
                    print(f"Detection Success! Found {len(detections)} objects.")
                    for det in detections:
                        print(f" - {det.get('class_name')} ({det.get('confidence'):.2f})")
                else:
                    print("Detection failed on server side.")
                
                # Unregister self after receiving result (Single Shot)
                # Note: This limits us to one concurrent request if we just use message type routing without ID filtering.
                # For this demo/prototype, it suffices.
                app.ws_manager.message_router.unregister_handler(MessageType.DETECTION_RESULT)

        # Register the handler
        app.ws_manager.message_router.register_handler(MessageType.DETECTION_RESULT, handle_result)
        
        # Build and send message
        msg = app.ws_manager.message_builder.build_detection_request(
            image_data=image_data,
            model=self.model_type,
            confidence=self.confidence
        )
        
        if app.ws_manager.send_message(msg):
            self.report({'INFO'}, "Detection request sent")
        else:
            self.report({'ERROR'}, "Failed to send request")
            # Cleanup handler if send fails
            app.ws_manager.message_router.unregister_handler(MessageType.DETECTION_RESULT)
            return {'CANCELLED'}
            
        return {'FINISHED'}


class ROBOT_OT_RealtimeDetection(bpy.types.Operator):
    """实时目标检测"""
    bl_idname = "robotic_twin.realtime_detection"
    bl_label = "实时目标检测"
    bl_description = "启动实时目标检测"
    
    @classmethod
    def poll(cls, context):
        app = get_app()
        # 需要连接且场景中有相机
        return app.is_connected() and context.scene.camera is not None
    
    def execute(self, context):
        # TODO: 实现实时检测功能
        self.report({'INFO'}, "实时检测功能待实现")
        return {'FINISHED'}
