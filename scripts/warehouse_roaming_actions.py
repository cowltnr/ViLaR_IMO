"""Isaac Sim adapter for post-loading roaming. No automatic Play/Bake/Save."""
import math
from uuid import uuid4
from scripts import warehouse_roaming_config as cfg
from scripts.warehouse_roaming_geometry import (
    footprint_grid,footprint_world,route_poses,pose_at,yaw_degrees,
)
from scripts.warehouse_worker_cart_pose_sync import compose_pose
from scripts.warehouse_worker_reach_gesture import follow_yaw
from scripts.warehouse_worker_face_box import target_yaw
from scripts.configure_warehouse_worker_behavior import validate_destination_path
from scripts.warehouse_roaming_cargo import CargoFollower


class OwnedPeopleCommand:
    def __init__(self,behavior):
        self.behavior=behavior
        self.key=None
        self.outcome=None

    def send(self,goal,yaw):
        if self.behavior.commands or self.behavior.current_command is not None:
            raise RuntimeError('People queue is not idle; refusing to override another command')
        self.key='warehouse_roaming_'+uuid4().hex
        self.outcome=None
        command='Worker_01 GoTo %.5f %.5f %.5f %.5f' % (*goal,yaw)
        self.behavior.inject_command([(self.key,command)],executeImmediately=False)

    def on_event(self,event):
        if self.key and event.payload.get('command_id','')==self.key:
            self.outcome=event.payload.get('status','')

    def complete(self):
        current=self.behavior.current_command
        if any(pair[0]==self.key for pair in self.behavior.commands) or (
                current is not None and getattr(current,'command_id',None)==self.key):
            return False
        if self.key is None:
            return True
        # People removes the command before the message-bus pop callback runs.
        # Await that event; LoadedCartRoaming already bounds this wait by timeout.
        if self.outcome is None:
            return False
        if self.outcome!='default':
            raise RuntimeError('Owned GoTo ended without successful completion: '+str(self.outcome))
        return True

    def cancel(self):
        current=self.behavior.current_command
        if self.key and current is not None and getattr(current,'command_id',None)==self.key:
            self.behavior.end_current_command(set_status=True)
            # force_quit leaves a finished object for execute_command to pop.
            # We remove our queue entry here, so also release that exact object.
            if self.behavior.current_command is current:
                self.behavior.current_command=None
        if self.key:
            self.behavior.commands[:]=[p for p in self.behavior.commands if p[0]!=self.key]
        self.key=None


