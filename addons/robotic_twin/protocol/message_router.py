# 消息路由器 - 根据消息类型分发到对应处理器
from typing import Dict, Callable, Any, List, Optional

from .message import MessageType


class MessageRouter:
    """消息路由器 - 根据消息类型分发到对应处理器"""
    
    def __init__(self):
        self._handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        self._default_handler: Optional[Callable[[Dict[str, Any]], None]] = None
    
    def register_handler(self, msg_type: MessageType, handler: Callable[[Dict[str, Any]], None]):
        """注册消息处理器"""
        type_str = msg_type.value if isinstance(msg_type, MessageType) else msg_type
        self._handlers[type_str] = handler
    
    def register_handlers(self, handlers: Dict[MessageType, Callable[[Dict[str, Any]], None]]):
        """批量注册消息处理器"""
        for msg_type, handler in handlers.items():
            self.register_handler(msg_type, handler)
    
    def set_default_handler(self, handler: Callable[[Dict[str, Any]], None]):
        """设置默认处理器"""
        self._default_handler = handler
    
    def unregister_handler(self, msg_type: MessageType):
        """取消注册消息处理器"""
        type_str = msg_type.value if isinstance(msg_type, MessageType) else msg_type
        if type_str in self._handlers:
            del self._handlers[type_str]
    
    def route(self, message: Dict[str, Any]) -> bool:
        """路由消息到对应处理器"""
        msg_type = message.get("type")
        
        if msg_type in self._handlers:
            try:
                self._handlers[msg_type](message)
                return True
            except Exception as e:
                print(f"Error handling message {msg_type}: {e}")
                return False
        elif self._default_handler:
            try:
                self._default_handler(message)
                return True
            except Exception as e:
                print(f"Default handler error for message {msg_type}: {e}")
                return False
        else:
            print(f"Unregistered message type: {msg_type}")
            return False
    
    def has_handler(self, msg_type: MessageType) -> bool:
        """检查是否已注册指定类型的处理器"""
        type_str = msg_type.value if isinstance(msg_type, MessageType) else msg_type
        return type_str in self._handlers
    
    def get_supported_types(self) -> List[str]:
        """获取已注册的消息类型列表"""
        return list(self._handlers.keys())
    
    def clear_handlers(self):
        """清除所有处理器"""
        self._handlers.clear()
        self._default_handler = None
