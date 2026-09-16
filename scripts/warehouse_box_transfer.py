"""Visual-only box transfer in an owned, removable session sublayer."""

import itertools
import math


def placement_center(lower, upper, box_size, margin, gap):
    if (not all(math.isfinite(v) for v in (*lower, *upper, *box_size, margin, gap))
            or margin < 0 or gap < 0 or any(v <= 0 for v in box_size)
            or any(upper[i] <= lower[i] for i in range(3))):
        raise ValueError("Invalid pallet or box dimensions")
    if any(box_size[i] + 2 * margin > upper[i] - lower[i] for i in (0, 1)):
        raise ValueError("Box does not fit on selected Pallet; transfer refused")
    return ((lower[0] + upper[0]) / 2, (lower[1] + upper[1]) / 2,
            upper[2] + box_size[2] / 2 + gap)


def transfer_points(source, destination, worker, rack_min, rack_max, box_size,
                    margin, clearance, max_pull, max_center_height=None):
    values = (*source, *destination, *worker, *rack_min, *rack_max,
              *box_size, margin, clearance, max_pull)
    if not all(math.isfinite(v) for v in values) or min(margin, clearance) < 0 or max_pull <= 0:
        raise ValueError("Invalid transfer path inputs")
    direction = (worker[0] - source[0], worker[1] - source[1])
    length = math.hypot(*direction)
    if length < 1e-6:
        raise ValueError("Worker must be horizontally outside the box position")
    direction = tuple(v / length for v in direction)
    lower = tuple(rack_min[i] - box_size[i] / 2 - margin for i in (0, 1))
    upper = tuple(rack_max[i] + box_size[i] / 2 + margin for i in (0, 1))
    if all(lower[i] <= source[i] <= upper[i] for i in (0, 1)):
        exits = [( (upper[i] if direction[i] > 0 else lower[i]) - source[i]) / direction[i]
                 for i in (0, 1) if abs(direction[i]) > 1e-9]
        distance = min(exits)
    else:
        raise ValueError("Box is not within selected rack footprint; verify rack target")
    if distance > max_pull:
        raise ValueError("Rack extraction exceeds configured maximum; inspect geometry")
    pull = (source[0] + distance * direction[0], source[1] + distance * direction[1], source[2])
    height = max(source[2], destination[2]) + clearance
    if max_center_height is not None:
        if not math.isfinite(max_center_height):
            raise ValueError("Invalid arm height limit")
        if height > max_center_height + 1e-6:
            raise ValueError(f"Box path center height {height:.3f} m exceeds arm limit "
                             f"{max_center_height:.3f} m; transfer refused before moving")
    return [tuple(source), pull, (pull[0], pull[1], height),
            (destination[0], destination[1], height), tuple(destination)]


def sample_path(points, fraction):
    if not math.isfinite(fraction) or len(points) < 2:
        raise ValueError("Invalid path sampling input")
    progress = max(0, min(1, fraction)) * (len(points) - 1)
    index = min(int(progress), len(points) - 2)
    t = progress - index
    t = t * t * (3 - 2 * t)
    return tuple(points[index][i] * (1 - t) + points[index + 1][i] * t for i in range(3))


