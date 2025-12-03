# Blender 插件项目重构设计文档

## 1. 项目概述

### 1.1 项目背景

`robotic_twin` 是一个 Blender 插件，用于实现 **视觉引导系统** 与 **Blender 虚拟环境** 之间的通信。该插件作为视觉引导系统的客户端，负责：

1. **接收运动指令** - 从视觉引导系统接收机器人运动指令，驱动 Blender 中的虚拟机器人
2. **发送图像数据** - 将 Blender 虚拟相机的渲染图像发送给视觉引导系统
3. **状态反馈** - 向视觉引导系统报告虚拟机器人的当前状态

### 1.2 当前问题

| 问题 | 描述 |
|------|------|
| **协议不统一** | 当前使用简单的 `{"action": 0/1, ...}` 格式，与统一通信协议不兼容 |
| **缺少消息标识** | 没有 `message_id`、`sender`、`target` 等标准字段 |
| **缺少客户端注册** | 没有实现 `register` 消息，服务端无法识别客户端身份 |
| **缺少心跳机制** | 没有心跳检测，无法及时发现连接断开 |
| **缺少状态反馈** | 没有实现 `command_ack`、`execution_status` 等状态消息 |
| **指令类型单一** | 仅支持简单的移动命令，不支持标准的 `motion_command`、`grasp_command` 等 |

### 1.3 重构目标

1. **完全兼容统一通信协议** - 实现协议文档定义的所有消息类型
2. **模块化设计** - 清晰的分层架构，便于维护和扩展
3. **健壮的连接管理** - 支持心跳、自动重连、错误处理
4. **完整的状态反馈** - 指令确认、执行状态、机器人状态上报

---

## 2. 系统架构

### 2.1 分层架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                       UI 层 (Blender Panels)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ 连接管理    │  │ 运动控制    │  │ 状态显示    │              │
│  │   面板      │  │   面板      │  │   面板      │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
├──────────────────────────────────────────────────────────────────┤
│                       操作层 (Operators)                          │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  连接操作 | 断开操作 | 发送命令 | 图像采集 | 状态查询       │ │
│  └─────────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────┤
│                       协议层 (Protocol)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ MessageBuilder│ │MessageParser│  │MessageRouter│              │
│  │  消息构建器  │  │ 消息解析器  │  │ 消息路由器  │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
├──────────────────────────────────────────────────────────────────┤
│                       指令层 (Command)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │CommandParser│  │CommandExecutor│ │CommandQueue│              │
│  │  指令解析器  │  │  指令执行器  │  │  指令队列  │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
├──────────────────────────────────────────────────────────────────┤
│                       核心层 (Core)                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │RobotController│ │ImageCapture │  │StateManager│              │
│  │ 机器人控制器 │  │  图像采集   │  │ 状态管理器 │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
├──────────────────────────────────────────────────────────────────┤
│                       传输层 (Transport)                          │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              WebSocketManager (连接管理器)                    │ │
│  │  - 连接/断开 | 心跳维护 | 消息收发 | 自动重连                │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流向

