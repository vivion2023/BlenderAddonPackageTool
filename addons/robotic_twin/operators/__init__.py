from .connection_operators import WS_OT_Connect, WS_OT_Disconnect, WS_OT_SendStatus
from .robot_operators import (
    ROBOT_OT_SetJoints,
    ROBOT_OT_ResetToZero,
    ROBOT_OT_SendMoveCommand,
    ROBOT_OT_BindAxis,
    ROBOT_OT_UnbindAxis,
    ROBOT_OT_SendImage
)
from .detection_operators import WS_OT_DetectImage, ROBOT_OT_RealtimeDetection

classes = (
    WS_OT_Connect,
    WS_OT_Disconnect,
    WS_OT_SendStatus,
    ROBOT_OT_SetJoints,
    ROBOT_OT_ResetToZero,
    ROBOT_OT_SendMoveCommand,
    ROBOT_OT_BindAxis,
    ROBOT_OT_UnbindAxis,
    ROBOT_OT_SendImage,
    WS_OT_DetectImage,
    ROBOT_OT_RealtimeDetection,
)
