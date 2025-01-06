import bpy
from bpy.props import StringProperty, IntProperty

from ..config import __addon_name__
from ..preference.AddonPreferences import ExampleAddonPreferences

class ExampleOperator(bpy.types.Operator):
    '''ExampleAddon'''
    bl_idname = "object.example_ops"
    bl_label = "ExampleOperator"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.active_object is not None

    def execute(self, context: bpy.types.Context):
        addon_prefs = bpy.context.preferences.addons[__addon_name__].preferences
        assert isinstance(addon_prefs, ExampleAddonPreferences)
        context.active_object.scale *= addon_prefs.number
        return {'FINISHED'}
    
        # 添加轴选择的枚举属性
    def register_axis_properties():
        axis_items = [
            ('axis_1', 'Axis 1', 'First axis'),
            ('axis_2', 'Axis 2', 'Second axis'),
            ('axis_3', 'Axis 3', 'Third axis'),
            ('axis_4', 'Axis 4', 'Fourth axis'),
            ('axis_5', 'Axis 5', 'Fifth axis'),
            ('axis_6', 'Axis 6', 'Sixth axis'),
        ]
        bpy.types.Scene.axis_selection = EnumProperty(
            items=axis_items,
            name="Axis Selection",
            default='axis_1'
        )

class OBJECT_OT_BindAxis(bpy.types.Operator):
    bl_idname = "robotic_twin.bind_axis"
    bl_label = "Bind Axis"
    bl_description = "Bind selected bone to the chosen axis"
    
    def execute(self, context):
        # 检查是否在姿态模式
        if context.mode != 'POSE':
            self.report({'ERROR'}, "请切换到姿态模式!")
            return {'CANCELLED'}
            
        # 获取选中的骨骼
        active_bone = context.active_pose_bone
        if not active_bone:
            self.report({'ERROR'}, "请选择一个骨骼!")
            return {'CANCELLED'}
            
        # 获取选择的轴
        selected_axis = context.scene.axis_selection
        
        # 重命名骨骼
        active_bone.bone.name = selected_axis
        print(f"{selected_axis} connect successfully")
        
        return {'FINISHED'}