```
                    ┌─────────────────────────────────────┐
                    │          视觉引导系统（服务端）        │
                    └─────────────────┬───────────────────┘
                                      │
                              WebSocket 通信
                                      │
┌─────────────────────────────────────┼─────────────────────────────────────┐
│                                     │                                     │
│  ┌──────────────────────────────────┴──────────────────────────────────┐  │
│  │                     WebSocketManager                                 │  │
│  │                   (接收消息 / 发送消息)                               │  │
│  └──────────────────────────────────┬──────────────────────────────────┘  │
│                                     │                                     │
│                    ┌────────────────┼────────────────┐                    │
│                    ↓                ↓                ↓                    │
│  ┌─────────────────────┐ ┌─────────────────┐ ┌─────────────────────┐     │
│  │   MessageParser     │ │  MessageRouter  │ │   MessageBuilder    │     │
│  │   (解析接收消息)     │ │  (路由分发)     │ │   (构建发送消息)    │     │
│  └──────────┬──────────┘ └────────┬────────┘ └──────────┬──────────┘     │
│             │                     │                     ↑                 │
│             ↓                     ↓                     │                 │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                        CommandExecutor                               │ │
│  │  motion_command → 驱动骨骼旋转                                       │ │
│  │  grasp_command  → 控制夹爪                                           │ │
│  │  system_command → 初始化/复位                                        │ │
│  │  image_request  → 触发图像采集                                       │ │
│  └──────────────────────────────────┬──────────────────────────────────┘ │
│                                     │                                     │
│                    ┌────────────────┼────────────────┐                    │
│                    ↓                ↓                ↓                    │
│  ┌─────────────────────┐ ┌─────────────────┐ ┌─────────────────────┐     │
│  │  RobotController    │ │  ImageCapture   │ │   StateManager      │     │
│  │  (骨骼/物体控制)    │ │  (相机渲染)     │ │   (状态管理)        │     │
│  └─────────────────────┘ └─────────────────┘ └─────────────────────┘     │
│                                                                           │
│                              Blender 插件                                 │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 目录结构设计

```
addons/robotic_twin/
├── __init__.py                    # 插件入口，注册/注销
├── config.py                      # 插件配置
├── blender_manifest.toml          # Blender 扩展清单
│
├── protocol/                      # 协议层 - 消息处理
│   ├── __init__.py
│   ├── message.py                 # 消息数据结构定义
│   ├── message_types.py           # 消息类型常量
│   ├── message_builder.py         # 消息构建器
│   ├── message_parser.py          # 消息解析器
│   └── message_router.py          # 消息路由器
│
├── command/                       # 指令层 - 指令处理
│   ├── __init__.py
│   ├── command_types.py           # 指令类型定义
│   ├── command_parser.py          # 指令解析器
│   ├── command_executor.py        # 指令执行器（重构）
│   └── command_queue.py           # 指令队列
│
├── core/                          # 核心层 - 业务逻辑
│   ├── __init__.py
│   ├── robot_controller.py        # 机器人控制器（骨骼驱动）
│   ├── image_capture.py           # 图像采集模块
│   ├── state_manager.py           # 状态管理器
│   └── config_manager.py          # 配置管理
│
├── transport/                     # 传输层 - WebSocket 通信
│   ├── __init__.py
│   ├── websocket_manager.py       # WebSocket 管理器（重构）
│   ├── heartbeat.py               # 心跳管理
│   └── reconnect.py               # 自动重连
│
├── operators/                     # Blender 操作符
│   ├── __init__.py
│   ├── connection_operators.py    # 连接相关操作
│   ├── command_operators.py       # 命令相关操作
│   └── capture_operators.py       # 图像采集操作
│
├── panels/                        # Blender 面板
│   ├── __init__.py
│   ├── connection_panel.py        # 连接管理面板
│   ├── control_panel.py           # 运动控制面板
│   └── status_panel.py            # 状态显示面板
│
├── preference/                    # 插件偏好设置
│   ├── __init__.py
│   └── addon_preferences.py
│
├── i18n/                          # 国际化
│   ├── __init__.py
│   └── dictionary.py
│
└── utils/                         # 工具函数
    ├── __init__.py
    ├── uuid_utils.py              # UUID 生成
    └── math_utils.py              # 数学工具
```

---

## 4. 核心模块设计

### 4.1 消息数据结构 (`protocol/message.py`)

```python
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
    
    # 指令消息
    MOTION_COMMAND = "motion_command"
    GRASP_COMMAND = "grasp_command"
    SYSTEM_COMMAND = "system_command"
    COMMAND_ACK = "command_ack"
    
    # 状态消息
    ROBOT_STATUS = "robot_status"
    EXECUTION_STATUS = "execution_status"

@dataclass
class Sender:
    """发送者信息"""
    client_id: str
    client_type: str

@dataclass
class Target:
    """目标接收者"""
    client_id: Optional[str] = None
    client_type: Optional[str] = None

