"""Phased visual carry: pickup, People GoTo with held box, place, release.

People exclusively owns walking translation. This controller never teleports
the Worker. Box transforms remain in the existing removable transfer layer.
"""
import math
from scripts.warehouse_worker_cart_pose_sync import compose_pose
from scripts.warehouse_oriented_clearance import OrientedBox,from_stage,collisions,route_around
from scripts.warehouse_worker_face_box import target_yaw


def held_center(pose,distance,height):
    return compose_pose(pose,((0,-distance,height),(0,0,0,1)))[0]


def begin_segment(transfer,points,now,duration):
    if duration<=0 or not math.isfinite(duration):
        raise ValueError('Invalid carry duration')
    transfer.points=list(points)
    transfer.start_time,transfer.duration=now,duration
    transfer.state='moving'


def world_proxy(stage,path):
    """Conservative visible world AABB, including non-upright cart geometry."""
    from pxr import Usd,UsdGeom
    prim=stage.GetPrimAtPath(path)
    if not prim:
        raise RuntimeError('Missing collision geometry: '+path)
    bounds=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render','proxy']).ComputeWorldBound(prim).ComputeAlignedRange()
    if bounds.IsEmpty():
        raise RuntimeError('Empty collision geometry: '+path)
    return OrientedBox(path,tuple(bounds.GetMidpoint()),tuple(v/2 for v in bounds.GetSize()),0.)


class WalkingCarry:
    def __init__(self,owner,now,pose,dry_run=False):
        self.r=owner
        self.phase='pickup'
        self.distance=owner.config.CARRY_HOLD_DISTANCE_M
        self.height=owner.config.CARRY_HOLD_HEIGHT_M
        self.box=from_stage(owner.stage,owner.box)
        self.obstacles=[from_stage(owner.stage,p) for p in owner.config.BOX_PATHS if p!=owner.box]
        self.obstacles.extend(world_proxy(owner.stage,p)
            for p in sorted(set(owner.config.SOURCE_SUPPORT_PATHS.values())))
        self.cart=world_proxy(owner.stage,owner.config.CART_PATH)
        self.destination=owner.transfer.destination
        self.goal=self.find_drop_goal(pose)
        if self.goal is None:
            raise RuntimeError('No connected carry/drop work position')
        target=held_center(pose,self.distance,self.height)
        source,destination,low,high,size=owner.transfer._geometry()
        original=owner.transfer.path_builder(source,destination,pose[0],low,high,size,
            owner.transfer.pull_margin,owner.transfer.lift_clearance,owner.transfer.max_pull,
            pose[0][2]+owner.transfer.max_center_height_offset)
        points=[*original[:3],(original[2][0],original[2][1],target[2]),target]
        if collisions(points,self.box,[*self.obstacles,self.body(pose)]):
            raise RuntimeError('Pickup-to-hold path obstructed')
        if dry_run:
            return
        begin_segment(owner.transfer,points,now+owner.config.ARM_RAISE_SECONDS,
                      owner.config.PICKUP_SECONDS)
        owner.transfer.state='waiting'
        self.previous=owner.transfer.current_center
        print('[Walking Carry] PICKUP: box to holding position')

    def body(self,pose):
        c=self.r.config
        return OrientedBox('WorkerBody',(pose[0][0],pose[0][1],pose[0][2]+c.WORKER_BODY_HEIGHT_M/2),
            (c.WORKER_BODY_RADIUS_M,c.WORKER_BODY_RADIUS_M,c.WORKER_BODY_HEIGHT_M/2),0.)

    def placing_path(self,pose):
        target=held_center(pose,self.distance,self.height)
        z=max(target[2],self.destination[2])+self.r.config.LIFT_CLEARANCE_M
        if z>pose[0][2]+self.r.transfer.max_center_height_offset:
            return None
        points=[target,target,target,(target[0],target[1],z),
                (self.destination[0],self.destination[1],z),self.destination]
        return route_around(points,self.box,[*self.obstacles,self.body(pose)],.05)

    def find_drop_goal(self,pose):
        import carb
        import omni.anim.navigation.core as nav
        from scripts.configure_warehouse_worker_behavior import validate_destination_path
        mesh=nav.acquire_interface().get_navmesh()
        if mesh is None:
            return None
        for radius in self.r.config.DROP_WORK_DISTANCES_M:
            for angle in self.r.config.DROP_WORK_ANGLES_DEG:
                a=math.radians(angle)
                candidate=(self.destination[0]+radius*math.cos(a),
                           self.destination[1]+radius*math.sin(a),pose[0][2])
                result=mesh.query_closest_point(carb.Float3(*candidate))
                if result is None or math.dist(tuple(result),candidate)>self.r.config.MAX_NAVMESH_SNAP_M:
                    continue
                goal=tuple(result)
                route=mesh.query_shortest_path(start_pos=carb.Float3(*pose[0]),end_pos=carb.Float3(*goal))
                points=list(route.get_points()) if route else []
                try:
                    validate_destination_path(points,pose[0],goal)
                except RuntimeError:
                    continue
                # Conservative circle-enclosing prism includes carried box during turns.
                footprint=self.distance+math.hypot(*self.box.half[:2])
                envelope=OrientedBox('WorkerWithBox',pose[0],
                    (footprint,footprint,max(self.height+self.box.half[2],1.8)/2),0.)
                sweep=[(p[0],p[1],p[2]+envelope.half[2]) for p in points]
                if collisions(sweep,envelope,[*self.obstacles,self.cart]):
                    continue
                yaw=target_yaw(goal,self.destination,-90)
                q=math.radians(yaw)/2
                if self.placing_path((goal,(0,0,math.sin(q),math.cos(q)))) is None:
                    continue
                self.drop_heading=yaw
                return goal
        return None

    def update(self,now):
        r=self.r
        pose=r.sync._read_worker_pose()
        if self.phase=='pickup':
            r.transfer.update(now)
            arrived=r.transfer.state=='loaded'
            if arrived:
                r.transfer.state='moving'  # Hold arms; do not release at pickup.
            r.gesture.update(now)
            if arrived:
                r.move(self.goal,'walking_load',heading='%.5f'%self.drop_heading)
                self.phase='walking'
                r.gesture.walking_pose=pose
                print('[Walking Carry] WALK_TO_CART:',self.goal)
        elif self.phase=='walking':
            if now-r.move_started>90:
                raise RuntimeError('Carry walking timeout; press Stop')
            target=held_center(pose,self.distance,self.height)
            if collisions([self.previous,target],self.box,[*self.obstacles,self.cart]):
                raise RuntimeError('Carried box path obstructed during walking; press Stop')
            begin_segment(r.transfer,[target,target],now,1.)
            r.transfer.update(now)
            r.gesture.walking_pose=pose
            r.gesture.update(now)
            if r.pending:
                r.pending=False
                if math.dist(pose[0],self.goal)>.25:
                    raise RuntimeError('Carry arrival outside tolerance')
                points=self.placing_path(pose)
                if points is None:
                    raise RuntimeError('Placement path obstructed; press Stop')
                begin_segment(r.transfer,points,now,r.config.PLACE_SECONDS)
                self.phase='placing'
                print('[Walking Carry] PLACE: Worker reached Cart')
        else:
            r.transfer.update(now)
            r.gesture.walking_pose=pose
            r.gesture.update(now)
            if r.transfer.state=='loaded' and r.gesture.done:
                r.gesture.walking_pose=None
                r.loaded.append(r.placement)
                r.index+=1
                r.retreats=0
                r.relocations=0
                r.state='next'
                r.walking_carry=None
        self.previous=r.transfer.current_center
