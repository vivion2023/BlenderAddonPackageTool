# 指令处理器 - 连接消息路由与指令执行
from typing import Dict, Any

from ..protocol.message import MessageType, ExecutionStatus, CommandAckStatus
from ..protocol.message_builder import MessageBuilder
from ..protocol.message_router import MessageRouter
from .command_executor import CommandExecutor, ExecutionResult


class CommandHandler:
    """指令处理器 - 连接消息路由与指令执行"""
    
    def __init__(self, message_router: MessageRouter, 
                 message_builder: MessageBuilder,
                 send_callback=None):
        self.router = message_router
        self.builder = message_builder
        self.executor = CommandExecutor()
        self._send_callback = send_callback
        
        self._register_handlers()
    
    def _register_handlers(self):
        """注册指令消息处理器"""
        self.router.register_handler(MessageType.MOTION_COMMAND, self._handle_motion_command)
        self.router.register_handler(MessageType.GRASP_COMMAND, self._handle_grasp_command)
        self.router.register_handler(MessageType.SYSTEM_COMMAND, self._handle_system_command)
    
    def set_send_callback(self, callback):
        self._send_callback = callback
    
    def set_executor(self, executor: CommandExecutor):
        self.executor = executor
    
    def _handle_motion_command(self, message: Dict[str, Any]):
        self._process_command(message)
    
    def _handle_grasp_command(self, message: Dict[str, Any]):
        self._process_command(message)
    
    def _handle_system_command(self, message: Dict[str, Any]):
        self._process_command(message)
    
    def _process_command(self, message: Dict[str, Any]):
        """处理指令的通用流程"""
        payload = message.get("payload", {})
        command_id = payload.get("command_id", "unknown")
        request_id = message.get("message_id")
        
        # 发送确认
        self._send_command_ack(command_id, CommandAckStatus.ACCEPTED, "指令已接收", request_id)
        
        # 执行
        result = self.executor.execute(message)
        
        # 发送状态
        if result.success:
            self._send_execution_status(command_id, ExecutionStatus.COMPLETED, {"percentage": 100}, result.current_state)
        else:
            self._send_execution_status(command_id, ExecutionStatus.FAILED, {"percentage": 0, "error": result.message}, result.current_state)
    
    def _send_command_ack(self, command_id: str, status: CommandAckStatus, message: str = "", request_id: str = None):
        if not self._send_callback:
            return
        msg = self.builder.build_command_ack(command_id, status, message, request_id)
        self._send_callback(msg.to_dict())
    
    def _send_execution_status(self, command_id: str, status: ExecutionStatus, progress: Dict = None, current_state: Dict = None):
        if not self._send_callback:
            return
        msg = self.builder.build_execution_status(command_id, status, progress, current_state)
        self._send_callback(msg.to_dict())
    
    def send_robot_status(self):
        """主动发送机器人状态"""
        if not self._send_callback:
            return
        joint_positions = self.executor.get_joint_positions()
        status = self.executor.get_current_status()
        msg = self.builder.build_robot_status(joint_positions=joint_positions, operational_status=status)
        self._send_callback(msg.to_dict())
