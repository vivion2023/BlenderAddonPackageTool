# 指令执行器 - 执行统一格式的运动指令
import bpy
import math
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from ..protocol.message import (
    CommandType, GraspAction, SystemAction, 
    ExecutionStatus, OperationalStatus
)


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    command_id: str
    message: str = ""
    status: ExecutionStatus = ExecutionStatus.COMPLETED
    current_state: Optional[Dict[str, Any]] = None


class CommandExecutor:
    """指令执行器"""
    
    def __init__(self, armature_name: str = "Armature"):
        self.armature_name = armature_name
        self._joint_names = [f"axis_{i}" for i in range(1, 7)]
        self._current_status = OperationalStatus.IDLE
    
    def execute(self, message: Dict[str, Any]) -> ExecutionResult:
        """执行指令消息"""
        msg_type = message.get("type")
        payload = message.get("payload", {})
        command_id = payload.get("command_id", "unknown")
        
        print(f"Executing command: type={msg_type}, command_id={command_id}")
        
        if msg_type == "model_command":
            return self.execute_model_command(message)
        elif msg_type == "motion_command":
            return self._execute_motion(command_id, payload)
        elif msg_type == "grasp_command":
            return self._execute_grasp(command_id, payload)
        elif msg_type == "system_command":
            return self._execute_system(command_id, payload)
        else:
            return ExecutionResult(
                success=False,
                command_id=command_id,
                message=f"Unsupported command type: {msg_type}",
                status=ExecutionStatus.FAILED
            )

    def execute_model_command(self, message: Dict[str, Any]) -> ExecutionResult:
        """执行下行 model_command（当前重点）。"""
        payload = message.get("payload", {})
        command = payload.get("command", "")
        command_id = self._resolve_model_command_id(message)

        if command == "idle":
            self._current_status = OperationalStatus.IDLE
            return ExecutionResult(
                True,
                command_id,
                "Switched to idle",
                ExecutionStatus.COMPLETED,
                {"operational_status": self._current_status.value},
            )

        if command == "init_bones":
            return self._move_joint(command_id, {"joint_angles": [0.0] * len(self._joint_names)})

        if command == "execute_grasp_plan":
            return self._execute_grasp_plan(command_id, payload)

        return ExecutionResult(
            False,
            command_id,
            f"Unsupported model command: {command}",
            ExecutionStatus.FAILED,
        )

    def _resolve_model_command_id(self, message: Dict[str, Any]) -> str:
        payload = message.get("payload", {})
        return (
            payload.get("plan_id")
            or payload.get("command_id")
            or message.get("message_id")
            or "unknown"
        )

    def _execute_grasp_plan(self, command_id: str, payload: Dict[str, Any]) -> ExecutionResult:
        """按 sequence.action 分派执行。"""
        sequence = payload.get("sequence", []) or []
        self._current_status = OperationalStatus.EXECUTING

        try:
            for item in sorted(sequence, key=lambda x: x.get("step", 0)):
                action = item.get("action", "")
                name = item.get("name", "")
                step = item.get("step")
                joint_angles = item.get("joint_angles")

                # 优先使用六轴角执行（服务端下发 joint_angles 时无需再看 pose）
                if isinstance(joint_angles, list) and len(joint_angles) > 0:
                    print(
                        f"[GraspPlan] step={step} action=move_joint name={name} "
                        f"joint_angles={joint_angles}"
                    )
                    result = self._move_joint(command_id, {"joint_angles": joint_angles})
                    if not result.success:
                        return result
                    continue

                if action == "init_bones":
                    result = self._move_joint(command_id, {"joint_angles": [0.0] * len(self._joint_names)})
                    if not result.success:
                        return result
                elif action in {"move_joint", "move_cartesian"}:
                    # 没有 joint_angles 的运动步无法直接驱动六轴，跳过并告警
                    print(
                        f"[GraspPlan] step={step} action={action} name={name} "
                        "missing joint_angles, skipped"
                    )
                elif action in {"gripper_close", "gripper_open"}:
                    print(f"[GraspPlan] step={step} action={action} name={name}")
                else:
                    print(f"[GraspPlan] step={step} unsupported action={action} name={name}")
        finally:
            self._current_status = OperationalStatus.IDLE

        return ExecutionResult(
            True,
            command_id,
            f"execute_grasp_plan handled, steps={len(sequence)}",
            ExecutionStatus.COMPLETED,
            {"joint_positions": self.get_joint_positions()},
        )
    
    def _execute_motion(self, command_id: str, payload: Dict) -> ExecutionResult:
        """执行运动指令"""
        command_type = payload.get("command_type")
        motion_data = payload.get("motion_data", {})
        
        self._current_status = OperationalStatus.MOVING
        
        try:
            if command_type == CommandType.MOVE_JOINT.value:
                result = self._move_joint(command_id, motion_data)
            elif command_type == CommandType.MOVE_CARTESIAN.value:
                result = ExecutionResult(False, command_id, "Cartesian motion not implemented", ExecutionStatus.FAILED)
            else:
                result = ExecutionResult(False, command_id, f"Unsupported motion type: {command_type}", ExecutionStatus.FAILED)
        finally:
            self._current_status = OperationalStatus.IDLE
        
        return result
    
    def _move_joint(self, command_id: str, motion_data: Dict) -> ExecutionResult:
        """关节空间运动"""
        joint_angles = motion_data.get("joint_angles", [])
        joint_names = motion_data.get("joint_names", self._joint_names)
        
        if not joint_angles:
            return ExecutionResult(False, command_id, "Missing joint_angles parameter", ExecutionStatus.FAILED)
        
        armature = bpy.data.objects.get(self.armature_name)
        if not armature:
            return ExecutionResult(False, command_id, f"Armature not found: {self.armature_name}", ExecutionStatus.FAILED)
        
        actual_positions = []
        for name, angle in zip(joint_names, joint_angles):
            bone = armature.pose.bones.get(name)
            if bone:
                bone.rotation_euler[1] = angle
                actual_positions.append(angle)
            else:
                actual_positions.append(0.0)
        
        bpy.context.view_layer.update()
        
        return ExecutionResult(
            success=True,
            command_id=command_id,
            message="Joint motion executed successfully",
            status=ExecutionStatus.COMPLETED,
            current_state={"joint_positions": actual_positions}
        )
    
    def _execute_grasp(self, command_id: str, payload: Dict) -> ExecutionResult:
        """执行抓取指令"""
        grasp_data = payload.get("grasp_data", {})
        action = grasp_data.get("action", "")
        print(f"Executing gripper action: {action}")
        return ExecutionResult(True, command_id, f"Gripper action {action} executed", ExecutionStatus.COMPLETED)
    
    def _execute_system(self, command_id: str, payload: Dict) -> ExecutionResult:
        """执行系统指令"""
        system_data = payload.get("system_data", {})
        action = system_data.get("action", "")
        
        if action == SystemAction.RESET.value:
            return self._move_joint(command_id, {"joint_angles": [0.0] * 6})
        elif action == SystemAction.GET_STATUS.value:
            return ExecutionResult(
                True, command_id, "Status retrieved successfully", ExecutionStatus.COMPLETED,
                {"joint_positions": self.get_joint_positions(), "operational_status": self._current_status.value}
            )
        else:
            return ExecutionResult(False, command_id, f"Unsupported system command: {action}", ExecutionStatus.FAILED)
    
    def get_current_status(self) -> OperationalStatus:
        return self._current_status
    
    def get_joint_positions(self) -> List[float]:
        """获取当前关节角度"""
        armature = bpy.data.objects.get(self.armature_name)
        if not armature:
            return [0.0] * 6
        
        positions = []
        for name in self._joint_names:
            bone = armature.pose.bones.get(name)
            positions.append(bone.rotation_euler[1] if bone else 0.0)
        return positions
    
    def set_armature_name(self, name: str):
        self.armature_name = name
    
    def set_joint_names(self, names: List[str]):
        self._joint_names = names
