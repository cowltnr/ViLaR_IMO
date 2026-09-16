"""Optional visual reach, not grasping. Owned session Graph edits; no save or Bake."""

import math


def gesture_sample(elapsed, reach, hold, lower):
    if not all(math.isfinite(v) for v in (elapsed, reach, hold, lower)) or min(reach, hold, lower) <= 0:
        raise ValueError('Gesture timing must be positive and finite')
    smooth = lambda t: (lambda x: x*x*(3-2*x))(max(0, min(1, t)))
    weight = smooth(elapsed / reach) * (1 - smooth((elapsed - reach - hold) / lower))
    extension = 1 - 0.4 * smooth((elapsed - reach) / hold)
    return weight, extension


def arm_chains(joints):
    """Resolve full hierarchy first; graph IK consumes unique leaf joint tokens."""
    result = {}
    for side, names in [('left', ('lefthand', 'lhand', 'lwrist')),
                        ('right', ('righthand', 'rhand', 'rwrist'))]:
        ends = [str(j) for j in joints if str(j).split('/')[-1].lower().replace('_', '') in names]
        if len(ends) != 1:
            raise ValueError(f'Cannot identify unique {side} hand in Graph reference Skeleton')
        end = ends[0]
        parent = end.rsplit('/', 1)[0]
        start = parent.rsplit('/', 1)[0]
        if parent not in joints or start not in joints or start == parent:
            raise ValueError(f'Missing two-bone hierarchy for {end}')
        chain = tuple(j.split('/')[-1] for j in (start, parent, end))
        if any(sum(str(j).split('/')[-1] == token for j in joints) != 1 for token in chain):
            raise ValueError('Ambiguous Graph joint leaf names')
        result[side] = chain
    return result


def reach_target(shoulder, box, distance):
    if not all(math.isfinite(v) for v in (*shoulder, *box, distance)) or distance <= 0:
        raise ValueError('Invalid reach geometry')
    delta = tuple(box[i] - shoulder[i] for i in range(3))
    length = math.sqrt(sum(v*v for v in delta))
    if length < 1e-6:
        raise ValueError('No reach direction')
    return tuple(shoulder[i] + delta[i] / length * min(distance, length) for i in range(3))


class GestureGraphLayer:
    def __init__(self, stage, graph_path, chains):
        self.stage, self.path, self.chains = stage, graph_path, chains
        self.layer = None

    def install(self):
        from pxr import Usd, Sdf
        if self.layer is not None:
            raise RuntimeError('Gesture Graph already installed')
        graph = self.stage.GetPrimAtPath(self.path)
        pose = graph.GetRelationship('inputs:pose').GetTargets()
        if len(pose) != 1:
            raise RuntimeError('Expected one existing Graph pose source')
        if any(str(p.GetName()).startswith('WarehouseReach') for p in graph.GetChildren()):
            raise RuntimeError('Existing WarehouseReach nodes; shut down old runtime first')
        self.layer = Sdf.Layer.CreateAnonymous('warehouse-reach-gesture.usda')
        session = self.stage.GetSessionLayer()
        session.subLayerPaths = [self.layer.identifier, *session.subLayerPaths]
        try:
            with Usd.EditContext(self.stage, self.layer):
                for name, kind, value in [('Weight', Sdf.ValueTypeNames.Float, 0.0),
                                          ('LeftTarget', Sdf.ValueTypeNames.Float3, (0, 0, 0)),
                                          ('RightTarget', Sdf.ValueTypeNames.Float3, (0, 0, 0))]:
                    var = 'WarehouseReach' + name
                    graph.CreateAttribute('anim:graph:variable:' + var, kind,
                                          custom=True, variability=Sdf.VariabilityUniform).Set(value)
                    node = self.stage.DefinePrim(self.path + '/' + var, 'ReadVariable')
                    node.CreateAttribute('inputs:variableName', Sdf.ValueTypeNames.Token).Set(var)
                for side in ('left', 'right'):
                    path = self.path + '/WarehouseReach' + side.title() + 'IK'
                    node = self.stage.DefinePrim(path, 'TwoBoneIK')
                    node.CreateRelationship('inputs:pose').SetTargets(pose)
                    node.CreateRelationship('inputs:blendWeight').SetTargets([self.path + '/WarehouseReachWeight'])
                    node.CreateRelationship('inputs:targetPosition').SetTargets([
                        self.path + '/WarehouseReach' + side.title() + 'Target'])
                    for key, token in zip(('startJoint', 'hingeJoint', 'endJoint'), self.chains[side]):
                        node.CreateAttribute('inputs:' + key, Sdf.ValueTypeNames.Token).Set(token)
                    node.CreateAttribute('inputs:worldSpaceTarget', Sdf.ValueTypeNames.Bool).Set(True)
                    pose = [path]
                graph.GetRelationship('inputs:pose').SetTargets(pose)
            if str(graph.GetRelationship('inputs:pose').GetTargets()[0]) != pose[0]:
                raise RuntimeError('Stronger Graph pose override prevents gesture installation')
        except BaseException:
            self.restore()
            raise

    def restore(self):
        if self.layer is not None:
            session = self.stage.GetSessionLayer()
            session.subLayerPaths = [p for p in session.subLayerPaths if p != self.layer.identifier]
            self.layer = None


