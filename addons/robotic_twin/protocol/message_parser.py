# 消息解析器 - 负责解析接收到的消息
import json
from typing import Dict, Any, Optional, Tuple

from .message import Message, MessageType


class MessageParser:
    """消息解析器 - 负责解析和验证接收到的消息"""
    
    REQUIRED_FIELDS = ["message_id", "type", "sender", "timestamp", "payload"]
    REQUIRED_SENDER_FIELDS = ["client_id", "client_type"]
    
    def __init__(self):
        pass
    
    def parse(self, raw_message: str) -> Tuple[Optional[Message], Optional[str]]:
        """解析原始消息字符串"""
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError as e:
            return None, f"JSON 解析失败: {e}"
        
        error = self._validate(data)
        if error:
            return None, error
        
        try:
            message = Message.from_dict(data)
            return message, None
        except Exception as e:
            return None, f"消息对象创建失败: {e}"
    
    def parse_dict(self, data: Dict[str, Any]) -> Tuple[Optional[Message], Optional[str]]:
        """解析字典格式的消息"""
        error = self._validate(data)
        if error:
            return None, error
        
        try:
            message = Message.from_dict(data)
            return message, None
        except Exception as e:
            return None, f"消息对象创建失败: {e}"
    
    def _validate(self, data: Dict[str, Any]) -> Optional[str]:
        """验证消息格式"""
        for field in self.REQUIRED_FIELDS:
            if field not in data:
                return f"缺少必填字段: {field}"
        
        sender = data.get("sender", {})
        for field in self.REQUIRED_SENDER_FIELDS:
            if field not in sender:
                return f"sender 缺少必填字段: {field}"
        
        msg_type = data.get("type")
        if not self._is_valid_message_type(msg_type):
            return f"未知的消息类型: {msg_type}"
        
        return None
    
    def _is_valid_message_type(self, msg_type: str) -> bool:
        """检查消息类型是否有效"""
        try:
            MessageType(msg_type)
            return True
        except ValueError:
            return False
    
    def get_message_type(self, data: Dict[str, Any]) -> Optional[MessageType]:
        """获取消息类型枚举"""
        msg_type = data.get("type")
        try:
            return MessageType(msg_type)
        except ValueError:
            return None