@dataclass
class Metadata:
    """消息元数据"""
    request_id: Optional[str] = None
    priority: int = 1
    ttl: int = 30000

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
               client_id: str, target: Optional[Target] = None) -> 'Message':
        """创建消息的工厂方法"""
        return cls(
            message_id=str(uuid.uuid4()),
            type=msg_type.value,
            sender=Sender(client_id=client_id, client_type=ClientType.BLENDER.value),
            timestamp=int(time.time() * 1000),
            payload=payload,
            target=target
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "message_id": self.message_id,
            "type": self.type,
            "sender": {
                "client_id": self.sender.client_id,
                "client_type": self.sender.client_type
            },
            "timestamp": self.timestamp,
            "payload": self.payload
        }
        if self.target:
            result["target"] = {
                "client_id": self.target.client_id,
                "client_type": self.target.client_type
            }
        if self.metadata:
            result["metadata"] = {
                "request_id": self.metadata.request_id,
                "priority": self.metadata.priority,
                "ttl": self.metadata.ttl
            }
        return result
```

### 4.2 消息构建器 (`protocol/message_builder.py`)

```python
import uuid
import time
import base64
from typing import Dict, Any, List, Optional
from .message import Message, MessageType, Target, Metadata, ClientType

class MessageBuilder:
    """消息构建器 - 负责构建符合协议的消息"""
    
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.client_type = ClientType.BLENDER.value
    
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
    
    def build_image_frame(self, image_data: bytes, width: int, height: int,
                          camera_info: Optional[Dict] = None) -> Message:
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
        return Message.create(MessageType.IMAGE_FRAME, payload, self.client_id)
    
    def build_command_ack(self, command_id: str, status: str, 
                          message: str = "", request_id: str = None) -> Message:
        """构建指令确认消息"""
        payload = {
            "command_id": command_id,
            "status": status,  # accepted, rejected, queued
            "message": message
        }
        msg = Message.create(MessageType.COMMAND_ACK, payload, self.client_id)
        if request_id:
            msg.metadata = Metadata(request_id=request_id)
        return msg
    
    def build_execution_status(self, command_id: str, status: str,
                               progress: Dict[str, Any] = None,
                               current_state: Dict[str, Any] = None) -> Message:
        """构建执行状态消息"""
        payload = {
            "command_id": command_id,
            "status": status,  # queued, executing, completed, failed, cancelled
            "progress": progress or {},
            "current_state": current_state or {}
        }
        return Message.create(MessageType.EXECUTION_STATUS, payload, self.client_id)
    
    def build_robot_status(self, joint_positions: List[float],
                           tcp_position: Dict[str, float],
                           tcp_orientation: Dict[str, float],
                           operational_status: str = "idle") -> Message:
        """构建机器人状态消息"""
        payload = {
            "robot_id": self.client_id,
            "connection_status": "connected",
            "operational_status": operational_status,
            "current_state": {
                "joint_positions": joint_positions,
                "joint_velocities": [0.0] * len(joint_positions),
                "tcp_position": tcp_position,
                "tcp_orientation": tcp_orientation
            },
            "gripper_state": {
                "position": 0.0,
                "force": 0.0,
                "object_detected": False
            },
            "error_state": {
                "has_error": False,
                "error_code": None,
                "error_message": None
            }
        }
        return Message.create(MessageType.ROBOT_STATUS, payload, self.client_id)
    
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
        msg = Message.create(MessageType.ERROR, payload, self.client_id)
        if request_id:
            msg.metadata = Metadata(request_id=request_id)
        return msg
```

### 4.3 消息路由器 (`protocol/message_router.py`)

```python
from typing import Dict, Callable, Any
from .message import MessageType

class MessageRouter:
    """消息路由器 - 根据消息类型分发到对应处理器"""
    
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
    
    def register_handler(self, msg_type: MessageType, handler: Callable):
        """注册消息处理器"""
        self._handlers[msg_type.value] = handler
    
    def route(self, message: Dict[str, Any]) -> bool:
        """路由消息到对应处理器"""
        msg_type = message.get("type")
        if msg_type in self._handlers:
            try:
                self._handlers[msg_type](message)
                return True
            except Exception as e:
                print(f"处理消息 {msg_type} 时出错: {e}")
                return False
        else:
            print(f"未知消息类型: {msg_type}")
            return False
    
    def get_supported_types(self) -> list:
        """获取支持的消息类型列表"""
        return list(self._handlers.keys())
