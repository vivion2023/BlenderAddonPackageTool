# 连接相关操作符
import bpy
from bpy.props import StringProperty, IntProperty

from ..core.app import get_app


class WS_OT_Connect(bpy.types.Operator):
    """连接到 WebSocket 服务器"""
    bl_idname = "robotic_twin.ws_connect"
    bl_label = "连接 WebSocket"
    bl_description = "连接到视觉引导系统服务器"
    
    ip_address: StringProperty(name="服务器地址", default="127.0.0.1")
    port: IntProperty(name="端口", default=5001, min=1, max=65535)
    
    @classmethod
    def poll(cls, context):
        app = get_app()
        return not app.is_connected()
    
    def invoke(self, context, event):
        app = get_app()
        if app.ws_manager:
            self.ip_address = app.ws_manager.ip_address
            self.port = app.ws_manager.port
        return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
        app = get_app()
        app.connect(self.ip_address, self.port)
        self.report({'INFO'}, f"Connecting to {self.ip_address}:{self.port}...")
        return {'FINISHED'}


class WS_OT_Disconnect(bpy.types.Operator):
    """断开 WebSocket 连接"""
    bl_idname = "robotic_twin.ws_disconnect"
    bl_label = "断开连接"
    
    @classmethod
    def poll(cls, context):
        app = get_app()
        return app.is_connected()
    
    def execute(self, context):
        app = get_app()
        app.disconnect()
        self.report({'INFO'}, "Disconnected")
        return {'FINISHED'}


class WS_OT_SendStatus(bpy.types.Operator):
    """发送机器人状态"""
    bl_idname = "robotic_twin.send_status"
    bl_label = "发送状态"
    
    @classmethod
    def poll(cls, context):
        app = get_app()
        return app.is_connected()
    
    def execute(self, context):
        app = get_app()
        app.send_robot_status()
        self.report({'INFO'}, "Status sent")
        return {'FINISHED'}