class ReachGesture:
    def __init__(self, stage, skelroot_path, *, reach, hold, lower, distance):
        from pxr import Usd, UsdGeom, UsdSkel
        gesture_sample(0, reach, hold, lower)
        if not math.isfinite(distance) or distance <= 0:
            raise ValueError('Invalid reach distance')
        root = stage.GetPrimAtPath(skelroot_path)
        graphs = root.GetRelationship('animationGraph').GetTargets()
        if len(graphs) != 1:
            raise RuntimeError('Expected one Worker Animation Graph')
        graph = stage.GetPrimAtPath(graphs[0])
        refs = graph.GetRelationship('skel:skeleton').GetTargets()
        if len(refs) != 1:
            raise RuntimeError('Expected one Graph reference Skeleton')
        ref = UsdSkel.Skeleton(stage.GetPrimAtPath(refs[0]))
        if not ref:
            raise RuntimeError('Graph reference Skeleton not loaded')
        chains = arm_chains(list(ref.GetJointsAttr().Get() or []))
        skeletons = [UsdSkel.Skeleton(p) for p in Usd.PrimRange(root) if p.IsA(UsdSkel.Skeleton)]
        if len(skeletons) != 1:
            raise RuntimeError('Expected one Worker Skeleton')
        skeleton = skeletons[0]
        joints = list(skeleton.GetJointsAttr().Get() or [])
        worker_chains = arm_chains(joints)
        binds = skeleton.GetBindTransformsAttr().Get()
        if binds is None or len(binds) != len(joints):
            raise RuntimeError('Worker bind pose incomplete')
        relative = (UsdGeom.Xformable(skeleton).ComputeLocalToWorldTransform(Usd.TimeCode.Default()) *
                    UsdGeom.Xformable(root).ComputeLocalToWorldTransform(Usd.TimeCode.Default()).GetInverse())
        self.shoulders = {}
        self.arm_lengths = {}
        for side, chain in worker_chains.items():
            indices = [next(i for i, j in enumerate(joints) if str(j).split('/')[-1] == token) for token in chain]
            points = [tuple((binds[i] * relative).ExtractTranslation()) for i in indices]
            length = math.dist(points[0], points[1]) + math.dist(points[1], points[2])
            if not 0.1 < distance < length * 0.95:
                raise RuntimeError(f'Reach distance exceeds {side} arm length; inspect rig')
            self.shoulders[side] = points[0]
            self.arm_lengths[side] = length
        self.graph = GestureGraphLayer(stage, str(graphs[0]), chains)
        self.reach, self.hold, self.lower, self.distance = reach, hold, lower, distance
        self.character = None
        self.started = None
        self.done = False

    def install(self):
        self.graph.install()

    def start(self, now, character, pose, target):
        from scripts.warehouse_worker_cart_pose_sync import compose_pose
        self.character = character
        self.started = now
        self.done = False
        self.origins = {side: compose_pose(pose, (point, (0, 0, 0, 1)))[0]
                        for side, point in self.shoulders.items()}
        self.target = target
        self.update(now)
        print('[Worker Reach] REACHING: visual gesture, no hand contact required.')

    def update(self, now):
        import carb
        if self.started is None or self.done:
            return
        weight, extension = gesture_sample(now - self.started, self.reach, self.hold, self.lower)
        for side, shoulder in self.origins.items():
            point = reach_target(shoulder, self.target, self.distance * extension)
            self.character.set_variable('WarehouseReach' + side.title() + 'Target', carb.Float3(*point))
        self.character.set_variable('WarehouseReachWeight', float(weight))
        values = self.character.get_variable('WarehouseReachWeight')
        if not values or abs(float(values[0]) - weight) > 1e-4:
            raise RuntimeError('Gesture variable not accepted by Animation Graph')
        if now - self.started >= self.reach + self.hold + self.lower:
            self.done = True
            print('[Worker Reach] COMPLETE: arms returned to baseline pose.')

    def reset(self):
        # Stop may already have invalidated the runtime character. The Graph default is zero.
        try:
            if self.character is not None:
                self.character.set_variable('WarehouseReachWeight', 0.0)
        except RuntimeError as error:
            print(f'[Worker Reach] RESET note: {error}; Graph default weight remains zero.')
        finally:
            self.walking_pose = None
            self.character = None
            self.started = None
            self.done = False

    def shutdown(self):
        try:
            self.reset()
        finally:
            self.graph.restore()