```

### 4.4 指令执行器 (`command/command_executor.py`)

```python
import bpy
import math
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    command_id: str
    message: str = ""
    current_state: Optional[Dict] = None

class CommandExecutor:
    """指令执行器 - 执行统一格式的运动指令"""
    
    def __init__(self, armature_name: str = "Armature"):
        self.armature_name = armature_name
        self._joint_names = [f"axis_{i}" for i in range(1, 7)]
    
    def execute(self, message: Dict[str, Any]) -> ExecutionResult:
        """执行指令消息"""
        msg_type = message.get("type")
        payload = message.get("payload", {})
        command_id = payload.get("command_id", "unknown")
        
        if msg_type == "motion_command":
            return self._execute_motion(command_id, payload)
        elif msg_type == "grasp_command":
            return self._execute_grasp(command_id, payload)
        elif msg_type == "system_command":
            return self._execute_system(command_id, payload)
        else:
            return ExecutionResult(
                success=False,
                command_id=command_id,
                message=f"不支持的指令类型: {msg_type}"
            )
    
    def _execute_motion(self, command_id: str, payload: Dict) -> ExecutionResult:
        """执行运动指令"""
        command_type = payload.get("command_type")
        motion_data = payload.get("motion_data", {})
        
        if command_type == "move_joint":
            return self._move_joint(command_id, motion_data)
        elif command_type == "move_cartesian":
            return self._move_cartesian(command_id, motion_data)
        elif command_type == "move_path":
            return self._move_path(command_id, motion_data)
        else:
            return ExecutionResult(
                success=False,
                command_id=command_id,
                message=f"不支持的运动类型: {command_type}"
            )
    
    def _move_joint(self, command_id: str, motion_data: Dict) -> ExecutionResult:
        """关节空间运动"""
        joint_angles = motion_data.get("joint_angles", [])
        joint_names = motion_data.get("joint_names", self._joint_names)
        
        # 获取骨架
        armature = bpy.data.objects.get(self.armature_name)
        if not armature:
            return ExecutionResult(
                success=False,
                command_id=command_id,
                message=f"未找到骨架: {self.armature_name}"
            )
        
        # 设置各关节角度
        for i, (name, angle) in enumerate(zip(joint_names, joint_angles)):
            bone = armature.pose.bones.get(name)
            if bone:
                # 角度已经是弧度
                bone.rotation_euler[1] = angle  # Y轴旋转
            else:
                print(f"警告: 未找到骨骼 {name}")
        
        # 更新视图
        bpy.context.view_layer.update()
        
        return ExecutionResult(
            success=True,
            command_id=command_id,
            message="关节运动执行成功",
            current_state={"joint_positions": joint_angles}
        )
    
    def _move_cartesian(self, command_id: str, motion_data: Dict) -> ExecutionResult:
        """笛卡尔空间运动 - 需要逆运动学"""
        # TODO: 实现逆运动学计算
        position = motion_data.get("position", {})
        orientation = motion_data.get("orientation", {})
        
        return ExecutionResult(
            success=False,
            command_id=command_id,
            message="笛卡尔运动暂未实现"
        )
    
    def _move_path(self, command_id: str, motion_data: Dict) -> ExecutionResult:
        """路径运动"""
        waypoints = motion_data.get("waypoints", [])
        # TODO: 实现路径运动
        return ExecutionResult(
            success=False,
            command_id=command_id,
            message="路径运动暂未实现"
        )
    
    def _execute_grasp(self, command_id: str, payload: Dict) -> ExecutionResult:
        """执行抓取指令"""
        grasp_data = payload.get("grasp_data", {})
        action = grasp_data.get("action")  # open, close, grasp, release
        
        # TODO: 实现夹爪控制
        return ExecutionResult(
            success=True,
            command_id=command_id,
            message=f"夹爪动作 {action} 执行成功"
        )
    
    def _execute_system(self, command_id: str, payload: Dict) -> ExecutionResult:
        """执行系统指令"""
        system_data = payload.get("system_data", {})
        action = system_data.get("action")
        
        if action == "init":
            return self._init_robot(command_id)
        elif action == "reset":
            return self._reset_robot(command_id)
        elif action == "get_status":
            return self._get_status(command_id)
        else:
            return ExecutionResult(
                success=False,
                command_id=command_id,
                message=f"不支持的系统指令: {action}"
            )
    
    def _init_robot(self, command_id: str) -> ExecutionResult:
        """初始化机器人（归零位）"""
        zero_angles = [0.0] * 6
        return self._move_joint(command_id, {"joint_angles": zero_angles})
    
    def _reset_robot(self, command_id: str) -> ExecutionResult:
        """复位机器人"""
        return self._init_robot(command_id)
    
    def _get_status(self, command_id: str) -> ExecutionResult:
        """获取机器人状态"""
        armature = bpy.data.objects.get(self.armature_name)
        if not armature:
            return ExecutionResult(
                success=False,
                command_id=command_id,
                message=f"未找到骨架: {self.armature_name}"
            )
        
        joint_positions = []
        for name in self._joint_names:
            bone = armature.pose.bones.get(name)
            if bone:
                joint_positions.append(bone.rotation_euler[1])
            else:
                joint_positions.append(0.0)
        
        return ExecutionResult(
            success=True,
            command_id=command_id,
            message="状态获取成功",
            current_state={"joint_positions": joint_positions}
        )
