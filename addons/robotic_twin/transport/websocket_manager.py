# WebSocket 连接管理器
import json
import threading
import time
import uuid
import websocket
from typing import Optional, Callable, Dict, Any

from ..protocol.message import Message, MessageType
from ..protocol.message_builder import MessageBuilder
from ..protocol.message_parser import MessageParser
from ..protocol.message_router import MessageRouter


class WebSocketManager:
    """WebSocket 连接管理器"""
    
    CAPABILITIES = ["motion_execute", "image_capture", "status_report"]
    
    def __init__(self):
        self.ws: Optional[websocket.WebSocketApp] = None
        self.thread: Optional[threading.Thread] = None
        self.connected = False
        
        self.ip_address = "localhost"
        self.port = 5001
        
        self.client_id = f"blender_{uuid.uuid4().hex[:8]}"
        self.session_id: Optional[str] = None
        
        self.heartbeat_interval = 30
        self.heartbeat_sequence = 0
        self._heartbeat_timer: Optional[threading.Timer] = None
        self._heartbeat_enabled = True
        
        self.message_builder = MessageBuilder(self.client_id)
        self.message_parser = MessageParser()
        self.message_router = MessageRouter()
        
        self._on_connected_callback: Optional[Callable[[], None]] = None
        self._on_disconnected_callback: Optional[Callable[[], None]] = None
        self._on_error_callback: Optional[Callable[[str], None]] = None
        
        self._registered = False
    
    def set_server(self, ip_address: str, port: int):
        """设置服务器地址"""
        self.ip_address = ip_address
        self.port = port
    
    def set_callbacks(self, on_connected: Callable[[], None] = None, 
                      on_disconnected: Callable[[], None] = None,
                      on_error: Callable[[str], None] = None):
        """设置连接状态回调"""
        self._on_connected_callback = on_connected
        self._on_disconnected_callback = on_disconnected
        self._on_error_callback = on_error
    
    def connect(self):
        """建立 WebSocket 连接"""
        if self.connected:
            return
        
        url = f"ws://{self.ip_address}:{self.port}"
        print(f"Connecting to {url}...")
        
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
        
        print("Disconnecting WebSocket...")
        self._stop_heartbeat()
        
        if self.ws:
            try:
                self.ws.close()
                if self.thread and self.thread.is_alive():
                    self.thread.join(timeout=1)
                if hasattr(self.ws, 'sock') and self.ws.sock:
                    self.ws.sock.close()
            except Exception as e:
                print(f"Error closing connection: {e}")
        
        self._reset_state()
        
        if self._on_disconnected_callback:
            self._on_disconnected_callback()
        
        print("WebSocket disconnected")
    
    def _reset_state(self):
        """重置连接状态"""
        self.ws = None
        self.thread = None
        self.connected = False
        self.session_id = None
        self._registered = False
        self.heartbeat_sequence = 0
    
    def send_message(self, message: Message) -> bool:
        """发送 Message 对象"""
        return self.send_dict(message.to_dict())
    
    def send_dict(self, data: Dict[str, Any]) -> bool:
        """发送字典格式消息"""
        if not self.connected or not self.ws:
            print("WebSocket not connected")
            return False
        
        try:
            json_str = json.dumps(data, ensure_ascii=False)
            self.ws.send(json_str)
            return True
        except Exception as e:
            print(f"Failed to send message: {e}")
            return False
    
    def send_raw(self, message: str) -> bool:
        """发送原始字符串消息"""
        if not self.connected or not self.ws:
            return False
        
        try:
            self.ws.send(message)
            return True
        except Exception as e:
            print(f"Failed to send message: {e}")
            return False
    
    def _on_open(self, ws):
        """连接建立回调"""
        print("WebSocket connected")
        self.connected = True
        self._send_register()
        
        if self._on_connected_callback:
            self._on_connected_callback()
    
    def _on_message(self, ws, message: str):
        """消息接收回调"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == MessageType.REGISTER_ACK.value:
                self._handle_register_ack(data)
                return
            
            if msg_type == MessageType.HEARTBEAT_ACK.value:
                return
            
            if not self.message_router.route(data):
                print(f"Message not handled: {msg_type}")
            
        except json.JSONDecodeError as e:
            print(f"Message parse failed: {e}")
        except Exception as e:
            print(f"Error processing message: {e}")
    
    def _on_error(self, ws, error):
        """错误回调"""
        print(f"WebSocket error: {error}")
        if self._on_error_callback:
            self._on_error_callback(str(error))
    
    def _on_close(self, ws, close_status_code, close_msg):
        """连接关闭回调"""
        print(f"WebSocket closed: {close_status_code} - {close_msg}")
        self._stop_heartbeat()
        self.connected = False
        self._registered = False
        
        if self._on_disconnected_callback:
            self._on_disconnected_callback()
    
    def _send_register(self):
        """发送客户端注册消息"""
        try:
            import bpy
            blender_version = bpy.app.version_string
        except:
            blender_version = "unknown"
        
        device_info = {
            "name": "Blender Virtual Robot",
            "blender_version": blender_version
        }
        
        msg = self.message_builder.build_register(
            capabilities=self.CAPABILITIES,
            device_info=device_info
        )
        self.send_message(msg)
        print(f"Register message sent, client_id: {self.client_id}")
    
    def _handle_register_ack(self, data: Dict[str, Any]):
        """处理注册确认"""
        payload = data.get("payload", {})
        status = payload.get("status")
        
        if status == "success":
            self.session_id = payload.get("session_id")
            config = payload.get("config", {})
            heartbeat_ms = config.get("heartbeat_interval", 30000)
            self.heartbeat_interval = heartbeat_ms / 1000
            
            self._registered = True
            print(f"Registration successful, session_id: {self.session_id}")
            
            if self._heartbeat_enabled:
                self._start_heartbeat()
        else:
            error_msg = payload.get("message", "Unknown error")
            print(f"Registration failed: {error_msg}")
    
    def _start_heartbeat(self):
        """启动心跳"""
        if not self._heartbeat_enabled:
            return
        self._send_heartbeat()
    
    def _send_heartbeat(self):
        """发送心跳"""
        if not self.connected or not self._heartbeat_enabled:
            return
        
        self.heartbeat_sequence += 1
        msg = self.message_builder.build_heartbeat(self.heartbeat_sequence)
        self.send_message(msg)
        
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
    
    def is_connected(self) -> bool:
        return self.connected
    
    def is_registered(self) -> bool:
        return self._registered
    
    def get_client_id(self) -> str:
        return self.client_id
    
    def get_session_id(self) -> Optional[str]:
        return self.session_id


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
