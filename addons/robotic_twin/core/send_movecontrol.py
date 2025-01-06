import json
from ..core.websocket_manager import get_websocket_manager
import math

class MoveControl:
    @staticmethod
    def send_move_command(axis_values):
        """
        发送运动命令
        命令格式: {"action": 1, "axis_1": 1, "axis_2": 2, "axis_3": 3, "axis_4": 4, "axis_5": 5, "axis_6": 6}
        """
        ws_manager = get_websocket_manager()
        if not ws_manager.connected:
            print("WebSocket connection not established")
            return False
            
        command = {
            "action": 1,
            "axis_1": axis_values[0],
            "axis_2": axis_values[1],
            "axis_3": axis_values[2],
            "axis_4": axis_values[3],
            "axis_5": axis_values[4],
            "axis_6": axis_values[5]
        }

        # 如果需要发送度数而不是弧度，可以这样转换：
        command = {
            "action": 1,
            "axis_1": math.degrees(axis_values[0]),
            "axis_2": math.degrees(axis_values[1]),
            "axis_3": math.degrees(axis_values[2]),
            "axis_4": math.degrees(axis_values[3]),
            "axis_5": math.degrees(axis_values[4]),
            "axis_6": math.degrees(axis_values[5])
        }

        print(f"Sending move command: {command}")
        return ws_manager.send_message(json.dumps(command))