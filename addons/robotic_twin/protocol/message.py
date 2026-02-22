# 消息数据结构定义
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
import uuid
import time


class ClientType(Enum):
    """客户端类型"""
    WEB = "web"
    BLENDER = "blender"
    ROBOT = "robot"
    CAMERA = "camera"
    SERVER = "server"


class MessageType(Enum):
    """消息类型"""
    # 系统消息
    REGISTER = "register"
    REGISTER_ACK = "register_ack"
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"
    ERROR = "error"
    
    # 图像消息
    IMAGE_FRAME = "image_frame"
    IMAGE_REQUEST = "image_request"
    VIDEO_STREAM = "video_stream"
    
    # 检测消息
    DETECTION_REQUEST = "detection_request"
    DETECTION_RESULT = "detection_result"
    
    # 位姿消息
    POSE_TRANSFORM_REQUEST = "pose_transform_request"
    POSE_TRANSFORM_RESULT = "pose_transform_result"
    
    # 指令消息
    MODEL_COMMAND = "model_command"
    MOTION_COMMAND = "motion_command"
    GRASP_COMMAND = "grasp_command"
    SYSTEM_COMMAND = "system_command"
    COMMAND_ACK = "command_ack"
    
    # 状态消息
    ROBOT_STATUS = "robot_status"
    EXECUTION_STATUS = "execution_status"
    SYSTEM_STATUS = "system_status"


class CommandType(Enum):
    """运动指令类型"""
    MOVE_JOINT = "move_joint"
    MOVE_CARTESIAN = "move_cartesian"
    MOVE_PATH = "move_path"


class GraspAction(Enum):
    """抓取动作类型"""
    OPEN = "open"
    CLOSE = "close"
    GRASP = "grasp"
    RELEASE = "release"


class SystemAction(Enum):
    """系统指令类型"""
    INIT = "init"
    RESET = "reset"
    EMERGENCY_STOP = "emergency_stop"
    ENABLE = "enable"
    DISABLE = "disable"
    GET_STATUS = "get_status"
    CALIBRATE = "calibrate"


class CommandAckStatus(Enum):
    """指令确认状态"""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    QUEUED = "queued"


class ExecutionStatus(Enum):
    """执行状态"""
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OperationalStatus(Enum):
    """运行状态"""
    IDLE = "idle"
    MOVING = "moving"
    EXECUTING = "executing"
    PAUSED = "paused"
    ERROR = "error"
    EMERGENCY = "emergency"


@dataclass
class Sender:
    """发送者信息"""
    client_id: str
    client_type: str
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "client_id": self.client_id,
            "client_type": self.client_type
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'Sender':
        return cls(
            client_id=data.get("client_id", ""),
            client_type=data.get("client_type", "")
        )


@dataclass
class Target:
    """目标接收者"""
    client_id: Optional[str] = None
    client_type: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "client_id": self.client_id,
            "client_type": self.client_type
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Target':
        return cls(
            client_id=data.get("client_id"),
            client_type=data.get("client_type")
        )


@dataclass
class Metadata:
    """消息元数据"""
    request_id: Optional[str] = None
    priority: int = 1
    ttl: int = 30000
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "priority": self.priority,
            "ttl": self.ttl
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Metadata':
        return cls(
            request_id=data.get("request_id"),
            priority=data.get("priority", 1),
            ttl=data.get("ttl", 30000)
        )


@dataclass
class Message:
    """统一消息格式"""
    message_id: str
    type: str
    sender: Sender
    timestamp: int
    payload: Dict[str, Any]
    target: Optional[Target] = None
    metadata: Optional[Metadata] = None
    
    @classmethod
    def create(cls, msg_type: MessageType, payload: Dict[str, Any], 
               client_id: str, target: Optional[Target] = None,
               metadata: Optional[Metadata] = None) -> 'Message':
        """创建消息的工厂方法"""
        return cls(
            message_id=str(uuid.uuid4()),
            type=msg_type.value,
            sender=Sender(client_id=client_id, client_type=ClientType.BLENDER.value),
            timestamp=int(time.time() * 1000),
            payload=payload,
            target=target,
            metadata=metadata
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "message_id": self.message_id,
            "type": self.type,
            "sender": self.sender.to_dict(),
            "timestamp": self.timestamp,
            "payload": self.payload
        }
        if self.target:
            result["target"] = self.target.to_dict()
        if self.metadata:
            result["metadata"] = self.metadata.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """从字典创建消息"""
        target = None
        if "target" in data and data["target"]:
            target = Target.from_dict(data["target"])
        
        metadata = None
        if "metadata" in data and data["metadata"]:
            metadata = Metadata.from_dict(data["metadata"])
        
        return cls(
            message_id=data.get("message_id", str(uuid.uuid4())),
            type=data.get("type", ""),
            sender=Sender.from_dict(data.get("sender", {})),
            timestamp=data.get("timestamp", int(time.time() * 1000)),
            payload=data.get("payload", {}),
            target=target,
            metadata=metadata
        )
