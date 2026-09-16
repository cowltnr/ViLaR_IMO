"""Manual visual unloading controller. Owns callbacks and temporary box layers."""
import math

from scripts.warehouse_box_transfer import BoxTransfer, transfer_points
from scripts.warehouse_worker_face_box import matches_arrival, target_yaw, turn_yaw, box_center


def restore_transfers(transfers):
    errors = []
    for transfer in transfers:
        try:
            transfer.restore()
        except Exception as error:
            errors.append(str(error))
    return errors


def attention_targets(pose, shoulders, lengths):
    from scripts.warehouse_worker_cart_pose_sync import compose_pose
    return {side: compose_pose(pose, ((p[0],p[1],p[2]-lengths[side]*.9),
                                      (0,0,0,1)))[0]
            for side,p in shoulders.items()}


def path_collisions(points, size, obstacles):
    """Continuous translating AABB test against explicitly supplied obstacles.

    Allows contact without penetration; not a full warehouse/mesh collision test.
    """
    hits = []
    for name,lower,upper in obstacles:
        low = tuple(lower[k]-size[k]/2+1e-6 for k in range(3))
        high = tuple(upper[k]+size[k]/2-1e-6 for k in range(3))
        for a,b in zip(points,points[1:]):
            enter,leave = 0.,1.
            for k in range(3):
                d = b[k]-a[k]
                if abs(d)<1e-12:
                    if not low[k]<a[k]<high[k]:
                        enter,leave = 1.,0.
                        break
                else:
                    t0,t1 = sorted(((low[k]-a[k])/d,(high[k]-a[k])/d))
                    enter,leave = max(enter,t0),min(leave,t1)
            if enter < leave:
                hits.append(name)
                break
    return tuple(hits)


def pallet_transfer_points(source, destination, worker, support_min, support_max,
                           box_size, margin, clearance, max_pull, max_center_height=None):
    """Visual extraction: lift clear of the direct support before moving sideways.

    Does not certify clearance from neighboring boxes or warehouse obstacles.
    """
    raised = (*source[:2], max(source[2], support_max[2] + box_size[2]/2) + clearance)
    # Extract square to the support face toward the worker. A diagonal pull
    # toward an offset worker can sweep into the adjacent source stack before
    # clearing the support. Preserve the orthogonal source coordinate first.
    axis = max((0,1),key=lambda k: abs(worker[k]-source[k]))
    extraction_target = list(source)
    extraction_target[axis] = worker[axis]
    points = transfer_points(raised, destination, extraction_target, support_min, support_max,
                             box_size, margin, 0, max_pull, max_center_height)
    # Preserve destination approach clearance without increasing the source lift twice.
    height = max(raised[2], destination[2] + clearance)
    if max_center_height is not None and height > max_center_height + 1e-6:
        raise ValueError('Pallet transfer exceeds arm height limit')
    points[2] = (*points[2][:2], height)
    points[3] = (*points[3][:2], height)
    return [tuple(source), *points]


class PlacedTransfer(BoxTransfer):
    path_builder = staticmethod(pallet_transfer_points)
    def relocate(self, destination, now, duration, delay):
        if self.state != 'loaded' or self.layer is None:
            raise RuntimeError('Only owned loaded cargo can slide')
        if (not all(math.isfinite(v) for v in (*destination, now, duration, delay))
                or duration <= 0 or delay < 0):
            raise ValueError('Invalid slide timing or target')
        self.points = [tuple(self.current_center), tuple(destination)]
        self.duration, self.start_time = duration, now + delay
        self.state = 'waiting'

    def __init__(self, *args, destination, **kwargs):
        self.destination = destination
        super().__init__(*args, **kwargs)

    def _geometry(self):
        source, _, low, high, size = super()._geometry()
        return source, self.destination, low, high, size


