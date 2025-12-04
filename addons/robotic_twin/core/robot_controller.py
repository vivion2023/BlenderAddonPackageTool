# 机器人控制器 - 封装 Blender 骨骼操作
import bpy
import math
from typing import List, Dict, Tuple


class RobotController:
    """机器人控制器"""
    
    def __init__(self, armature_name: str = "Armature"):
        self.armature_name = armature_name
        self._joint_names = [f"axis_{i}" for i in range(1, 7)]
        self._joint_count = 6
    
    def set_armature_name(self, name: str):
        self.armature_name = name
    
    def set_joint_names(self, names: List[str]):
        self._joint_names = names
        self._joint_count = len(names)
    
    def get_joint_names(self) -> List[str]:
        return self._joint_names.copy()
    
    def get_armature(self):
        return bpy.data.objects.get(self.armature_name)
    
    def is_armature_valid(self) -> bool:
        armature = self.get_armature()
        if not armature:
            return False
        for name in self._joint_names:
            if name not in armature.pose.bones:
                return False
        return True
    
    def get_bound_bones(self) -> Dict[str, Tuple]:
        """获取所有已绑定的骨骼信息
        返回: {axis_name: (pose_bone, rotation_axis)}
        """
        armature = self.get_armature()
        if not armature:
            return {}
        
        bound_bones = {}
        for pose_bone in armature.pose.bones:
            bone = pose_bone.bone
            if "robot_axis" in bone:
                axis_name = bone["robot_axis"]
                rotation_axis = bone.get("rotation_axis", "Z")
                bound_bones[axis_name] = (pose_bone, rotation_axis)
        return bound_bones
    
    def set_joint_angles(self, angles: List[float], update_view: bool = True) -> bool:
        """设置所有关节角度（弧度）
        基于绑定信息，使用轴角模式控制旋转
        """
        armature = self.get_armature()
        if not armature:
            return False
        
        bound_bones = self.get_bound_bones()
        
        for axis_name, angle in zip(self._joint_names, angles):
            if axis_name not in bound_bones:
                continue
            
            pose_bone, rotation_axis = bound_bones[axis_name]
            
            # 轴角模式: (W, X, Y, Z) 其中 W 是角度，XYZ 是轴向量
            axis_values = {'X': (1, 0, 0), 'Y': (0, 1, 0), 'Z': (0, 0, 1)}.get(rotation_axis, (0, 0, 1))
            pose_bone.rotation_axis_angle = (angle, axis_values[0], axis_values[1], axis_values[2])
        
        if update_view:
            bpy.context.view_layer.update()
        return True
    
    def get_joint_angles(self) -> List[float]:
        """获取所有关节角度（弧度）
        从轴角模式读取角度值
        """
        armature = self.get_armature()
        if not armature:
            return [0.0] * self._joint_count
        
        bound_bones = self.get_bound_bones()
        angles = []
        
        for axis_name in self._joint_names:
            if axis_name not in bound_bones:
                angles.append(0.0)
                continue
            
            pose_bone, rotation_axis = bound_bones[axis_name]
            
            # 从轴角模式读取角度 (W, X, Y, Z)
            if pose_bone.rotation_mode == 'AXIS_ANGLE':
                angles.append(pose_bone.rotation_axis_angle[0])  # W 是角度
            else:
                angles.append(0.0)
        
        return angles
    
    def reset_to_zero(self, update_view: bool = True) -> bool:
        return self.set_joint_angles([0.0] * self._joint_count, update_view)
    
    @staticmethod
    def degrees_to_radians(degrees: List[float]) -> List[float]:
        return [math.radians(d) for d in degrees]
    
    @staticmethod
    def radians_to_degrees(radians: List[float]) -> List[float]:
        return [math.degrees(r) for r in radians]
    
    def get_joint_angles_degrees(self) -> List[float]:
        return self.radians_to_degrees(self.get_joint_angles())
    
    def set_joint_angles_degrees(self, degrees: List[float], update_view: bool = True) -> bool:
        return self.set_joint_angles(self.degrees_to_radians(degrees), update_view)
