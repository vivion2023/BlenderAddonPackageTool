# 消息构建器 - 负责构建符合协议的消息
import uuid
import base64
from typing import Dict, Any, List, Optional

from .message import (
    Message, MessageType, Target, Metadata, ClientType,
    CommandAckStatus, ExecutionStatus, OperationalStatus
)


class MessageBuilder:
    """消息构建器 - 负责构建符合协议的消息"""
    
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.client_type = ClientType.BLENDER.value
    
    # ==================== 系统消息 ====================
    
    def build_register(self, capabilities: List[str], device_info: Dict[str, Any]) -> Message:
        """构建客户端注册消息"""
        payload = {
            "capabilities": capabilities,
            "device_info": device_info
        }
        return Message.create(MessageType.REGISTER, payload, self.client_id)
    
    def build_heartbeat(self, sequence: int) -> Message:
        """构建心跳消息"""
        payload = {"sequence": sequence}
        return Message.create(MessageType.HEARTBEAT, payload, self.client_id)
    
    def build_error(self, error_code: str, error_type: str, 
                    message: str, details: Dict = None,
                    request_id: str = None) -> Message:
        """构建错误消息"""
        payload = {
            "error_code": error_code,
            "error_type": error_type,
            "message": message,
            "details": details or {}
        }
        metadata = Metadata(request_id=request_id) if request_id else None
        return Message.create(MessageType.ERROR, payload, self.client_id, metadata=metadata)
    
    # ==================== 图像消息 ====================
    
    def build_image_frame(self, image_data: bytes, width: int, height: int,
                          camera_info: Optional[Dict] = None,
                          frame_number: int = 0) -> Message:
        """构建图像帧消息"""
        payload = {
            "image_id": str(uuid.uuid4()),
            "format": "jpeg",
            "encoding": "base64",
            "width": width,
            "height": height,
            "data": base64.b64encode(image_data).decode('utf-8'),
            "camera_info": camera_info or {}
        }
        metadata = Metadata()
        msg = Message.create(MessageType.IMAGE_FRAME, payload, self.client_id, metadata=metadata)
        return msg
    
    # ==================== 运动指令消息 ====================
    
    def build_motion_command(self, joint_angles: List[float], 
                             joint_names: List[str],
                             execution_target: List[str] = None,
                             speed: float = 0.2,
                             acceleration: float = 0.1) -> Message:
        """构建关节运动指令消息"""
        payload = {
            "command_id": str(uuid.uuid4()),
            "command_type": "move_joint",
            "execution_target": execution_target or ["blender", "robot"],
            "motion_data": {
                "joint_angles": joint_angles,
                "joint_names": joint_names
            },
            "motion_params": {
                "speed": speed,
                "acceleration": acceleration,
                "motion_type": "joint_space"
            },
            "safety": {
                "collision_check": True,
                "workspace_check": True,
                "max_velocity": 1.0
            }
        }
        metadata = Metadata(priority=1, ttl=30000)
        target = Target(client_type="all")
        return Message.create(MessageType.MOTION_COMMAND, payload, self.client_id, 
                              target=target, metadata=metadata)
    
    # ==================== 指令确认消息 ====================
    
    def build_command_ack(self, command_id: str, status: CommandAckStatus, 
                          message: str = "", request_id: str = None) -> Message:
        """构建指令确认消息"""
        payload = {
            "command_id": command_id,
            "status": status.value if isinstance(status, CommandAckStatus) else status,
            "message": message
        }
        metadata = Metadata(request_id=request_id) if request_id else None
        return Message.create(MessageType.COMMAND_ACK, payload, self.client_id, metadata=metadata)
    
    # ==================== 状态消息 ====================
    
    def build_execution_status(self, command_id: str, status: ExecutionStatus,
                               progress: Dict[str, Any] = None,
                               current_state: Dict[str, Any] = None,
                               estimated_completion_ms: int = None) -> Message:
        """构建执行状态消息"""
        payload = {
            "command_id": command_id,
            "status": status.value if isinstance(status, ExecutionStatus) else status,
            "progress": progress or {},
            "current_state": current_state or {}
        }
        if estimated_completion_ms is not None:
            payload["estimated_completion_ms"] = estimated_completion_ms
        return Message.create(MessageType.EXECUTION_STATUS, payload, self.client_id)
    
    def build_robot_status(self, joint_positions: List[float],
                           tcp_position: Dict[str, float] = None,
                           tcp_orientation: Dict[str, float] = None,
                           operational_status: OperationalStatus = OperationalStatus.IDLE,
                           gripper_state: Dict[str, Any] = None,
                           error_state: Dict[str, Any] = None) -> Message:
        """构建机器人状态消息"""
        payload = {
            "robot_id": self.client_id,
            "connection_status": "connected",
            "operational_status": operational_status.value if isinstance(operational_status, OperationalStatus) else operational_status,
            "current_state": {
                "joint_positions": joint_positions,
                "joint_velocities": [0.0] * len(joint_positions),
                "tcp_position": tcp_position or {"x": 0.0, "y": 0.0, "z": 0.0},
                "tcp_orientation": tcp_orientation or {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}
            },
            "gripper_state": gripper_state or {
                "position": 0.0,
                "force": 0.0,
                "object_detected": False
            },
            "error_state": error_state or {
                "has_error": False,
                "error_code": None,
                "error_message": None
            }
        }
        return Message.create(MessageType.ROBOT_STATUS, payload, self.client_id)