class Unloading:
    def __init__(self, sync, stage, gesture, config, expected, worker_goal, cart_goal):
        import carb.events
        import omni.kit.app
        import omni.timeline
        from omni.anim.people.settings import AgentEvent
        self.sync, self.stage, self.gesture, self.config = sync, stage, gesture, config
        self.expected, self.goal, self.cart_goal = expected, worker_goal, cart_goal
        self.timeline = omni.timeline.get_timeline_interface()
        self.state = 'parking'
        self.loaded, self.transfers = [], []
        self.index, self.pending = 0, False
        self.return_pose = None
        self.transfer = None
        self.reason = None
        self.slide = None
        self.relocations = 0
        self.full_plan = None
        self.retreats = 0
        self.walking_carry=None
        app = omni.kit.app.get_app()
        self.command_sub = app.get_message_bus_event_stream().create_subscription_to_pop_by_type(
            carb.events.type_from_string(AgentEvent.CommandEndEvent), self.on_command,
            name='MultiBoxCommand')
        self.update_sub = app.get_update_event_stream().create_subscription_to_pop(self.update, name='MultiBoxUpdate')
        self.stop_sub = self.timeline.get_timeline_event_stream().create_subscription_to_pop(self.on_stop)

    def on_command(self, event):
        if self.timeline.is_playing() and self.state in ('parking', 'approaching', 'returning','walking_load'):
            if matches_arrival(event.payload, self.expected):
                self.pending = True

    def move(self, goal, state, heading='_'):
        import carb
        import omni.anim.navigation.core as nav
        from omni.anim.people.scripts.utils import Utils
        from scripts.configure_warehouse_worker_behavior import validate_destination_path
        mesh = nav.acquire_interface().get_navmesh()
        if mesh is None:
            raise RuntimeError('NavMesh missing')
        start = self.sync._read_worker_pose()[0]
        snapped = mesh.query_closest_point(carb.Float3(*goal))
        if snapped is None or math.dist(tuple(snapped), goal) > self.config.MAX_NAVMESH_SNAP_M:
            raise RuntimeError('Goal outside NavMesh')
        goal = tuple(snapped)
        if math.dist(start, goal) <= .05:
            self.goal, self.state, self.pending = goal, state, True
            self.move_started = self.timeline.get_current_time()
            return
        path = mesh.query_shortest_path(start_pos=carb.Float3(*start), end_pos=carb.Float3(*goal))
        validate_destination_path(list(path.get_points()) if path else [], start, goal)
        person = Utils.fetch_target_character_instance_by_name('Worker_01')
        if person is None or person.current_command is not None or person.commands:
            raise RuntimeError('Worker command queue is occupied; no command overwritten')
        self.expected = 'Worker_01 GoTo %.5f %.5f %.5f %s' % (*goal, heading)
        person.inject_command([self.expected], executeImmediately=False)
        self.goal, self.state = goal, state
        self.move_started = self.timeline.get_current_time()

    def plan_next(self):
        from pxr import Usd, UsdGeom
        from scripts.warehouse_multi_box_inspection import collect_lid_meshes
        from scripts.warehouse_composite_support import (lid_surfaces_from_mesh_report,
            plan_with_slides, plan_full_load, CompositePlan)
        if self.index >= len(self.config.BOX_PATHS):
            self.begin_return('all_loaded')
            return
        self.box = self.config.BOX_PATHS[self.index]
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default', 'render', 'proxy'])
        bounds = cache.ComputeWorldBound(self.stage.GetPrimAtPath(self.box)).ComputeAlignedRange()
        surfaces = lid_surfaces_from_mesh_report(collect_lid_meshes(self.stage, self.config.PALLET_PATH),
                                                verified_ids=self.config.COMPOSITE_VERIFIED_LID_PATHS)
        # Height is limited using the existing authored rig reach, never an arbitrary 3m ceiling.
        limit = self.sync._read_worker_pose()[0][2] + min(
            self.gesture.shoulders[s][2] + self.gesture.arm_lengths[s] * .9 * .95
            for s in self.gesture.shoulders)
        size = tuple(bounds.GetSize())
        policy = dict(
            max_gap=self.config.COMPOSITE_MAX_GAP_M,
            max_height_delta=self.config.COMPOSITE_MAX_HEIGHT_DELTA_M,
            min_coverage=self.config.COMPOSITE_MIN_COVERAGE,
            edge_margin=self.config.EDGE_MARGIN_M, placement_gap=self.config.PLACEMENT_GAP_M)
        if self.config.USE_FULL_LOAD_PLAN:
            if self.full_plan is None:
                boxes = []
                for path in self.config.BOX_PATHS:
                    r = cache.ComputeWorldBound(self.stage.GetPrimAtPath(path)).ComputeAlignedRange()
                    if r.IsEmpty():
                        raise RuntimeError('Box geometry unavailable: ' + path)
                    boxes.append((path,tuple(r.GetSize())))
                self.full_plan = plan_full_load(boxes,surfaces,max_center_height=limit,
                    worker_position=self.return_pose[0],
                    stack_second_on_first=getattr(self.config,'STACK_SECOND_ON_FIRST',False),
                    clearance=self.config.LIFT_CLEARANCE_M,
                    max_states=self.config.MAX_SEARCH_STATES,**policy)
                print('[Multi-box] FULL_PLAN:',self.full_plan.reason,
                      'planned=',len(self.full_plan.placements),'of=',len(boxes))
            if self.index >= len(self.full_plan.placements):
                self.begin_return('no_valid_load_plan:' + self.full_plan.reason)
                return
            planned = self.full_plan.placements[self.index]
            if planned.box_id != self.box or any(abs(a-b)>1e-5 for a,b in zip(planned.bounds.size,size)):
                raise RuntimeError('Box geometry changed after full-load planning')
            plan = CompositePlan(planned,(),tuple(self.loaded))
        else:
            plan = plan_with_slides(self.box, size, surfaces, self.loaded,
            max_relocations=max(0, self.config.MAX_RELOCATIONS-self.relocations),
            max_states=self.config.MAX_SEARCH_STATES,
            max_top=limit + size[2]/2 - self.config.LIFT_CLEARANCE_M,**policy)
        if plan is None:
            self.begin_return('no_valid_load_plan')
            return
        if plan.slides:
            self.slide = plan.slides[0]
            self.transfer = next((t for t in self.transfers if t.box_path == self.slide.box_id), None)
            if self.transfer is None:
                raise RuntimeError('Slide target is not owned cargo')
            self.target = self.transfer.current_center
            self.gesture.reset()
            self.move(self.return_pose[0], 'approaching')
            return
        placement = plan.placement
        self.placement = placement
        self.target = box_center(self.stage, self.box)
        support = self.config.SOURCE_SUPPORT_PATHS.get(self.box)
        if not support:
            self.begin_return('source_support_unresolved:' + self.box)
            return
        destination = tuple((a+b)/2 for a,b in zip(placement.bounds.lower, placement.bounds.upper))
        self.transfer = PlacedTransfer(self.stage, self.box, self.config.PALLET_PATH, support,
            destination=destination, delay=self.config.ARM_RAISE_SECONDS,
            duration=self.config.TRANSFER_SECONDS, edge_margin=self.config.EDGE_MARGIN_M,
            gap=self.config.PLACEMENT_GAP_M, pull_margin=.10,
            lift_clearance=self.config.LIFT_CLEARANCE_M, max_pull=3,
            max_center_height_offset=limit-self.sync._read_worker_pose()[0][2])
        self.transfers.append(self.transfer)
        import carb
        import omni.anim.navigation.core as nav
        from scripts.warehouse_worker_approach import select_forward_approach
        mesh = nav.acquire_interface().get_navmesh()
        def closest(p):
            result = mesh.query_closest_point(carb.Float3(*p))
            return tuple(result) if result is not None else None
        def path(a,b):
            result = mesh.query_shortest_path(start_pos=carb.Float3(*a), end_pos=carb.Float3(*b))
            return list(result.get_points()) if result else []
        goal, _ = select_forward_approach(self.sync._read_worker_pose()[0], self.target,
            closest, path, self.config.MAX_NAVMESH_SNAP_M, .05, .55)
        self.gesture.reset()
        self.move(goal, 'approaching')

    def begin_return(self, reason):
        self.reason = reason
        self.gesture.reset()
        print('[Multi-box] RETURN:', reason, 'loaded=', len(self.loaded))
        self.move(self.return_pose[0], 'returning')

    def find_work_position(self,pose,moving,obstacles):
        import carb
        import omni.anim.navigation.core as nav
        from scripts.warehouse_work_position import select_work_position
        from scripts.warehouse_oriented_clearance import OrientedBox,collisions,route_around
        mesh=nav.acquire_interface().get_navmesh()
        if mesh is None:
            return None
        def closest(p):
            result=mesh.query_closest_point(carb.Float3(*p))
            return tuple(result) if result is not None else None
        def route(a,b):
            result=mesh.query_shortest_path(start_pos=carb.Float3(*a),end_pos=carb.Float3(*b))
            return list(result.get_points()) if result else []
        source,destination,low,high,size=self.transfer._geometry()
        height=self.config.WORKER_BODY_HEIGHT_M
        radius=self.config.WORKER_BODY_RADIUS_M
        def clear_at(goal,walk):
            body=OrientedBox('WorkerBody',(goal[0],goal[1],goal[2]+height/2),
                             (radius,radius,height/2),0.)
            body_walk=[(p[0],p[1],p[2]+height/2) for p in walk]
            if collisions(body_walk,body,[moving,*obstacles]):
                return False
            if self.config.WALK_WITH_BOX:
                from scripts.warehouse_walking_carry import WalkingCarry
                heading=math.radians(target_yaw(goal,self.target,-90))/2
                candidate_pose=(goal,(0,0,math.sin(heading),math.cos(heading)))
                try:
                    WalkingCarry(self,self.timeline.get_current_time(),candidate_pose,dry_run=True)
                except (ValueError,RuntimeError):
                    return False
                return True
            try:
                points=self.transfer.path_builder(source,destination,goal,low,high,size,
                    self.transfer.pull_margin,self.transfer.lift_clearance,self.transfer.max_pull,
                    goal[2]+self.transfer.max_center_height_offset)
            except ValueError:
                return False
            return route_around(points,moving,[*obstacles,body],.05) is not None
        return select_work_position(pose[0],self.target,self.config.WORKER_REPOSITION_DISTANCES_M,
            self.config.WORKER_REPOSITION_ANGLES_DEG,closest,route,clear_at,self.config.MAX_NAVMESH_SNAP_M)

    def turn(self, target, final=False):
        self.pose = self.sync._read_worker_pose()
        self.start_yaw = math.degrees(2*math.atan2(self.pose[1][2], self.pose[1][3]))
        self.end_yaw = target
        self.turn_started = self.timeline.get_current_time()
        self.turn_duration = max(.01, abs((target-self.start_yaw+180)%360-180)/45)
        self.state = 'final_turn' if final else 'turning'

    def update(self, event):
        if not self.timeline.is_playing() or self.state in ('failed', 'done', 'stopped'):
            return
        try:
            now = self.timeline.get_current_time()
            if getattr(self,'walking_carry',None) is not None:
                self.walking_carry.update(now)
                return
            if self.pending:
                self.pending = False
                if math.dist(self.sync._read_worker_pose()[0], self.goal) > .25:
                    raise RuntimeError('Arrival outside tolerance')
                if self.state == 'parking':
                    if math.dist(self.sync._read_cart_pose()[0][:2], self.cart_goal[:2]) > .25:
                        raise RuntimeError('Cart parking outside tolerance')
                    self.sync.hold()
                    self.return_pose = self.sync._read_worker_pose()
                    self.state = 'next'
                elif self.state == 'approaching':
                    self.turn(target_yaw(self.sync._read_worker_pose()[0], self.target, -90))
                elif self.state == 'returning':
                    q = self.return_pose[1]
                    self.turn(math.degrees(2*math.atan2(q[2],q[3])), final=True)
            if self.state == 'next':
                self.plan_next()
            if self.state in ('turning', 'final_turn'):
                import carb
                fraction = (now-self.turn_started)/self.turn_duration
                yaw = math.radians(turn_yaw(self.start_yaw,self.end_yaw,fraction))/2
                self.sync._character.set_world_transform(carb.Float3(*self.pose[0]),
                    carb.Float4(0,0,math.sin(yaw),math.cos(yaw)))
                if fraction >= 1:
                    if self.state == 'final_turn':
                        points = attention_targets(self.sync._read_worker_pose(),
                            self.gesture.shoulders,self.gesture.arm_lengths)
                        for side,point in points.items():
                            self.sync._character.set_variable('WarehouseReach'+side.title()+'Target',
                                                               carb.Float3(*point))
                        self.sync._character.set_variable('WarehouseReachWeight',1.0)
                        # Keep a reference so Stop resets the final IK override.
                        self.gesture.character = self.sync._character
                        self.state = 'done'
                        print('[Multi-box] FINISHED:', self.reason, 'loaded=',len(self.loaded))
                        return
                    self.gesture.follow_transfer(self.transfer,-90,45)
                    pose = self.sync._read_worker_pose()
                    self.gesture.refresh_shoulders(self.sync._character,pose)
                    if self.slide is not None:
                        end = self.slide.end
                        destination = tuple((a+b)/2 for a,b in zip(end.lower,end.upper))
                        self.transfer.relocate(destination,now,self.config.SLIDE_SECONDS,
                                               self.config.ARM_RAISE_SECONDS)
                    else:
                        self.transfer.start(now,pose[0])
                        if self.config.WALK_WITH_BOX:
                            from scripts.warehouse_walking_carry import WalkingCarry
                            try:
                                self.walking_carry=WalkingCarry(self,now,pose)
                            except RuntimeError as error:
                                from scripts.warehouse_oriented_clearance import from_stage
                                self.transfer.restore()
                                moving=from_stage(self.stage,self.box)
                                obstacles=[from_stage(self.stage,p) for p in self.config.BOX_PATHS if p!=self.box]
                                goal=self.find_work_position(pose,moving,obstacles) if self.retreats<self.config.WORKER_MAX_RETREATS else None
                                if goal is None:
                                    self.begin_return('walking_carry_unavailable:'+str(error))
                                else:
                                    self.retreats+=1
                                    self.move(goal,'approaching')
                                    print('[Walking Carry] REPOSITION_FOR_PICKUP:',goal)
                                return
                            self.gesture.start(now,self.sync._character,pose,self.target)
                            self.state='pickup_walk'
                            return
                        from scripts.warehouse_oriented_clearance import from_stage,OrientedBox,route_around
                        moving=from_stage(self.stage,self.box)
                        obstacles=[from_stage(self.stage,p) for p in self.config.BOX_PATHS if p!=self.box]
                        body=OrientedBox('WorkerBody',
                            (pose[0][0],pose[0][1],pose[0][2]+self.config.WORKER_BODY_HEIGHT_M/2),
                            (self.config.WORKER_BODY_RADIUS_M,self.config.WORKER_BODY_RADIUS_M,
                             self.config.WORKER_BODY_HEIGHT_M/2),0.)
                        path=route_around(self.transfer.points,moving,[*obstacles,body],.05)
                        if path is None:
                            self.transfer.restore()
                            if self.retreats < self.config.WORKER_MAX_RETREATS:
                                goal=self.find_work_position(pose,moving,obstacles)
                                if goal is not None:
                                    try:
                                        self.move(goal,'approaching')
                                    except RuntimeError as error:
                                        print('[Multi-box] RETREAT_UNAVAILABLE:',error)
                                    else:
                                        self.retreats+=1
                                        print('[Multi-box] REPOSITION:',goal,'navigation and box path checked')
                                        return
                            self.begin_return('no_clear_box_path_after_retreat')
                            return
                        self.transfer.points=path
                    self.gesture.start(now,self.sync._character,pose,self.target)
                    self.state = 'carrying'
            if self.state == 'carrying':
                self.transfer.update(now)
                self.gesture.update(now)
                if self.transfer.state == 'loaded' and self.gesture.done:
                    if getattr(self, 'slide', None) is not None:
                        from scripts.warehouse_composite_support import CargoPlacement
                        self.loaded = [CargoPlacement(p.box_id,self.slide.end,p.support_ids)
                                       if p.box_id == self.slide.box_id else p for p in self.loaded]
                        self.slide = None
                        self.relocations += 1
                    else:
                        self.loaded.append(self.placement)
                        self.index += 1
                        self.relocations = 0
                        self.retreats = 0
                    self.state = 'next'
            if self.state in ('approaching','returning') and not self.pending:
                if now-getattr(self,'move_started',now) > 90:
                    raise RuntimeError('Worker travel timeout')
        except Exception as error:
            self.state = 'failed'
            self.gesture.reset()
            # A failed carry must not leave People walking with an abandoned box.
            if getattr(self,'walking_carry',None) is not None:
                self.timeline.pause()
            print('[Multi-box] FAILED:',error,'; press Stop')

    def on_stop(self,event):
        import omni.timeline
        if event.type == int(omni.timeline.TimelineEventType.STOP):
            self.gesture.reset()
            errors = restore_transfers(self.transfers)
            if errors:
                print('[Multi-box] RESTORE_ERRORS:',errors)
            self.state = 'stopped'
            if getattr(self,'spacing',None) is not None:
                self.spacing.restore()

    def shutdown(self):
        self.command_sub = self.update_sub = self.stop_sub = None
        try:
            errors = restore_transfers(self.transfers)
            if errors:
                print('[Multi-box] RESTORE_ERRORS:',errors)
        finally:
            if getattr(self,'spacing',None) is not None:
                self.spacing.restore()
            try:
                self.gesture.shutdown()
            finally:
                self.sync.shutdown()