def height_matched_target(shoulder, box, horizontal_reach, arm_limit):
    """Preserve box height before allocating remaining arm reach in XY."""
    if (not all(math.isfinite(v) for v in (*shoulder, *box, horizontal_reach, arm_limit))
            or horizontal_reach < 0 or arm_limit <= 0):
        raise ValueError('Invalid synchronized reach geometry')
    dz = max(-arm_limit * .95, min(arm_limit * .95, box[2] - shoulder[2]))
    dx, dy = box[0] - shoulder[0], box[1] - shoulder[1]
    planar = math.hypot(dx, dy)
    length = min(horizontal_reach, math.sqrt(max(0, arm_limit**2 - dz**2)), planar)
    return (shoulder[0] + (dx / planar * length if planar > 1e-8 else 0),
            shoulder[1] + (dy / planar * length if planar > 1e-8 else 0), shoulder[2] + dz)


def follow_yaw(current, desired, dt, rate):
    if not all(math.isfinite(v) for v in (current, desired, dt, rate)) or dt < 0 or rate <= 0:
        raise ValueError('Invalid heading update')
    error = (desired - current + 180) % 360 - 180
    return current + max(-rate * dt, min(rate * dt, error))


def height_limit_direction(target_z, box_z):
    if abs(target_z - box_z) <= .01:
        return None
    return 'below_minimum' if target_z > box_z else 'above_maximum'


def height_feedback_step(offset, desired, measured, dt, limit, response_seconds):
    if (not all(math.isfinite(v) for v in (offset, desired, measured, dt, limit, response_seconds))
            or dt < 0 or limit <= 0 or response_seconds <= 0):
        raise ValueError('Invalid hand height feedback')
    gain = 1 - math.exp(-min(dt, .1) / response_seconds)
    return max(-limit, min(limit, offset + gain * (desired - measured)))


