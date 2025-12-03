# 应用主入口 - 整合所有模块
from typing import Optional, Dict, Any

from ..protocol.message import MessageType
from ..protocol.message_builder import MessageBuilder
from ..protocol.message_router import MessageRouter
from ..transport.websocket_manager import WebSocketManager, get_websocket_manager
from ..command.command_executor import CommandExecutor
from ..command.command_handler import CommandHandler
from .robot_controller import RobotController
from .state_manager import StateManager, ConnectionState


class RoboticTwinApp:
    """应用主入口"""
    
    def __init__(self):
        self.state_manager = StateManager()
        self.robot_controller = RobotController()
        self.ws_manager: Optional[WebSocketManager] = None
        self.command_handler: Optional[CommandHandler] = None
        self._initialized = False
    
    def initialize(self):
        if self._initialized:
            return
        
        self.ws_manager = get_websocket_manager()
        self.ws_manager.set_callbacks(
            on_connected=self._on_connected,
            on_disconnected=self._on_disconnected,
            on_error=self._on_error
        )
        
        self.command_handler = CommandHandler(
            message_router=self.ws_manager.message_router,
            message_builder=self.ws_manager.message_builder,
            send_callback=self._send_message
        )
        
        self.command_handler.executor.set_armature_name(self.robot_controller.armature_name)
        self.command_handler.executor.set_joint_names(self.robot_controller.get_joint_names())
        
        self._initialized = True
        print("RoboticTwinApp initialized")
    
    def cleanup(self):
        if self.ws_manager:
            self.ws_manager.disconnect()
        self._initialized = False
    
    def connect(self, ip_address: str = None, port: int = None):
        if not self._initialized:
            self.initialize()
        
        if ip_address:
            self.ws_manager.ip_address = ip_address
        if port:
            self.ws_manager.port = port
        
        self.state_manager.set_connection_state(ConnectionState.CONNECTING)
        self.ws_manager.connect()
    
    def disconnect(self):
        if self.ws_manager:
            self.ws_manager.disconnect()
    
    def is_connected(self) -> bool:
        return self.ws_manager.is_connected() if self.ws_manager else False
    
    def is_registered(self) -> bool:
        return self.ws_manager.is_registered() if self.ws_manager else False
    
    def get_joint_angles(self):
        return self.robot_controller.get_joint_angles()
    
    def get_connection_state(self) -> ConnectionState:
        return self.state_manager.get_connection_state()
    
    def get_status_summary(self) -> str:
        return self.state_manager.get_status_summary()
    
    def _send_message(self, data: Dict[str, Any]) -> bool:
        if not self.ws_manager:
            return False
        success = self.ws_manager.send_dict(data)
        if success:
            self.state_manager.increment_sent()
        return success
    
    def send_robot_status(self):
        if self.command_handler:
            self.command_handler.send_robot_status()
    
    def _on_connected(self):
        self.state_manager.on_connected()
    
    def _on_disconnected(self):
        self.state_manager.on_disconnected()
    
    def _on_error(self, error: str):
        self.state_manager.on_connection_error(error)
    
    def set_armature_name(self, name: str):
        self.robot_controller.set_armature_name(name)
        if self.command_handler:
            self.command_handler.executor.set_armature_name(name)
    
    def set_server(self, ip_address: str, port: int):
        if self.ws_manager:
            self.ws_manager.set_server(ip_address, port)


_app_instance: Optional[RoboticTwinApp] = None

def get_app() -> RoboticTwinApp:
    global _app_instance
    if _app_instance is None:
        _app_instance = RoboticTwinApp()
        _app_instance.initialize()
    return _app_instance

def cleanup_app():
    global _app_instance
    if _app_instance:
        _app_instance.cleanup()
        _app_instance = None
