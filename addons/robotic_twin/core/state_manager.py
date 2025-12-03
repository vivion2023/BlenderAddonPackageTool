# 状态管理器 - 管理插件运行状态
from typing import Optional, Any, Callable, List
from enum import Enum
from dataclasses import dataclass
import time


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    REGISTERED = "registered"
    ERROR = "error"


class RobotState(Enum):
    IDLE = "idle"
    MOVING = "moving"
    EXECUTING = "executing"
    ERROR = "error"


@dataclass
class StatusInfo:
    connection_state: ConnectionState = ConnectionState.DISCONNECTED
    robot_state: RobotState = RobotState.IDLE
    last_error: Optional[str] = None
    message_count_sent: int = 0
    message_count_received: int = 0


class StateManager:
    """状态管理器"""
    
    def __init__(self):
        self._status = StatusInfo()
        self._listeners: List[Callable[[str, Any, Any], None]] = []
    
    def get_connection_state(self) -> ConnectionState:
        return self._status.connection_state
    
    def get_robot_state(self) -> RobotState:
        return self._status.robot_state
    
    def get_last_error(self) -> Optional[str]:
        return self._status.last_error
    
    def get_status_info(self) -> StatusInfo:
        return self._status
    
    def is_connected(self) -> bool:
        return self._status.connection_state in [ConnectionState.CONNECTED, ConnectionState.REGISTERED]
    
    def is_registered(self) -> bool:
        return self._status.connection_state == ConnectionState.REGISTERED
    
    def set_connection_state(self, state: ConnectionState):
        self._status.connection_state = state
    
    def set_robot_state(self, state: RobotState):
        self._status.robot_state = state
    
    def set_error(self, error: str):
        self._status.last_error = error
    
    def clear_error(self):
        self._status.last_error = None
    
    def increment_sent(self):
        self._status.message_count_sent += 1
    
    def increment_received(self):
        self._status.message_count_received += 1
    
    def on_connected(self):
        self.set_connection_state(ConnectionState.CONNECTED)
        self.clear_error()
    
    def on_registered(self):
        self.set_connection_state(ConnectionState.REGISTERED)
    
    def on_disconnected(self):
        self.set_connection_state(ConnectionState.DISCONNECTED)
        self.set_robot_state(RobotState.IDLE)
    
    def on_connection_error(self, error: str):
        self.set_connection_state(ConnectionState.ERROR)
        self.set_error(error)
    
    def get_status_summary(self) -> str:
        return (
            f"连接: {self._status.connection_state.value}, "
            f"机器人: {self._status.robot_state.value}, "
            f"发送: {self._status.message_count_sent}, "
            f"接收: {self._status.message_count_received}"
        )
