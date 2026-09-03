#!/usr/bin/env python3
"""Synchronize a warehouse cart with an Animation Graph character pose."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Callable, TypeAlias


Vector3: TypeAlias = tuple[float, float, float]
QuaternionXyzw: TypeAlias = tuple[float, float, float, float]
Pose: TypeAlias = tuple[Vector3, QuaternionXyzw]
PoseReader: TypeAlias = Callable[[], Pose]
PoseWriter: TypeAlias = Callable[[Pose], None]


def _float_tuple(values: Sequence[float], size: int, label: str) -> tuple[float, ...]:
    if len(values) != size:
        raise ValueError(f"{label} must contain exactly {size} values")
    result = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in result):
        raise ValueError(f"{label} values must be finite")
    return result


def _validate_pose(pose: tuple[Sequence[float], Sequence[float]]) -> Pose:
    if len(pose) != 2:
        raise ValueError("pose must contain position and quaternion")
    position = _float_tuple(pose[0], 3, "position")
    quaternion = normalize_quaternion_xyzw(pose[1])
    return (
        (position[0], position[1], position[2]),
        quaternion,
    )


def normalize_quaternion_xyzw(quaternion: Sequence[float]) -> QuaternionXyzw:
    """Return a finite unit quaternion stored in x, y, z, w order."""
    x, y, z, w = _float_tuple(quaternion, 4, "quaternion")
    length = math.sqrt(x * x + y * y + z * z + w * w)
    if length <= 1e-12:
        raise ValueError("zero-length quaternion is invalid")
    return (x / length, y / length, z / length, w / length)


def _multiply_quaternions(
    left: QuaternionXyzw,
    right: QuaternionXyzw,
) -> QuaternionXyzw:
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    return normalize_quaternion_xyzw(
        (
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
            lw * rw - lx * rx - ly * ry - lz * rz,
        )
    )


def _conjugate_quaternion(quaternion: QuaternionXyzw) -> QuaternionXyzw:
    x, y, z, w = quaternion
    return (-x, -y, -z, w)


def _rotate_vector(vector: Vector3, quaternion: QuaternionXyzw) -> Vector3:
    vx, vy, vz = vector
    qx, qy, qz, qw = quaternion
    tx = 2.0 * (qy * vz - qz * vy)
    ty = 2.0 * (qz * vx - qx * vz)
    tz = 2.0 * (qx * vy - qy * vx)
    return (
        vx + qw * tx + qy * tz - qz * ty,
        vy + qw * ty + qz * tx - qx * tz,
        vz + qw * tz + qx * ty - qy * tx,
    )


def compose_pose(
    parent_pose: tuple[Sequence[float], Sequence[float]],
    child_pose: tuple[Sequence[float], Sequence[float]],
) -> Pose:
    """Compose two rigid poses represented as position and xyzw quaternion."""
    parent_position, parent_rotation = _validate_pose(parent_pose)
    child_position, child_rotation = _validate_pose(child_pose)
    rotated_child = _rotate_vector(child_position, parent_rotation)
    return (
        tuple(
            parent_position[index] + rotated_child[index]
            for index in range(3)
        ),
        _multiply_quaternions(parent_rotation, child_rotation),
    )


def relative_pose(
    parent_pose: tuple[Sequence[float], Sequence[float]],
    world_pose: tuple[Sequence[float], Sequence[float]],
) -> Pose:
    """Return the transform that maps parent_pose to world_pose."""
    parent_position, parent_rotation = _validate_pose(parent_pose)
    world_position, world_rotation = _validate_pose(world_pose)
    inverse_rotation = _conjugate_quaternion(parent_rotation)
    delta = tuple(
        world_position[index] - parent_position[index]
        for index in range(3)
    )
    return (
        _rotate_vector(delta, inverse_rotation),
        _multiply_quaternions(inverse_rotation, world_rotation),
    )


class PoseSyncController:
    """Maintain a calibrated Worker-to-Cart transform while playback is active."""

    def __init__(
        self,
        *,
        read_worker_pose: PoseReader,
        read_cart_pose: PoseReader,
        write_cart_pose: PoseWriter,
        clear_cart_override: Callable[[], None],
        is_playing: Callable[[], bool],
    ) -> None:
        self._read_worker_pose = read_worker_pose
        self._read_cart_pose = read_cart_pose
        self._write_cart_pose = write_cart_pose
        self._clear_cart_override = clear_cart_override
        self._is_playing = is_playing
        self.relative_transform: Pose | None = None
        self.calibration_count = 0

    def update(self) -> bool:
        """Write one Cart pose when playing; return whether a pose was written."""
        if not self._is_playing():
            return False

        worker_pose = self._read_worker_pose()
        if self.relative_transform is None:
            self.relative_transform = relative_pose(
                worker_pose,
                self._read_cart_pose(),
            )
            self.calibration_count += 1

        self._write_cart_pose(compose_pose(worker_pose, self.relative_transform))
        return True

    def stop(self) -> None:
        """Clear the runtime override and calibrate again on the next Play."""
        self._clear_cart_override()
        self.relative_transform = None


DEFAULT_WORKER_SKELROOT_PATH = "/World/Characters/Worker_01/DHGen/SkelRoot"
DEFAULT_CART_PATH = "/World/DynamicActors/CartAssembly"
_HANDLE_NAME = "_warehouse_worker_cart_pose_sync_handle"


class IsaacSimPoseSynchronizer:
    """Isaac Sim subscriptions and Session Layer adapter for PoseSyncController."""

    _TRANSFORM_PROPERTIES = ("xformOp:translate", "xformOp:orient")

    def __init__(self, worker_skelroot_path: str, cart_path: str) -> None:
        import omni.anim.graph.core as ag
        import omni.kit.app
        import omni.timeline
        import omni.usd

        self._ag = ag
        self._omni_usd = omni.usd
        self._timeline_module = omni.timeline
        self._timeline = omni.timeline.get_timeline_interface()
        if self._timeline.is_playing():
            raise RuntimeError("Stop the Timeline before configuring Worker-Cart sync.")

        self._stage = omni.usd.get_context().get_stage()
        if self._stage is None:
            raise RuntimeError("No USD stage is open.")

        self._worker_skelroot_path = worker_skelroot_path
        self._cart_path = cart_path
        worker = self._stage.GetPrimAtPath(worker_skelroot_path)
        if not worker or not worker.IsValid():
            raise RuntimeError(f"Worker SkelRoot prim not found: {worker_skelroot_path}")

        self._cart = self._stage.GetPrimAtPath(cart_path)
        if not self._cart or not self._cart.IsValid():
            raise RuntimeError(f"CartAssembly prim not found: {cart_path}")
        for property_name in self._TRANSFORM_PROPERTIES:
            attribute = self._cart.GetAttribute(property_name)
            if not attribute or not attribute.IsValid():
                raise RuntimeError(f"CartAssembly attribute not found: {property_name}")

        self._character = None
        self._last_runtime_error: str | None = None
        self._reported_calibration_count = 0
        self._controller = PoseSyncController(
            read_worker_pose=self._read_worker_pose,
            read_cart_pose=self._read_cart_pose,
            write_cart_pose=self._write_cart_pose,
            clear_cart_override=self._clear_cart_override,
            is_playing=self._timeline.is_playing,
        )
        self._update_subscription = (
            omni.kit.app.get_app()
            .get_update_event_stream()
            .create_subscription_to_pop(self._on_update, name="WorkerCartPoseSync")
        )
        self._timeline_subscription = (
            self._timeline.get_timeline_event_stream()
            .create_subscription_to_pop(self._on_timeline_event, name="WorkerCartPoseSyncTimeline")
        )

    @property
    def relative_transform(self) -> Pose | None:
        return self._controller.relative_transform

    @staticmethod
    def _matrix_to_pose(matrix) -> Pose:
        translation = matrix.ExtractTranslation()
        rotation = matrix.ExtractRotationQuat()
        imaginary = rotation.GetImaginary()
        return _validate_pose(
            (
                tuple(float(translation[index]) for index in range(3)),
                (
                    float(imaginary[0]),
                    float(imaginary[1]),
                    float(imaginary[2]),
                    float(rotation.GetReal()),
                ),
            )
        )

    def _read_worker_pose(self) -> Pose:
        import carb

        if self._character is None:
            self._character = self._ag.get_character(self._worker_skelroot_path)
        if self._character is None:
            raise RuntimeError(
                "Animation Graph character is not ready yet; waiting for a runtime frame."
            )

        position = carb.Float3(0.0, 0.0, 0.0)
        rotation = carb.Float4(0.0, 0.0, 0.0, 1.0)
        self._character.get_world_transform(position, rotation)
        return _validate_pose(
            (
                (position.x, position.y, position.z),
                (rotation.x, rotation.y, rotation.z, rotation.w),
            )
        )

    def _read_cart_pose(self) -> Pose:
        matrix = self._omni_usd.get_world_transform_matrix(self._cart)
        return self._matrix_to_pose(matrix)

    @staticmethod
    def _vector_value(attribute, position: Vector3):
        from pxr import Gf, Sdf

        type_name = attribute.GetTypeName()
        if type_name == Sdf.ValueTypeNames.Float3:
            return Gf.Vec3f(*position)
        if type_name == Sdf.ValueTypeNames.Half3:
            return Gf.Vec3h(*position)
        if type_name == Sdf.ValueTypeNames.Double3:
            return Gf.Vec3d(*position)
        raise RuntimeError(f"Unsupported Cart translate type: {type_name}")

    @staticmethod
    def _quaternion_value(attribute, quaternion: QuaternionXyzw):
        from pxr import Gf, Sdf

        x, y, z, w = quaternion
        type_name = attribute.GetTypeName()
        if type_name == Sdf.ValueTypeNames.Quatf:
            return Gf.Quatf(w, Gf.Vec3f(x, y, z))
        if type_name == Sdf.ValueTypeNames.Quath:
            return Gf.Quath(w, Gf.Vec3h(x, y, z))
        if type_name == Sdf.ValueTypeNames.Quatd:
            return Gf.Quatd(w, Gf.Vec3d(x, y, z))
        raise RuntimeError(f"Unsupported Cart orient type: {type_name}")

    def _write_cart_pose(self, world_pose: Pose) -> None:
        from pxr import Usd

        parent = self._cart.GetParent()
        parent_world_pose = self._matrix_to_pose(
            self._omni_usd.get_world_transform_matrix(parent)
        )
        local_position, local_rotation = relative_pose(parent_world_pose, world_pose)
        session_layer = self._stage.GetSessionLayer()
        edit_target = self._stage.GetEditTargetForLocalLayer(session_layer)
        with Usd.EditContext(self._stage, edit_target):
            translate = self._cart.GetAttribute("xformOp:translate")
            orient = self._cart.GetAttribute("xformOp:orient")
            if not translate.Set(self._vector_value(translate, local_position)):
                raise RuntimeError("Failed to write CartAssembly session translate.")
            if not orient.Set(self._quaternion_value(orient, local_rotation)):
                raise RuntimeError("Failed to write CartAssembly session orient.")

    def _clear_cart_override(self) -> None:
        from pxr import Sdf

        session_layer = self._stage.GetSessionLayer()
        session_prim = session_layer.GetPrimAtPath(Sdf.Path(self._cart_path))
        if not session_prim:
            return
        for property_name in self._TRANSFORM_PROPERTIES:
            property_path = session_prim.path.AppendProperty(property_name)
            property_spec = session_layer.GetPropertyAtPath(property_path)
            if property_spec:
                session_prim.RemoveProperty(property_spec)

    def _on_update(self, _event) -> None:
        try:
            if not self._controller.update():
                return
            if self._controller.calibration_count != self._reported_calibration_count:
                self._reported_calibration_count = self._controller.calibration_count
                print(
                    "[Worker-Cart Sync] CALIBRATED: "
                    f"relative={self._controller.relative_transform}"
                )
            self._last_runtime_error = None
        except Exception as error:
            message = f"{type(error).__name__}: {error}"
            if message != self._last_runtime_error:
                print(f"[Worker-Cart Sync] WAITING/FAILED: {message}")
                self._last_runtime_error = message

    def _on_timeline_event(self, event) -> None:
        if event.type == int(self._timeline_module.TimelineEventType.STOP):
            self._character = None
            self._controller.stop()
            self._last_runtime_error = None
            print("[Worker-Cart Sync] STOPPED: session transform override cleared.")

    def shutdown(self) -> None:
        """Release callbacks and remove only this synchronizer's Cart overrides."""
        self._controller.stop()
        self._update_subscription = None
        self._timeline_subscription = None
        self._character = None
        print("[Worker-Cart Sync] SHUTDOWN")


def run(
    worker_skelroot_path: str = DEFAULT_WORKER_SKELROOT_PATH,
    cart_path: str = DEFAULT_CART_PATH,
) -> IsaacSimPoseSynchronizer:
    """Install one live synchronizer from Isaac Sim's Script Editor."""
    import builtins

    previous = getattr(builtins, _HANDLE_NAME, None)
    if previous is not None:
        previous.shutdown()

    synchronizer = IsaacSimPoseSynchronizer(worker_skelroot_path, cart_path)
    setattr(builtins, _HANDLE_NAME, synchronizer)
    print(
        "[Worker-Cart Sync] READY: keep this script installed, then press Play. "
        "Press Stop to restore the Cart pose."
    )
    return synchronizer


if __name__ == "__main__":
    _SYNCHRONIZER = run()