class IsaacRoamingActions:
    def __init__(self,owner):
        import carb.events
        import omni.kit.app
        from omni.anim.people.settings import AgentEvent
        from omni.anim.people.scripts.utils import Utils
        self.owner,self.sync,self.stage=owner,owner.sync,owner.stage
        self.dock=owner.parking_worker_pose
        if self.dock is None or not all(t.state=='loaded' for t in owner.sequence.transfers):
            raise RuntimeError('Roaming requires captured dock pose and all boxes loaded')
        behavior=Utils.fetch_target_character_instance_by_name('Worker_01')
        if behavior is None:
            raise RuntimeError('Worker People behavior unavailable')
        self.command=OwnedPeopleCommand(behavior)
        self.event_sub=omni.kit.app.get_app().get_message_bus_event_stream().create_subscription_to_pop_by_type(
            carb.events.type_from_string(AgentEvent.CommandEndEvent),self.command.on_event,
            name='WarehouseRoamingCommandEnd')
        self.cargo=CargoFollower(self.stage,owner.config.CART_PATH,
                                [t.box_path for t in owner.sequence.transfers])
        self.phase='idle'
        self.last_time=owner.timeline.get_current_time()
        self.guard_error=None
        self.last_safe=None
        self.guard_callback=self._guard_motion
        self.cart_points=()

    def worker_position(self):
        return self.sync._read_worker_pose()[0]

    def _closest(self,point):
        import carb
        import omni.anim.navigation.core as nav
        mesh=nav.acquire_interface().get_navmesh()
        if mesh is None:
            raise RuntimeError('NavMesh unavailable; roaming stopped')
        hit=mesh.query_closest_point(carb.Float3(*point))
        return tuple(float(hit[k]) for k in range(3)) if hit is not None else None

    def _worker_path(self,goal):
        import carb
        import omni.anim.navigation.core as nav
        start=self.worker_position()
        snap=self._closest(start)
        if snap is None or math.dist(snap,start)>cfg.MAX_NAVMESH_SNAP_M:
            raise RuntimeError('Worker is outside NavMesh')
        route=nav.acquire_interface().get_navmesh().query_shortest_path(
            start_pos=carb.Float3(*snap),end_pos=carb.Float3(*goal))
        points=[tuple(float(p[k]) for k in range(3)) for p in route.get_points()] if route else []
        validate_destination_path(points,snap,goal)
        return points

    def _set_pose(self,pose):
        import carb
        self.sync._character.set_world_transform(carb.Float3(*pose[0]),carb.Float4(*pose[1]))

    def _align(self,desired):
        now=self.owner.timeline.get_current_time()
        dt=max(0.,min(.1,now-self.last_time))
        self.last_time=now
        pose=self.sync._read_worker_pose()
        yaw=follow_yaw(yaw_degrees(pose),desired,dt,cfg.ALIGN_RATE_DEG_S)
        proposed=pose_at(pose[0],yaw)
        if self.phase=='move_turn' and not self._guard_motion(proposed,compose_pose(proposed,self.relative)):
            raise RuntimeError(self.guard_error)
        self._set_pose(proposed)
        return abs((desired-yaw+180)%360-180)<.1

    def begin_return(self):
        self.sync.hold()
        if self.owner.gesture is not None:
            self.owner.gesture.reset()
        self.phase='dock_turn'
        if math.dist(self.worker_position(),self.dock[0])>cfg.DOCK_POSITION_TOLERANCE_M:
            self._worker_path(self.dock[0])
            self.command.send(self.dock[0],yaw_degrees(self.dock))
            self.phase='dock_walk'

    def return_complete(self):
        if self.phase=='dock_walk':
            if not self.command.complete():
                return False
            self.phase='dock_turn'
        if math.dist(self.worker_position(),self.dock[0])>cfg.DOCK_POSITION_TOLERANCE_M:
            raise RuntimeError('Worker return position outside docking tolerance')
        return self._align(yaw_degrees(self.dock))

    def attach_loaded_boxes(self):
        self.cargo.attach()
        try:
            self._capture_footprint()
        except BaseException:
            self.cargo.restore()
            raise

    def _capture_footprint(self):
        from pxr import Usd,UsdGeom,Gf
        inverse=self.cargo.matrix(self.owner.config.CART_PATH).GetInverse()
        cache=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render','proxy'])
        xy=[]
        for path in (self.owner.config.CART_PATH,*self.cargo.box_paths):
            r=cache.ComputeWorldBound(self.stage.GetPrimAtPath(path)).ComputeAlignedRange()
            if r.IsEmpty():
                raise RuntimeError('Loaded cart bounds unavailable')
            for x in (r.GetMin()[0],r.GetMax()[0]):
                for y in (r.GetMin()[1],r.GetMax()[1]):
                    point=inverse.Transform(Gf.Vec3d(x,y,r.GetMin()[2]))
                    xy.append((point[0],point[1]))
        low=tuple(min(p[k] for p in xy) for k in (0,1))
        high=tuple(max(p[k] for p in xy) for k in (0,1))
        self.cart_points=footprint_grid(low,high,cfg.FOOTPRINT_GRID_M)

    def _pose_safe(self,worker):
        cart=compose_pose(worker,self.relative)
        points=[worker[0],*[(p[0],p[1],worker[0][2]) for p in footprint_world(cart,self.cart_points)]]
        for point in points:
            hit=self._closest(point)
            if hit is None or math.dist(point,hit)>cfg.FOOTPRINT_SNAP_M:
                self.last_guard_reason={
                    'kind': 'footprint_off_navmesh' if hit is not None else 'navmesh_query_none',
                    'point': tuple(point),
                    'closest': tuple(hit) if hit is not None else None,
                    'distance': math.dist(point,hit) if hit is not None else None,
                    'threshold': cfg.FOOTPRINT_SNAP_M,
                }
                return False
        return True

    def resume_cart(self):
        self.sync.resume(self.dock,cfg.DOCK_POSITION_TOLERANCE_M,cfg.DOCK_ANGLE_TOLERANCE_DEG)
        self.relative=self.sync.relative_transform
        self.last_safe=self.sync._read_worker_pose()
        if not self._pose_safe(self.last_safe):
            self.sync.hold()
            raise RuntimeError('Loaded Cart footprint is outside existing NavMesh; inspect parking area')
        self.sync._controller.motion_guard=self.guard_callback
        self.phase='idle'

    def route_check_steps(self,points):
        self.last_guard_reason=None
        start=self.sync._read_worker_pose()
        if not points or math.dist(points[0],start[0])>cfg.MAX_NAVMESH_SNAP_M:
            self.last_guard_reason={'kind':'route_start_mismatch','route_start':points[0] if points else None,
                                    'worker_start':start[0]}
            return False
        for index,pose in enumerate(route_poses(points,yaw_degrees(start),self.owner.forward_yaw,
                                               cfg.PATH_SAMPLE_M,cfg.TURN_SAMPLE_DEG)):
            if index>=cfg.MAX_GUARD_POSES or not self._pose_safe(pose):
                if self.last_guard_reason is None:
                    self.last_guard_reason={'kind':'guard_pose_limit','index':index}
                return False
            yield None
        directions=[target_yaw(a,b,self.owner.forward_yaw) for a,b in zip(points,points[1:])
                    if math.dist(a[:2],b[:2])>1e-6]
        if not directions:
            self.last_guard_reason={'kind':'route_has_no_direction'}
            return False
        self.checked_goal=tuple(points[-1])
        self.checked_first_yaw,self.checked_last_yaw=directions[0],directions[-1]
        return True

    def _guard_motion(self,worker,cart):
        if self.guard_error:
            return False
        if worker==self.last_safe:
            return True
        previous=self.last_safe
        distance=math.dist(previous[0],worker[0])
        delta=(yaw_degrees(worker)-yaw_degrees(previous)+180)%360-180
        if distance>cfg.MAX_RUNTIME_STEP_M or abs(delta)>cfg.MAX_RUNTIME_TURN_DEG:
            self.guard_error='Unexpected Worker pose jump'
        else:
            n=max(1,math.ceil(distance/cfg.PATH_SAMPLE_M),math.ceil(abs(delta)/cfg.TURN_SAMPLE_DEG))
            for i in range(1,n+1):
                p=tuple(previous[0][k]+(worker[0][k]-previous[0][k])*i/n for k in range(3))
                if not self._pose_safe(pose_at(p,yaw_degrees(previous)+delta*i/n)):
                    self.guard_error='Worker/loaded Cart left sampled NavMesh clearance'
                    break
        if self.guard_error:
            self._set_pose(previous)
            return False
        self.last_safe=worker
        return True

    def begin_move(self,goal):
        if math.dist(goal,self.checked_goal)>1e-5:
            raise RuntimeError('Movement goal differs from checked route')
        self.move_goal=tuple(goal)
        self.move_yaw=self.checked_first_yaw
        self.phase='move_turn'
        self.last_time=self.owner.timeline.get_current_time()

    def move_complete(self,goal):
        if self.phase=='move_turn':
            if self._align(self.move_yaw):
                self.command.send(goal,self.checked_last_yaw)
                self.phase='move_walk'
            return False
        if not self.command.complete():
            return False
        if math.dist(self.worker_position(),goal)>cfg.ARRIVAL_TOLERANCE_M:
            raise RuntimeError('GoTo completion outside goal tolerance')
        self.phase='idle'
        return True

    def update_loaded_boxes(self):
        if self.guard_error:
            raise RuntimeError(self.guard_error)
        # Explicit order removes dependence on update subscription ordering.
        self.sync._controller.update()
        self.cargo.update()

    def stop_owned_motion(self):
        try:
            self.command.cancel()
        finally:
            if self.sync._controller.motion_guard==self.guard_callback:
                self.sync._controller.motion_guard=None
            if self.owner.timeline.is_playing() and self.sync.relative_transform is not None:
                self.sync.hold()
            self.event_sub=None

    def restore_loaded_boxes(self):
        self.cargo.restore()