class BoxTransfer:
    """No callbacks: FaceBoxRuntime owns scheduling and cleanup."""

    OP = "xformOp:transform:warehouseBoxTransfer"
    path_builder = staticmethod(transfer_points)

    def __init__(self, stage, box_path, pallet_path, rack_path, *, delay, duration,
                 edge_margin, gap, pull_margin, lift_clearance, max_pull,
                 max_center_height_offset=None):
        from pxr import UsdGeom, UsdPhysics, Usd
        self.stage = stage
        self.box_path, self.pallet_path, self.rack_path = box_path, pallet_path, rack_path
        self.delay, self.duration = delay, duration
        self.edge_margin, self.gap = edge_margin, gap
        self.pull_margin, self.lift_clearance, self.max_pull = pull_margin, lift_clearance, max_pull
        if max_center_height_offset is not None and not math.isfinite(max_center_height_offset):
            raise ValueError("Invalid Worker-relative arm height limit")
        self.max_center_height_offset = max_center_height_offset
        if (not all(math.isfinite(v) for v in (delay, duration, edge_margin, gap,
                                              pull_margin, lift_clearance, max_pull))
                or min(delay, edge_margin, gap, pull_margin, lift_clearance) < 0
                or min(duration, max_pull) <= 0):
            raise ValueError("Invalid transfer timing or clearance")
        self.layer = None
        self.state = "ready"
        for path in (box_path, pallet_path, rack_path):
            prim = stage.GetPrimAtPath(path)
            if not prim or not prim.IsValid() or not UsdGeom.Xformable(prim):
                raise RuntimeError(f"Transfer prim missing/not transformable: {path}")
        self.box = stage.GetPrimAtPath(box_path)
        if self.box.IsInstanceProxy() or self.box.IsInstance():
            raise RuntimeError("Instanced box is unsupported; transfer will not edit shared assets")
        prims = list(Usd.PrimRange(self.box))
        parent = self.box.GetParent()
        while parent and not parent.IsPseudoRoot():
            prims.append(parent)
            parent = parent.GetParent()
        for prim in prims:
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                if UsdPhysics.RigidBodyAPI(prim).GetRigidBodyEnabledAttr().Get() is not False:
                    raise RuntimeError(f"Active rigid body in Box hierarchy unsupported: {prim.GetPath()}")
        if UsdGeom.Xformable(self.box).TransformMightBeTimeVarying():
            raise RuntimeError("Animated box transform is unsupported")
        session_prim = stage.GetSessionLayer().GetPrimAtPath(box_path)
        if session_prim and any(p.name == "xformOpOrder" or p.name.startswith("xformOp:")
                                for p in session_prim.properties):
            raise RuntimeError("Existing session Box transform found; preserve it and refuse transfer")
        self._geometry()  # Read-only size/fit precheck before Play.

    def _geometry(self):
        from pxr import Usd, UsdGeom, Gf
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                                  [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy])
        box_range = cache.ComputeWorldBound(self.box).ComputeAlignedRange()
        pallet = self.stage.GetPrimAtPath(self.pallet_path)
        pallet_range = cache.ComputeUntransformedBound(pallet).ComputeAlignedRange()
        rack_range = cache.ComputeWorldBound(self.stage.GetPrimAtPath(self.rack_path)).ComputeAlignedRange()
        if any(r.IsEmpty() for r in (box_range, pallet_range, rack_range)):
            raise RuntimeError("Box/Pallet/Rack geometry is not loaded")
        matrix = UsdGeom.Xformable(pallet).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        if any(abs(sum(float(matrix[i][j])**2 for j in range(3)) - 1) > 1e-3 for i in range(3)):
            raise RuntimeError("Scaled Pallet frame unsupported for meter clearances")
        inverse = matrix.GetInverse()
        corners = [inverse.Transform(Gf.Vec3d(*p)) for p in itertools.product(
            *[(box_range.GetMin()[i], box_range.GetMax()[i]) for i in range(3)])]
        size = tuple(max(p[i] for p in corners) - min(p[i] for p in corners) for i in range(3))
        local = placement_center(tuple(pallet_range.GetMin()), tuple(pallet_range.GetMax()),
                                 size, self.edge_margin, self.gap)
        destination = tuple(matrix.Transform(Gf.Vec3d(*local)))
        return (tuple(box_range.GetMidpoint()), destination,
                tuple(rack_range.GetMin()), tuple(rack_range.GetMax()), tuple(box_range.GetSize()))

    def start(self, now, worker_position):
        from pxr import Usd, UsdGeom
        if self.state != "ready":
            raise RuntimeError("Box transfer is already started")
        source, destination, rack_min, rack_max, size = self._geometry()
        self.points = self.path_builder(source, destination, worker_position, rack_min, rack_max,
                                      size, self.pull_margin, self.lift_clearance, self.max_pull,
                                      max_center_height=(worker_position[2] + self.max_center_height_offset
                                                         if self.max_center_height_offset is not None else None))
        print(f"[Box Transfer] HEIGHT: path_max={max(p[2] for p in self.points):.3f} m, "
              f"clearance={self.lift_clearance:.3f} m, arm_limit="
              f"{worker_position[2] + self.max_center_height_offset if self.max_center_height_offset is not None else None}")
        self.source = source
        self.current_center = source
        self.original_world = UsdGeom.Xformable(self.box).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        self.start_time = now + self.delay
        self.state = "waiting"
        print(f"[Box Transfer] READY: source={source}, destination={destination}; visual-only")

    def update(self, now):
        from pxr import Sdf, Usd, UsdGeom, UsdPhysics, Gf, Vt
        if self.state in ("ready", "loaded") or now < self.start_time:
            return
        try:
            if self.layer is None:
                self.layer = Sdf.Layer.CreateAnonymous("warehouse_box_transfer.usda")
                session = self.stage.GetSessionLayer()
                session.subLayerPaths = [self.layer.identifier, *session.subLayerPaths]
                with Usd.EditContext(self.stage, self.layer):
                    self.box.CreateAttribute("xformOpOrder", Sdf.ValueTypeNames.TokenArray).Set(
                        Vt.TokenArray(["!resetXformStack!", self.OP]))
                    self.box.CreateAttribute(self.OP, Sdf.ValueTypeNames.Matrix4d)
                    # This is visual-only; disable only this box's own collision shapes.
                    for prim in Usd.PrimRange(self.box):
                        if prim.HasAPI(UsdPhysics.CollisionAPI):
                            UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Set(False)
                self.state = "moving"
                print("[Box Transfer] MOVING")
            fraction = (now - self.start_time) / self.duration
            center = sample_path(self.points, fraction)
            matrix = Gf.Matrix4d(self.original_world)
            origin = self.original_world.ExtractTranslation()
            matrix.SetTranslateOnly(Gf.Vec3d(*(origin[i] + center[i] - self.source[i] for i in range(3))))
            with Usd.EditContext(self.stage, self.layer):
                if not self.box.GetAttribute(self.OP).Set(matrix):
                    raise RuntimeError("Could not author Box runtime transform")
            self.current_center = center
            if fraction >= 1:
                self.state = "loaded"
                print(f"[Box Transfer] LOADED: Box on {self.pallet_path}; Stop restores shelf position.")
        except BaseException:
            self.restore()
            raise

    def restore(self):
        if self.layer is not None:
            session = self.stage.GetSessionLayer()
            session.subLayerPaths = [p for p in session.subLayerPaths if p != self.layer.identifier]
            self.layer = None
        self.state = "ready"
