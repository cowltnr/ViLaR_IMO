"""Optional post-arrival runtime turn; Cart stays parked. No USD authoring."""

import math


def target_yaw(position, target, forward_yaw_deg):
    if not all(math.isfinite(v) for v in (*position, *target, forward_yaw_deg)):
        raise ValueError("Facing inputs must be finite")
    dx, dy = target[0] - position[0], target[1] - position[1]
    if math.hypot(dx, dy) < 1e-6:
        raise ValueError("Box target has no horizontal direction from Worker")
    return math.degrees(math.atan2(dy, dx)) - forward_yaw_deg


def turn_yaw(start, target, fraction):
    return start + ((target - start + 180) % 360 - 180) * max(0, min(1, fraction))


def matches_arrival(payload, expected_command):
    # carb.dictionary.Item.get requires the default argument, unlike dict.get.
    return (payload.get("agent_name", "") == expected_command.split()[0]
            and payload.get("command_name", "") == "GoTo"
            and payload.get("status", "") == "default"
            and payload.get("command", "").split() == expected_command.split())


def box_center(stage, path):
    from pxr import Usd, UsdGeom
    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():
        raise RuntimeError(f"Box target does not exist: {path}")
    bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                              [UsdGeom.Tokens.default_, UsdGeom.Tokens.render,
                               UsdGeom.Tokens.proxy]).ComputeWorldBound(prim).ComputeAlignedRange()
    if bounds.IsEmpty():
        raise RuntimeError(f"Box target has no loaded geometry: {path}")
    center = tuple(float(v) for v in bounds.GetMidpoint())
    if not all(math.isfinite(v) for v in center):
        raise RuntimeError("Box bounds are not finite")
    return center


