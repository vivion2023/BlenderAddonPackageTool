import bpy
from bpy.props import FloatVectorProperty
from ..core.websocket_manager import get_websocket_manager

from ..config import __addon_name__
from ..operators.AddonOperators import ExampleOperator
from ....common.i18n.i18n import i18n
from ....common.types.framework import reg_order
import math

# 使用函数获取单例
ws_manager = get_websocket_manager()

class BasePanel(object):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ExampleAddon"

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return True


@reg_order(0)
class OBJECT_PT_CustomPanel(BasePanel, bpy.types.Panel):
    bl_label = "Websocket连接"
    bl_idname = "OBJECT_PT_custom_panel"


    @classmethod
    def poll(self,context):
        return True

    def draw(self, context):
        layout = self.layout

        # 定义状态对应的配置
        status_config = {
            True: {
                'alert': False,
                'text': "已连接",
                'icon': 'CHECKMARK',
                'operator': "robotic_twin.disconnect_websocket",
                'op_text': "断开连接"
            },
            False: {
                'alert': True,
                'text': "未连接",
                'icon': 'CANCEL',
                'operator': "robotic_twin.connect_websocket",
                'op_text': "连接WebSocket"
            }
        }

        # 获取当前状态的配置
        config = status_config[ws_manager.connected]
        
        
        # 应用配置
        row = layout.row()
        row.alert = config['alert']
        row.label(text=config['text'], icon=config['icon'])
        # 添加断开/连接按钮
        layout.operator(config['operator'], text=config['op_text'])
        layout.separator()
        layout.operator("robotic_twin.move_cube_random", text="随机移动物体")

@reg_order(1)  # 设置为1，让它在websocket面板之后显示
class OBJECT_PT_AxisBindingPanel(BasePanel, bpy.types.Panel):
    bl_label = "选择各个轴绑定的骨骼"
    bl_idname = "OBJECT_PT_axis_binding_panel"

    def draw(self, context):
        layout = self.layout
        
        # 创建下拉框
        row = layout.row()
        row.prop(context.scene, "axis_selection", text="")
        
        # 创建绑定按钮
        layout.operator("robotic_twin.bind_axis", text="绑定")

class OBJECT_OT_SetAxisValues(bpy.types.Operator):
    bl_idname = "robotic_twin.set_axis_values"
    bl_label = "设置轴值"
    
    axis_values: FloatVectorProperty(
        name="轴值",
        size=6,
        description="设置6个轴的值",
        default=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        min=-360.0,
        max=360.0,
        subtype='NONE',
        unit='ROTATION'
    )
    
    def execute(self, context):
        # 更新场景中的轴值
        context.scene.axis_values = self.axis_values
        return {'FINISHED'}
        
    def invoke(self, context, event):
        # 从场景中获取当前轴值
        self.axis_values = context.scene.axis_values
        return context.window_manager.invoke_props_dialog(self)
        
    def draw(self, context):
        layout = self.layout
        for i in range(6):
            row = layout.row()
            split = row.split(factor=0.33)
            split.label(text=f"Axis {i+1}")
            split.prop(self, "axis_values", index=i, text="")

class OBJECT_OT_ExecuteMove(bpy.types.Operator):
    bl_idname = "robotic_twin.execute_move"
    bl_label = "执行移动"
    
    def execute(self, context):
        from ..core.send_movecontrol import MoveControl
        if MoveControl.send_move_command(context.scene.axis_values):
            self.report({'INFO'}, "移动命令已发送")
        else:
            self.report({'ERROR'}, "发送移动命令失败")
        return {'FINISHED'}

@reg_order(2)
class OBJECT_PT_MoveControlPanel(BasePanel, bpy.types.Panel):
    bl_label = "运动控制"
    bl_idname = "OBJECT_PT_move_control_panel"
    
    def draw(self, context):
        layout = self.layout
        
        # 显示当前轴值的行，将弧度转换为度数显示
        row = layout.row()

        split = row.split(factor=0.67)
        values = [f"{math.degrees(v):.1f}" for v in context.scene.axis_values]
        split.operator("robotic_twin.set_axis_values", 
                    text=f"({', '.join(values)})")
        
        # 移动按钮
        split.operator("robotic_twin.execute_move", text="move")