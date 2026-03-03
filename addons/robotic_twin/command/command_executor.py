# 指令执行器 - 执行统一格式的运动指令（支持关键帧动画）
import bpy
import math
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple

from ..protocol.message import (
    CommandType,
    SystemAction,
    ExecutionStatus,
    OperationalStatus,
)


@dataclass
class ExecutionResult:
    """执行结果"""

    success: bool
    command_id: str
    message: str = ""
    status: ExecutionStatus = ExecutionStatus.COMPLETED
    current_state: Optional[Dict[str, Any]] = None


class CommandExecutor:
    """指令执行器"""

    AXIS_VECTOR_MAP: Dict[str, Tuple[float, float, float]] = {
        "X": (1.0, 0.0, 0.0),
        "Y": (0.0, 1.0, 0.0),
        "Z": (0.0, 0.0, 1.0),
    }
    DEFAULT_MOVE_FRAMES = 24
    DEFAULT_STEP_FRAMES = 12

    def __init__(self, armature_name: str = "Armature"):
        self.armature_name = armature_name
        self._joint_names = [f"axis_{i}" for i in range(1, 7)]
        self._current_status = OperationalStatus.IDLE
        self._playback_token = 0

    def execute(self, message: Dict[str, Any]) -> ExecutionResult:
        """执行指令消息"""
        msg_type = message.get("type")
        payload = message.get("payload", {})
        command_id = payload.get("command_id", "unknown")

        print(f"Executing command: type={msg_type}, command_id={command_id}")

        if msg_type == "model_command":
            return self.execute_model_command(message)
        if msg_type == "motion_command":
            return self._execute_motion(command_id, payload)
        if msg_type == "grasp_command":
            return self._execute_grasp(command_id, payload)
        if msg_type == "system_command":
            return self._execute_system(command_id, payload)

        return ExecutionResult(
            success=False,
            command_id=command_id,
            message=f"Unsupported command type: {msg_type}",
            status=ExecutionStatus.FAILED,
        )

    def execute_model_command(self, message: Dict[str, Any]) -> ExecutionResult:
        """执行下行 model_command。"""
        payload = message.get("payload", {})
        command = payload.get("command", "")
        command_id = self._resolve_model_command_id(message)

        if command == "idle":
            self._current_status = OperationalStatus.IDLE
            return ExecutionResult(
                True,
                command_id,
                "Switched to idle",
                ExecutionStatus.COMPLETED,
                {"operational_status": self._current_status.value},
            )

        if command == "init_bones":
            result = self._animate_joint_motion(
                command_id=command_id,
                target_angles=[0.0] * len(self._joint_names),
                joint_names=self._joint_names,
                duration_frames=self.DEFAULT_MOVE_FRAMES,
            )
            if result.success:
                self._play_frame_range(
                    int(result.current_state.get("frame_start", bpy.context.scene.frame_current)),
                    int(result.current_state.get("frame_end", bpy.context.scene.frame_current)),
                )
            return result

        if command == "execute_grasp_plan":
            return self._execute_grasp_plan(command_id, payload)

        return ExecutionResult(
            False,
            command_id,
            f"Unsupported model command: {command}",
            ExecutionStatus.FAILED,
        )

    def _resolve_model_command_id(self, message: Dict[str, Any]) -> str:
        payload = message.get("payload", {})
        return (
            payload.get("plan_id")
            or payload.get("command_id")
            or message.get("message_id")
            or "unknown"
        )

    def _execute_grasp_plan(self, command_id: str, payload: Dict[str, Any]) -> ExecutionResult:
        """按 sequence.action 分派执行。"""
        sequence = payload.get("sequence", []) or []
        scene = bpy.context.scene
        plan_frame_start = int(scene.frame_current)
        frame_cursor = plan_frame_start
        animated_any = False
        self._current_status = OperationalStatus.EXECUTING

        try:
            for item in sorted(sequence, key=lambda x: x.get("step", 0)):
                step = item.get("step")
                action = str(item.get("action", "")).strip()
                name = str(item.get("name", "")).strip()
                step_frames = self._resolve_duration_frames(item, None, self.DEFAULT_STEP_FRAMES)
                direct_joint_angles = self._extract_joint_angles(item)
                pseudo_joint_angles = []
                if action == "move_cartesian" and not direct_joint_angles:
                    pseudo_joint_angles = self._pseudo_joint_angles_from_pose(item.get("pose", {}))
                self._log_grasp_plan_axes(
                    step=step,
                    action=action,
                    name=name,
                    target_angles=(direct_joint_angles or pseudo_joint_angles),
                )

                # init_bones：动画回零
                if action == "init_bones":
                    result = self._animate_joint_motion(
                        command_id=command_id,
                        target_angles=[0.0] * len(self._joint_names),
                        joint_names=self._joint_names,
                        start_frame=frame_cursor,
                        duration_frames=step_frames,
                    )
                    if not result.success:
                        return result
                    animated_any = True
                    frame_cursor = int(result.current_state.get("frame_end", frame_cursor + step_frames)) + 1
                    print(f"[GraspPlan] step={step} action=init_bones done")
                    continue

                # move_joint：从消息中提取六轴角并做插帧动画
                if action == "move_joint":
                    joint_angles = direct_joint_angles
                    if not joint_angles:
                        return ExecutionResult(
                            False,
                            command_id,
                            f"step={step} move_joint missing six-axis data",
                            ExecutionStatus.FAILED,
                        )
                    joint_names = item.get("joint_names", self._joint_names)
                    result = self._animate_joint_motion(
                        command_id=command_id,
                        target_angles=joint_angles,
                        joint_names=joint_names,
                        start_frame=frame_cursor,
                        duration_frames=step_frames,
                    )
                    if not result.success:
                        return result
                    animated_any = True
                    frame_cursor = int(result.current_state.get("frame_end", frame_cursor + step_frames)) + 1
                    print(f"[GraspPlan] step={step} action=move_joint done")
                    continue

                # move_cartesian：若带六轴角则按六轴执行；否则暂不实现 IK，仅日志
                if action == "move_cartesian":
                    joint_angles = direct_joint_angles
                    if joint_angles:
                        result = self._animate_joint_motion(
                            command_id=command_id,
                            target_angles=joint_angles,
                            joint_names=item.get("joint_names", self._joint_names),
                            start_frame=frame_cursor,
                            duration_frames=step_frames,
                        )
                        if not result.success:
                            return result
                        animated_any = True
                        frame_cursor = int(result.current_state.get("frame_end", frame_cursor + step_frames)) + 1
                        print(f"[GraspPlan] step={step} action=move_cartesian(done via six-axis)")
                    else:
                        pseudo_angles = pseudo_joint_angles
                        if pseudo_angles:
                            result = self._animate_joint_motion(
                                command_id=command_id,
                                target_angles=pseudo_angles,
                                joint_names=item.get("joint_names", self._joint_names),
                                start_frame=frame_cursor,
                                duration_frames=step_frames,
                            )
                            if not result.success:
                                return result
                            animated_any = True
                            frame_cursor = int(result.current_state.get("frame_end", frame_cursor + step_frames)) + 1
                            print(f"[GraspPlan] step={step} action=move_cartesian(done via pseudo-ik)")
                        else:
                            # 按你的要求：抓取/放置动作先打印完成日志
                            if name in {"pick", "place"}:
                                print(
                                    f"[GraspPlan] step={step} action={action} name={name} "
                                    "completed (placeholder)"
                                )
                            else:
                                print(
                                    f"[GraspPlan] step={step} action={action} name={name} "
                                    "skipped (IK not implemented)"
                                )
                            frame_cursor += step_frames
                    continue

                # 抓取/放置先做占位日志
                if action in {"gripper_close", "gripper_open", "grasp", "release"}:
                    print(f"[GraspPlan] step={step} action={action} name={name} completed (placeholder)")
                    frame_cursor += max(2, step_frames // 2)
                    continue

                print(f"[GraspPlan] step={step} unsupported action={action} name={name}")
                frame_cursor += max(2, step_frames // 2)
        finally:
            self._current_status = OperationalStatus.IDLE

        if animated_any:
            self._play_frame_range(plan_frame_start, max(plan_frame_start, frame_cursor - 1))

        return ExecutionResult(
            True,
            command_id,
            f"execute_grasp_plan handled, steps={len(sequence)}",
            ExecutionStatus.COMPLETED,
            {
                "joint_positions": self.get_joint_positions(),
                "frame_end": frame_cursor,
            },
        )

    def _log_grasp_plan_axes(
        self,
        step: Any,
        action: str,
        name: str,
        target_angles: Optional[List[float]] = None,
    ):
        """打印 GraspPlan 每一步的六轴参数。"""
        if target_angles:
            angles = self._normalize_joint_angles(target_angles)
            source = "target"
        else:
            angles = self.get_joint_positions()
            source = "current"

        padded = (angles + [0.0] * 6)[:6]
        axis_parts = []
        for i in range(6):
            rad = padded[i]
            deg = math.degrees(rad)
            axis_parts.append(f"axis_{i+1}={rad:.4f}rad({deg:.2f}deg)")
        axis_str = ", ".join(axis_parts)
        print(
            f"[GraspPlan] step={step} action={action} name={name} "
            f"axes({source}): {axis_str}"
        )

    def _execute_motion(self, command_id: str, payload: Dict[str, Any]) -> ExecutionResult:
        """执行运动指令。"""
        command_type = payload.get("command_type")
        motion_data = payload.get("motion_data", {})
        motion_params = payload.get("motion_params", {})

        self._current_status = OperationalStatus.MOVING
        try:
            if command_type == CommandType.MOVE_JOINT.value:
                return self._move_joint(command_id, motion_data, motion_params)
            if command_type == CommandType.MOVE_CARTESIAN.value:
                pseudo_angles = self._pseudo_joint_angles_from_pose(motion_data)
                if not pseudo_angles:
                    return ExecutionResult(
                        False,
                        command_id,
                        "Cartesian motion missing pose data",
                        ExecutionStatus.FAILED,
                    )
                return self._move_joint(
                    command_id,
                    {"joint_angles": pseudo_angles, "joint_names": self._joint_names},
                    motion_params,
                )
            return ExecutionResult(
                False,
                command_id,
                f"Unsupported motion type: {command_type}",
                ExecutionStatus.FAILED,
            )
        finally:
            self._current_status = OperationalStatus.IDLE

    def _move_joint(
        self,
        command_id: str,
        motion_data: Dict[str, Any],
        motion_params: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """关节空间运动（动画插帧）。"""
        joint_angles = self._extract_joint_angles(motion_data)
        if not joint_angles:
            return ExecutionResult(
                False,
                command_id,
                "Missing six-axis data (joint_angles/axis_1~axis_6/j1~j6)",
                ExecutionStatus.FAILED,
            )

        joint_names = motion_data.get("joint_names", self._joint_names)
        start_frame = motion_data.get("start_frame")
        duration_frames = self._resolve_duration_frames(
            motion_data,
            motion_params,
            self.DEFAULT_MOVE_FRAMES,
        )
        result = self._animate_joint_motion(
            command_id=command_id,
            target_angles=joint_angles,
            joint_names=joint_names,
            start_frame=start_frame,
            duration_frames=duration_frames,
        )
        if result.success:
            self._play_frame_range(
                int(result.current_state.get("frame_start", bpy.context.scene.frame_current)),
                int(result.current_state.get("frame_end", bpy.context.scene.frame_current)),
            )
        return result

    def _execute_grasp(self, command_id: str, payload: Dict) -> ExecutionResult:
        """抓取动作占位。"""
        grasp_data = payload.get("grasp_data", {})
        action = grasp_data.get("action", "")
        print(f"[Gripper] action={action} completed (placeholder)")
        return ExecutionResult(
            True,
            command_id,
            f"Gripper action {action} completed (placeholder)",
            ExecutionStatus.COMPLETED,
        )

    def _execute_system(self, command_id: str, payload: Dict) -> ExecutionResult:
        """执行系统指令。"""
        system_data = payload.get("system_data", {})
        action = system_data.get("action", "")

        if action == SystemAction.RESET.value:
            result = self._animate_joint_motion(
                command_id=command_id,
                target_angles=[0.0] * len(self._joint_names),
                joint_names=self._joint_names,
                duration_frames=self.DEFAULT_MOVE_FRAMES,
            )
            if result.success:
                self._play_frame_range(
                    int(result.current_state.get("frame_start", bpy.context.scene.frame_current)),
                    int(result.current_state.get("frame_end", bpy.context.scene.frame_current)),
                )
            return result

        if action == SystemAction.GET_STATUS.value:
            return ExecutionResult(
                True,
                command_id,
                "Status retrieved successfully",
                ExecutionStatus.COMPLETED,
                {
                    "joint_positions": self.get_joint_positions(),
                    "operational_status": self._current_status.value,
                },
            )

        return ExecutionResult(
            False,
            command_id,
            f"Unsupported system command: {action}",
            ExecutionStatus.FAILED,
        )

    def _extract_joint_angles(self, source: Dict[str, Any]) -> List[float]:
        """从不同格式中提取六轴角数据。"""
        if not isinstance(source, dict):
            return []

        for key in ("joint_angles", "joint_positions", "axis_angles", "axes"):
            value = source.get(key)
            if isinstance(value, (list, tuple)) and len(value) > 0:
                return [self._as_float(v) for v in value]

        pose = source.get("pose")
        if isinstance(pose, dict):
            angles = self._extract_joint_angles_from_named_fields(pose)
            if angles:
                return angles

        return self._extract_joint_angles_from_named_fields(source)

    def _extract_joint_angles_from_named_fields(self, data: Dict[str, Any]) -> List[float]:
        key_patterns = [
            [f"axis_{i}" for i in range(1, 7)],
            [f"joint_{i}" for i in range(1, 7)],
            [f"joint{i}" for i in range(1, 7)],
            [f"j{i}" for i in range(1, 7)],
            [f"a{i}" for i in range(1, 7)],
        ]
        for keys in key_patterns:
            if all(k in data for k in keys):
                return [self._as_float(data[k]) for k in keys]
        return []

    def _pseudo_joint_angles_from_pose(self, data: Dict[str, Any]) -> List[float]:
        """从笛卡尔位姿生成临时六轴角（非真实 IK，仅用于联调动画展示）。"""
        if not isinstance(data, dict):
            return []

        pose = data.get("pose", data)
        if not isinstance(pose, dict):
            return []

        has_any = any(k in pose for k in ("x", "y", "z", "roll", "pitch", "yaw"))
        if not has_any:
            return []

        x = self._as_float(pose.get("x", 0.0))
        y = self._as_float(pose.get("y", 0.0))
        z = self._as_float(pose.get("z", 0.0))
        roll = self._as_float(pose.get("roll", 0.0))
        pitch = self._as_float(pose.get("pitch", 0.0))
        yaw = self._as_float(pose.get("yaw", 0.0))

        def clamp(v: float, vmin: float, vmax: float) -> float:
            return max(vmin, min(vmax, v))

        # 前3轴用位置做缩放映射，后3轴直接使用姿态角（度/弧度由 normalize 自动处理）
        axis1 = clamp(x * 5.0, -2.5, 2.5)
        axis2 = clamp(y * 5.0, -2.5, 2.5)
        axis3 = clamp((z - 0.15) * 8.0, -2.0, 2.0)
        return [axis1, axis2, axis3, roll, pitch, yaw]

    @staticmethod
    def _as_float(value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

    def _normalize_joint_angles(self, joint_angles: List[float]) -> List[float]:
        """角度归一化：默认弧度；若出现明显大值则按度数转弧度。"""
        angles = [self._as_float(v) for v in joint_angles]
        if any(abs(v) > 6.5 for v in angles):
            return [math.radians(v) for v in angles]
        return angles

    def _coerce_joint_names(self, joint_names: Any) -> List[str]:
        if isinstance(joint_names, (list, tuple)) and len(joint_names) > 0:
            return [str(n) for n in joint_names]
        return self._joint_names.copy()

    def _resolve_duration_frames(
        self,
        primary: Optional[Dict[str, Any]],
        secondary: Optional[Dict[str, Any]],
        default_frames: int,
    ) -> int:
        primary = primary or {}
        secondary = secondary or {}

        for key in ("duration_frames", "frames"):
            value = primary.get(key, secondary.get(key))
            if isinstance(value, (int, float)):
                return max(2, int(value))

        duration_ms = primary.get("duration_ms", secondary.get("duration_ms"))
        if isinstance(duration_ms, (int, float)) and duration_ms > 0:
            scene = bpy.context.scene
            fps_base = scene.render.fps_base if scene.render.fps_base else 1.0
            fps = scene.render.fps / fps_base
            return max(2, int(round(duration_ms / 1000.0 * fps)))

        speed = primary.get("speed", secondary.get("speed"))
        if isinstance(speed, (int, float)) and speed > 0:
            # speed 越大，动画越快（帧数越少）
            scaled = int(round(default_frames * (0.2 / max(speed, 0.05))))
            return max(4, min(120, scaled))

        return max(2, int(default_frames))

    def _ensure_animation_data(self, armature: bpy.types.Object):
        if armature.animation_data is None:
            armature.animation_data_create()
        if armature.animation_data.action is None:
            armature.animation_data.action = bpy.data.actions.new(
                name=f"{armature.name}_Action"
            )

    def _set_linear_interpolation(self, armature: bpy.types.Object, frame_start: int, frame_end: int):
        if not armature.animation_data or not armature.animation_data.action:
            return
        action = armature.animation_data.action
        for fcurve in action.fcurves:
            if "rotation_axis_angle" not in fcurve.data_path and "rotation_euler" not in fcurve.data_path:
                continue
            for point in fcurve.keyframe_points:
                if abs(point.co.x - frame_start) < 1e-4 or abs(point.co.x - frame_end) < 1e-4:
                    point.interpolation = "LINEAR"

    def _get_bound_bones(
        self,
        armature: bpy.types.Object,
    ) -> Dict[str, Tuple[bpy.types.PoseBone, Tuple[float, float, float]]]:
        bound = {}
        for pose_bone in armature.pose.bones:
            bone = pose_bone.bone
            if "robot_axis" not in bone:
                continue
            axis_name = str(bone["robot_axis"])
            axis_key = str(bone.get("rotation_axis", "Z")).upper()
            axis_vector = self.AXIS_VECTOR_MAP.get(axis_key, self.AXIS_VECTOR_MAP["Z"])
            bound[axis_name] = (pose_bone, axis_vector)
        return bound

    def _animate_joint_motion(
        self,
        command_id: str,
        target_angles: List[float],
        joint_names: Any,
        start_frame: Optional[int] = None,
        duration_frames: int = 24,
    ) -> ExecutionResult:
        """将关节从当前姿态插帧动画到目标姿态。"""
        armature = bpy.data.objects.get(self.armature_name)
        if not armature:
            return ExecutionResult(
                False,
                command_id,
                f"Armature not found: {self.armature_name}",
                ExecutionStatus.FAILED,
            )

        angles = self._normalize_joint_angles(target_angles)
        if not angles:
            return ExecutionResult(
                False,
                command_id,
                "Empty target joint angles",
                ExecutionStatus.FAILED,
            )

        names = self._coerce_joint_names(joint_names)
        scene = bpy.context.scene
        frame_start = int(scene.frame_current if start_frame is None else start_frame)
        frame_end = frame_start + max(2, int(duration_frames))

        self._ensure_animation_data(armature)
        bound_bones = self._get_bound_bones(armature)
        applied = 0

        for axis_name, angle in zip(names, angles):
            target_angle = self._as_float(angle)

            if axis_name in bound_bones:
                pose_bone, axis_vec = bound_bones[axis_name]
                pose_bone.rotation_mode = "AXIS_ANGLE"
                current_angle = self._as_float(pose_bone.rotation_axis_angle[0])

                pose_bone.rotation_axis_angle = (current_angle, axis_vec[0], axis_vec[1], axis_vec[2])
                pose_bone.keyframe_insert(data_path="rotation_axis_angle", frame=frame_start)

                pose_bone.rotation_axis_angle = (target_angle, axis_vec[0], axis_vec[1], axis_vec[2])
                pose_bone.keyframe_insert(data_path="rotation_axis_angle", frame=frame_end)
                applied += 1
                continue

            # 未绑定时按骨骼名 fallback 到 Euler.Y
            pose_bone = armature.pose.bones.get(axis_name)
            if not pose_bone:
                continue

            current_angle = self._as_float(pose_bone.rotation_euler[1])
            pose_bone.rotation_euler[1] = current_angle
            pose_bone.keyframe_insert(data_path="rotation_euler", index=1, frame=frame_start)
            pose_bone.rotation_euler[1] = target_angle
            pose_bone.keyframe_insert(data_path="rotation_euler", index=1, frame=frame_end)
            applied += 1

        if applied == 0:
            return ExecutionResult(
                False,
                command_id,
                "No valid joint/bone found for animation",
                ExecutionStatus.FAILED,
            )

        self._set_linear_interpolation(armature, frame_start, frame_end)
        scene.frame_set(frame_start)
        bpy.context.view_layer.update()

        return ExecutionResult(
            success=True,
            command_id=command_id,
            message=f"Joint motion animated ({frame_start}->{frame_end}, joints={applied})",
            status=ExecutionStatus.COMPLETED,
            current_state={
                "joint_positions": self.get_joint_positions(),
                "frame_start": frame_start,
                "frame_end": frame_end,
            },
        )

    def _play_frame_range(self, frame_start: int, frame_end: int):
        """按帧播放关键帧范围，避免看起来瞬间跳变。"""
        if frame_end <= frame_start:
            return

        scene = bpy.context.scene
        fps_base = scene.render.fps_base if scene.render.fps_base else 1.0
        fps = scene.render.fps / fps_base
        interval = 1.0 / max(fps, 1.0)

        self._playback_token += 1
        token = self._playback_token
        scene.frame_set(frame_start)

        def _tick():
            if token != self._playback_token:
                return None

            current = int(scene.frame_current)
            if current >= frame_end:
                scene.frame_set(frame_end)
                return None

            scene.frame_set(current + 1)
            return interval

        bpy.app.timers.register(_tick, first_interval=interval)

    def get_current_status(self) -> OperationalStatus:
        return self._current_status

    def get_joint_positions(self) -> List[float]:
        """获取当前关节角度（弧度）。"""
        armature = bpy.data.objects.get(self.armature_name)
        if not armature:
            return [0.0] * len(self._joint_names)

        bound_bones = self._get_bound_bones(armature)
        positions: List[float] = []
        for axis_name in self._joint_names:
            if axis_name in bound_bones:
                pose_bone, _ = bound_bones[axis_name]
                if pose_bone.rotation_mode == "AXIS_ANGLE":
                    positions.append(self._as_float(pose_bone.rotation_axis_angle[0]))
                else:
                    positions.append(self._as_float(pose_bone.rotation_euler[1]))
                continue

            pose_bone = armature.pose.bones.get(axis_name)
            if not pose_bone:
                positions.append(0.0)
            elif pose_bone.rotation_mode == "AXIS_ANGLE":
                positions.append(self._as_float(pose_bone.rotation_axis_angle[0]))
            else:
                positions.append(self._as_float(pose_bone.rotation_euler[1]))
        return positions

    def set_armature_name(self, name: str):
        self.armature_name = name

    def set_joint_names(self, names: List[str]):
        self._joint_names = [str(n) for n in names] if names else [f"axis_{i}" for i in range(1, 7)]
