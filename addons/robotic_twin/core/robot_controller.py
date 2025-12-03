# 机器人控制器 - 封装 Blender 骨骼操作
import bpy
import math
from typing import List, Dict


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
    
    def set_joint_angles(self, angles: List[float], update_view: bool = True) -> bool:
        """设置所有关节角度（弧度）"""
        armature = self.get_armature()
        if not armature:
            return False
        
        for name, angle in zip(self._joint_names, angles):
            bone = armature.pose.bones.get(name)
            if bone:
                bone.rotation_euler[1] = angle
        
        if update_view:
            bpy.context.view_layer.update()
        return True
    
    def get_joint_angles(self) -> List[float]:
        """获取所有关节角度（弧度）"""
        armature = self.get_armature()
        if not armature:
            return [0.0] * self._joint_count
        
        angles = []
        for name in self._joint_names:
            bone = armature.pose.bones.get(name)
            angles.append(bone.rotation_euler[1] if bone else 0.0)
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