class BoxSynchronizedReach(ReachGesture):
    """Same IK layer, driven by successful BoxTransfer updates instead of a timer.

    Owns heading only after initial facing. Keeps Worker root translation fixed.
    Final attention-like arms are explicit IK targets, not an assumed Idle pose.
    """

    controls_heading = True

    def configure_height_feedback(self, enabled, limit, response_seconds):
        height_feedback_step(0,0,0,0,limit,response_seconds)
        self.feedback_enabled, self.feedback_limit, self.feedback_response = enabled, limit, response_seconds

    def refresh_shoulders(self, character, pose):
        if not getattr(self, 'feedback_enabled', False):
            return
        import carb
        from scripts.warehouse_worker_cart_pose_sync import relative_pose
        shoulders = {}
        for side, name in [('left', 'LeftArm'), ('right', 'RightArm')]:
            p, q = carb.Float3(float('nan'),float('nan'),float('nan')), carb.Float4(0,0,0,1)
            result = character.get_joint_transform(name, p, q)
            point = (p.x,p.y,p.z)
            if (result is False or not all(math.isfinite(v) for v in point)
                    or not .3 < point[2] - pose[0][2] < 2.5 or math.dist(point, pose[0]) > 3):
                raise RuntimeError(f'Invalid runtime shoulder measurement: {name}; pickup refused')
            shoulders[side] = relative_pose(pose, (point, (0,0,0,1)))[0]
        self.shoulders = shoulders
        print('[Worker Box Sync] SHOULDERS_REFRESHED: current Worker pose, after approach.')

    def follow_transfer(self, transfer, forward_yaw, yaw_rate):
        if transfer is None:
            raise ValueError('Synchronized reach requires BoxTransfer')
        follow_yaw(0, 0, 0, yaw_rate)
        if not math.isfinite(forward_yaw):
            raise ValueError('Invalid Worker forward axis')
        self.transfer, self.forward_yaw, self.yaw_rate = transfer, forward_yaw, yaw_rate

    def start(self, now, character, pose, target):
        if self.transfer.state != 'waiting':
            raise RuntimeError('Start BoxTransfer before synchronized reach')
        self.character, self.started, self.done = character, now, False
        self.position = tuple(pose[0])
        self.yaw = math.degrees(2 * math.atan2(pose[1][2], pose[1][3]))
        self.last_time = now
        self.loaded_at = None
        self.release_targets = None
        self.height_warning = False
        self.height_offsets = {'left': 0., 'right': 0.}
        self.height_feedback_report = {}
        self.initial_distance = max(.01, math.dist(self.position[:2], target[:2]))
        self.update(now)
        print('[Worker Box Sync] RAISING: follow box height, then pull/turn/lower; visual-only.')

    def update(self, now):
        import carb
        from scripts.warehouse_worker_cart_pose_sync import compose_pose
        from scripts.warehouse_worker_face_box import target_yaw
        if self.started is None:
            return
        if not math.isfinite(now) or now < self.last_time:
            raise RuntimeError('Unexpected timeline jump; Stop and restart the scenario')
        dt = now - self.last_time
        self.last_time = now
        state = self.transfer.state
        if state not in ('waiting', 'moving', 'loaded'):
            raise RuntimeError('Box transfer not active; synchronized reach refused')
        box = self.transfer.current_center
        walking_pose=getattr(self,'walking_pose',None)
        if walking_pose is not None:
            self.position=tuple(walking_pose[0])
            self.yaw=math.degrees(2*math.atan2(walking_pose[1][2],walking_pose[1][3]))
        if walking_pose is None and math.dist(self.position[:2], box[:2]) > .01 and self.loaded_at is None:
            desired = target_yaw(self.position, box, self.forward_yaw)
            self.yaw = follow_yaw(self.yaw, desired, dt, self.yaw_rate)
        angle = math.radians(self.yaw) / 2
        rotation = (0, 0, math.sin(angle), math.cos(angle))
        if walking_pose is None:
            self.character.set_world_transform(carb.Float3(*self.position), carb.Float4(*rotation))
        origins = {side: compose_pose((self.position, rotation), (p, (0,0,0,1)))[0]
                   for side, p in self.shoulders.items()}
        # Inward motion of the box shortens horizontal extension; heights stay independent.
        extension = min(1, math.dist(self.position[:2], box[:2]) / self.initial_distance)
        hand_target = (
            box[0],
            box[1],
            box[2] + getattr(self, "hand_height_offset", 0.0),
        )

        points = {
            side: height_matched_target(
                p,
                hand_target,
                self.distance * extension,
                self.arm_lengths[side] * 0.9,
            )
            for side, p in origins.items()
        }
        if not self.height_warning and any(abs(p[2] - hand_target[2]) > .01 for p in points.values()):
            self.height_warning = True
            for side, point in points.items():
                direction = height_limit_direction(point[2], hand_target[2])
                if direction:
                    print(f'[Worker Box Sync] HEIGHT_LIMITED: side={side}, box={direction}, '
                          f'box_z={box[2]:.4f}, target_z={point[2]:.4f}; no bone stretching.')
        if state == 'loaded' and self.loaded_at is None:
            self.loaded_at = now
            self.release_targets = points
            print('[Worker Box Sync] RELEASING: box loaded; lowering arms to sides.')
        if self.loaded_at is not None:
            t = max(0, min(1, (now - self.loaded_at) / self.lower))
            blend = t*t*(3-2*t)
            for side, shoulder in origins.items():
                neutral = (shoulder[0], shoulder[1], shoulder[2] - self.arm_lengths[side] * .9)
                points[side] = tuple(self.release_targets[side][i] * (1-blend) + neutral[i] * blend
                                     for i in range(3))
            weight = 1.0
            if t >= 1 and not self.done:
                self.done = True
                print('[Worker Box Sync] ATTENTION: arms down; Cart remains parked.')
        else:
            t = max(0, min(1, (now - self.started) / self.reach))
            weight = t*t*(3-2*t)
        if (getattr(self, 'feedback_enabled', False) and weight >= .999
                and self.loaded_at is None):
            for side, name in [('left', 'LeftHand'), ('right', 'RightHand')]:
                p, q = carb.Float3(float('nan'),float('nan'),float('nan')), carb.Float4(0,0,0,1)
                result = self.character.get_joint_transform(name, p, q)
                measured = (p.x,p.y,p.z)
                if (result is False or not all(math.isfinite(v) for v in measured)
                        or math.dist(measured, origins[side]) > self.arm_lengths[side] * 1.2):
                    raise RuntimeError(f'Invalid runtime hand measurement: {name}; inspect rig')
                desired = points[side][2]
                self.height_offsets[side] = height_feedback_step(self.height_offsets[side], desired, p.z,
                    dt, self.feedback_limit, self.feedback_response)
                requested = (*points[side][:2], desired + self.height_offsets[side])
                points[side] = height_matched_target(origins[side], requested, self.distance * extension,
                                                     self.arm_lengths[side] * .9)
                self.height_feedback_report[side] = dict(box_z=box[2], desired_z=desired,
                    measured_z=p.z, command_z=points[side][2], offset=self.height_offsets[side])
        for side, point in points.items():
            self.character.set_variable('WarehouseReach' + side.title() + 'Target', carb.Float3(*point))
        self.character.set_variable('WarehouseReachWeight', float(weight))
        values = self.character.get_variable('WarehouseReachWeight')
        if not values or abs(float(values[0]) - weight) > 1e-4:
            raise RuntimeError('Synchronized IK variable not accepted')