class FaceBoxRuntime:
    """Own the synchronizer plus event/turn callbacks as one shutdown handle."""

    def __init__(self, sync, expected_command, worker_goal, cart_goal, target,
                 duration, forward_yaw, tolerance, transfer=None, approach=None, gesture=None):
        import carb.events
        import omni.kit.app
        import omni.timeline
        from omni.anim.people.settings import AgentEvent

        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Turn duration must be positive and finite")
        self.sync = sync
        self.transfer = transfer
        self.approach = approach
        self.gesture = gesture
        self.approach_completed = False
        self.expected_command = expected_command
        self.worker_goal, self.cart_goal = worker_goal, cart_goal
        self.target, self.duration = target, duration
        self.forward_yaw, self.tolerance = forward_yaw, tolerance
        self.timeline = omni.timeline.get_timeline_interface()
        self.state = "waiting_arrival"
        self._stop_type = int(omni.timeline.TimelineEventType.STOP)
        app = omni.kit.app.get_app()
        self._command_sub = app.get_message_bus_event_stream().create_subscription_to_pop_by_type(
            carb.events.type_from_string(AgentEvent.CommandEndEvent), self._on_command,
            name="WarehouseBoxArrival")
        self._update_sub = app.get_update_event_stream().create_subscription_to_pop(
            self._on_update, name="WarehouseBoxTurn")
        self._timeline_sub = self.timeline.get_timeline_event_stream().create_subscription_to_pop(
            self._on_timeline, name="WarehouseBoxTurnReset")

    def _on_command(self, event):
        if (self.timeline.is_playing() and self.state == "waiting_arrival"
                and matches_arrival(event.payload, self.expected_command)):
            self.state = "arrival_pending"
        elif (self.timeline.is_playing() and self.state == "approaching"
              and matches_arrival(event.payload, self.approach.command)):
            self.state = "approach_arrived"

    def _on_update(self, event):
        if not self.timeline.is_playing() or self.state in ("waiting_arrival", "failed"):
            return
        try:
            import carb
            if self.state == "approaching":
                if self.timeline.get_current_time() - self.approach.started > self.approach.timeout:
                    self.approach.cancel()
                    raise RuntimeError("Worker approach timed out; no turn or pickup started")
                return
            if self.state == "arrival_pending":
                pose = self.sync._read_worker_pose()
                cart = self.sync._read_cart_pose()
                if (math.dist(pose[0], self.worker_goal) > self.tolerance
                        or math.dist(cart[0][:2], self.cart_goal[:2]) > self.tolerance):
                    raise RuntimeError("GoTo ended outside arrival tolerance; rotation refused")
                self.sync.hold()
                if self.approach is not None and not getattr(self.approach, 'after_turn', False):
                    self.approach.begin(pose[0], self.target, self.timeline.get_current_time())
                    self.state = "approaching"
                    return
            if self.state in ("arrival_pending", "approach_arrived"):
                pose = self.sync._read_worker_pose()
                if self.state == "approach_arrived":
                    if (math.dist(pose[0], self.approach.goal) > self.tolerance
                            or (not getattr(self.approach, 'after_turn', False)
                                and math.dist(pose[0][:2], self.target[:2]) > self.approach.max_distance)):
                        raise RuntimeError("Approach ended outside position tolerance")
                    print("[Worker Approach] ARRIVED; Cart remains parked.")
                    self.approach_completed = True
                self.position = pose[0]
                self.start_yaw = math.degrees(2 * math.atan2(pose[1][2], pose[1][3]))
                self.end_yaw = target_yaw(self.position, self.target, self.forward_yaw)
                self.start_time = self.timeline.get_current_time()
                self.state = "turning"
                print("[Worker Face Box] TURNING; Cart parked.")
            fraction = (self.timeline.get_current_time() - self.start_time) / self.duration
            angle = math.radians(turn_yaw(self.start_yaw, self.end_yaw, fraction)) / 2
            # Runtime pose only: preserve position, change planar heading during Idle.
            if self.state != "facing" or not getattr(self.gesture, "controls_heading", False):
                self.sync._character.set_world_transform(
                    carb.Float3(*self.position), carb.Float4(0, 0, math.sin(angle), math.cos(angle)))
            if fraction >= 1 and self.state != "facing":
                if (getattr(self.approach, 'after_turn', False)
                        and not getattr(self, 'approach_completed', False)):
                    moving = self.approach.begin(self.sync._read_worker_pose()[0], self.target,
                                                 self.timeline.get_current_time())
                    if moving:
                        self.state = 'approaching'
                        return
                    self.approach_completed = True
                self.state = "facing"
                print("[Worker Face Box] FACING_BOX; Worker waiting, Cart parked.")
                if self.transfer is not None:
                    if hasattr(self.gesture, 'refresh_shoulders'):
                        self.gesture.refresh_shoulders(self.sync._character,
                            (self.position, (0,0,math.sin(angle),math.cos(angle))))
                        if self.transfer.max_center_height_offset is not None:
                            self.transfer.max_center_height_offset = min(
                                self.gesture.shoulders[side][2] + self.gesture.arm_lengths[side]*.9*.95
                                for side in self.gesture.shoulders)
                    self.transfer.start(self.timeline.get_current_time(), self.position)
                if self.gesture is not None:
                    self.gesture.start(self.timeline.get_current_time(), self.sync._character,
                                       (self.position, (0, 0, math.sin(angle), math.cos(angle))), self.target)
            if self.state == "facing" and self.transfer is not None:
                self.transfer.update(self.timeline.get_current_time())
            if self.state == "facing" and self.gesture is not None:
                self.gesture.update(self.timeline.get_current_time())
        except Exception as error:
            self.state = "failed"
            if self.approach is not None:
                self.approach.cancel()
            if self.transfer is not None:
                self.transfer.restore()
            if self.gesture is not None:
                self.gesture.reset()
            print(f"[Worker Face Box] FAILED: {error}; inspect scene and press Stop.")

    def _on_timeline(self, event):
        if event.type == self._stop_type:
            try:
                if self.transfer is not None:
                    self.transfer.restore()
            finally:
                if self.gesture is not None:
                    self.gesture.reset()
                if self.approach is not None:
                    self.approach.reset()
                self.state = "waiting_arrival"
                self.approach_completed = False

    def shutdown(self):
        self._command_sub = self._update_sub = self._timeline_sub = None
        self.state = "failed"
        try:
            if self.approach is not None:
                self.approach.reset()
            if self.transfer is not None:
                self.transfer.restore()
        finally:
            try:
                if self.gesture is not None:
                    self.gesture.shutdown()
            finally:
                self.sync.shutdown()