```

### 4.5 WebSocket 管理器 (`transport/websocket_manager.py`)

```python
import json
import threading
import time
import uuid
import websocket
from typing import Optional, Callable, Dict, Any

from ..protocol.message_builder import MessageBuilder
from ..protocol.message_router import MessageRouter
from ..protocol.message import MessageType

class WebSocketManager:
    """WebSocket 连接管理器"""
    
    # 客户端能力列表
    CAPABILITIES = ["motion_execute", "image_capture", "status_report"]
    
    def __init__(self):
        self.ws: Optional[websocket.WebSocketApp] = None
        self.thread: Optional[threading.Thread] = None
        self.connected = False
        
        # 连接配置
        self.ip_address = "localhost"
        self.port = 5001
        
        # 客户端标识
        self.client_id = f"blender_{uuid.uuid4().hex[:8]}"
        self.session_id: Optional[str] = None
        
        # 心跳配置
        self.heartbeat_interval = 30  # 秒
        self.heartbeat_sequence = 0
        self._heartbeat_timer: Optional[threading.Timer] = None
        
        # 消息处理
        self.message_builder = MessageBuilder(self.client_id)
        self.message_router = MessageRouter()
        
        # 回调函数
        self._on_connected_callback: Optional[Callable] = None
        self._on_disconnected_callback: Optional[Callable] = None
    
    def set_callbacks(self, on_connected: Callable = None, 
                      on_disconnected: Callable = None):
        """设置连接状态回调"""
        self._on_connected_callback = on_connected
        self._on_disconnected_callback = on_disconnected
    
    def connect(self):
        """建立 WebSocket 连接"""
        if self.connected:
            return
        
        url = f"ws://{self.ip_address}:{self.port}"
        print(f"正在连接到 {url}...")
        
        self.ws = websocket.WebSocketApp(
            url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        
        self.thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self.thread.start()
    
    def disconnect(self):
        """断开 WebSocket 连接"""
        if not self.connected:
            return
        
        print("正在断开 WebSocket 连接...")
        self._stop_heartbeat()
        
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                print(f"关闭连接时出错: {e}")
        
        self.ws = None
        self.thread = None
        self.connected = False
        self.session_id = None
        
        if self._on_disconnected_callback:
            self._on_disconnected_callback()
        
        print("WebSocket 连接已断开")
    
    def send_message(self, message: Dict[str, Any]) -> bool:
        """发送消息"""
        if not self.connected or not self.ws:
            print("WebSocket 未连接")
            return False
        
        try:
            json_str = json.dumps(message)
            self.ws.send(json_str)
            return True
        except Exception as e:
            print(f"发送消息失败: {e}")
            return False
    
    def _on_open(self, ws):
        """连接建立回调"""
        print("WebSocket 连接已建立")
        self.connected = True
        
        # 发送注册消息
        self._send_register()
        
        if self._on_connected_callback:
            self._on_connected_callback()
    
    def _on_message(self, ws, message: str):
        """消息接收回调"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            # 处理注册确认
            if msg_type == "register_ack":
                self._handle_register_ack(data)
                return
            
            # 处理心跳响应
            if msg_type == "heartbeat_ack":
                return
            
            # 路由到对应处理器
            self.message_router.route(data)
            
        except json.JSONDecodeError as e:
            print(f"消息解析失败: {e}")
        except Exception as e:
            print(f"处理消息时出错: {e}")
    
    def _on_error(self, ws, error):
        """错误回调"""
        print(f"WebSocket 错误: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """连接关闭回调"""
        print(f"WebSocket 连接关闭: {close_status_code} - {close_msg}")
        self._stop_heartbeat()
        self.connected = False
        
        if self._on_disconnected_callback:
            self._on_disconnected_callback()
    
    def _send_register(self):
        """发送客户端注册消息"""
        import bpy
        device_info = {
            "name": "Blender Virtual Robot",
            "blender_version": bpy.app.version_string
        }
        
        msg = self.message_builder.build_register(
            capabilities=self.CAPABILITIES,
            device_info=device_info
        )
        self.send_message(msg.to_dict())
    
    def _handle_register_ack(self, data: Dict):
        """处理注册确认"""
        payload = data.get("payload", {})
        if payload.get("status") == "success":
            self.session_id = payload.get("session_id")
            config = payload.get("config", {})
            self.heartbeat_interval = config.get("heartbeat_interval", 30000) / 1000
            
            print(f"注册成功，session_id: {self.session_id}")
            
            # 启动心跳
            self._start_heartbeat()
        else:
            print(f"注册失败: {payload}")
    
    def _start_heartbeat(self):
        """启动心跳"""
        self._send_heartbeat()
    
    def _send_heartbeat(self):
        """发送心跳"""
        if not self.connected:
            return
        
        self.heartbeat_sequence += 1
        msg = self.message_builder.build_heartbeat(self.heartbeat_sequence)
        self.send_message(msg.to_dict())
        
        # 设置下次心跳
        self._heartbeat_timer = threading.Timer(
            self.heartbeat_interval, 
            self._send_heartbeat
        )
        self._heartbeat_timer.daemon = True
        self._heartbeat_timer.start()
    
    def _stop_heartbeat(self):
        """停止心跳"""
        if self._heartbeat_timer:
            self._heartbeat_timer.cancel()
            self._heartbeat_timer = None


# 全局单例
_websocket_manager_instance: Optional[WebSocketManager] = None

def get_websocket_manager() -> WebSocketManager:
    """获取 WebSocket 管理器单例"""
    global _websocket_manager_instance
    if _websocket_manager_instance is None:
        _websocket_manager_instance = WebSocketManager()
    return _websocket_manager_instance

def cleanup_websocket_manager():
    """清理 WebSocket 管理器"""
    global _websocket_manager_instance
    if _websocket_manager_instance:
        _websocket_manager_instance.disconnect()
        _websocket_manager_instance = None
```

---

## 5. 消息类型支持矩阵

### 5.1 接收消息（服务端 → Blender）

| 消息类型 | 说明 | 优先级 | 状态 |
|---------|------|--------|------|
| `register_ack` | 注册确认 | 高 | 待实现 |
| `heartbeat_ack` | 心跳响应 | 高 | 待实现 |
| `error` | 错误消息 | 高 | 待实现 |
| `motion_command` | 运动指令 | 高 | 待实现 |
| `grasp_command` | 抓取指令 | 中 | 待实现 |
| `system_command` | 系统指令 | 高 | 待实现 |
| `image_request` | 图像请求 | 中 | 待实现 |

### 5.2 发送消息（Blender → 服务端）

| 消息类型 | 说明 | 优先级 | 状态 |
|---------|------|--------|------|
| `register` | 客户端注册 | 高 | 待实现 |
| `heartbeat` | 心跳 | 高 | 待实现 |
| `image_frame` | 图像帧 | 中 | 待实现 |
| `command_ack` | 指令确认 | 高 | 待实现 |
| `execution_status` | 执行状态 | 高 | 待实现 |
| `robot_status` | 机器人状态 | 中 | 待实现 |
| `error` | 错误消息 | 高 | 待实现 |

---

## 6. 指令类型支持

### 6.1 运动指令 (`motion_command`)

| 指令类型 | 说明 | 优先级 | 状态 |
|---------|------|--------|------|
| `move_joint` | 关节空间运动 | 高 | 待实现 |
| `move_cartesian` | 笛卡尔空间运动 | 中 | 待实现 |
| `move_path` | 路径运动 | 低 | 待实现 |

### 6.2 抓取指令 (`grasp_command`)

| 动作 | 说明 | 优先级 | 状态 |
|------|------|--------|------|
| `open` | 张开夹爪 | 中 | 待实现 |
| `close` | 闭合夹爪 | 中 | 待实现 |
| `grasp` | 执行抓取 | 中 | 待实现 |
| `release` | 释放物体 | 中 | 待实现 |

### 6.3 系统指令 (`system_command`)

| 动作 | 说明 | 优先级 | 状态 |
|------|------|--------|------|
| `init` | 初始化（归零位） | 高 | 待实现 |
| `reset` | 复位 | 高 | 待实现 |
| `get_status` | 获取状态 | 高 | 待实现 |
| `enable` | 使能 | 低 | 待实现 |
| `disable` | 去使能 | 低 | 待实现 |

---

## 7. 重构计划

### 7.1 第一阶段：协议层实现（1-2天）

1. [ ] 创建 `protocol/` 目录结构
2. [ ] 实现 `message.py` - 消息数据结构
3. [ ] 实现 `message_builder.py` - 消息构建器
4. [ ] 实现 `message_parser.py` - 消息解析器
5. [ ] 实现 `message_router.py` - 消息路由器

### 7.2 第二阶段：传输层重构（1天）

1. [ ] 重构 `websocket_manager.py`
2. [ ] 添加客户端注册流程
3. [ ] 实现心跳机制
4. [ ] 添加自动重连功能

### 7.3 第三阶段：指令层实现（1-2天）

1. [ ] 创建 `command/` 目录结构
2. [ ] 重构 `command_executor.py`
3. [ ] 实现 `command_queue.py` - 指令队列
4. [ ] 支持所有运动指令类型

### 7.4 第四阶段：核心层实现（1-2天）

1. [ ] 实现 `robot_controller.py` - 骨骼驱动
2. [ ] 实现 `image_capture.py` - 图像采集
3. [ ] 实现 `state_manager.py` - 状态管理

### 7.5 第五阶段：UI 层更新（1天）

1. [ ] 更新面板显示
2. [ ] 添加状态显示面板
3. [ ] 更新操作符

---

## 8. 兼容性说明

### 8.1 向后兼容

重构后的插件将**不再兼容**旧的消息格式（`{"action": 0/1, ...}`）。服务端需要同步升级到统一通信协议。

### 8.2 Blender 版本

- 最低支持版本：Blender 3.5.0
- 推荐版本：Blender 4.0+

### 8.3 Python 依赖

- `websocket-client` - WebSocket 客户端库

---

## 9. 总结

本设计文档定义了 `robotic_twin` Blender 插件的重构方案，主要改进包括：

1. **完全兼容统一通信协议** - 实现标准的消息格式和所有消息类型
2. **分层架构设计** - 协议层、指令层、核心层、传输层清晰分离
3. **健壮的连接管理** - 客户端注册、心跳维护、错误处理
4. **完整的状态反馈** - 指令确认、执行状态、机器人状态上报
5. **可扩展性** - 便于添加新的指令类型和功能
