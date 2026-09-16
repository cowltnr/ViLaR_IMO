"""Shelf arrival plus visual four-box stack, with explicit proxy path checks."""
import math
import time
from scripts.warehouse_worker_face_box import FaceBoxRuntime,box_center
from scripts.warehouse_oriented_clearance import OrientedBox,from_stage,collisions,axes


class PathSearchError(RuntimeError):
    def __init__(self,phase,blockers=(),checks=0):
        self.phase,self.blockers,self.checks=phase,tuple(sorted(blockers)),checks
        super().__init__('phase='+phase+'; checks='+str(checks)+'; blockers='+','.join(self.blockers))


def path_search_steps(source,destination,moving,obstacles,clearance,
                      offsets=(0.,.35,.7,1.),max_extra_height=2.,max_checks=512):
    """Yield between checks. Conservative broad phase excludes only disjoint boxes."""
    if clearance<0 or not math.isfinite(clearance):
        raise ValueError('Invalid clearance')
    extent=lambda box:tuple(sum(h*abs(a[k]) for h,a in zip(box.half,axes(box))) for k in range(3))
    moving_extent=extent(moving)
    entries=[(o,extent(o)) for o in obstacles]
    checks=0
    def check(points):
        nonlocal checks
        if checks>=max_checks:
            raise PathSearchError('search_budget',checks=checks)
        checks+=1
        low=tuple(min(p[k] for p in points)-moving_extent[k] for k in range(3))
        high=tuple(max(p[k] for p in points)+moving_extent[k] for k in range(3))
        candidates=[o for o,e in entries if all(o.center[k]+e[k]>=low[k] and o.center[k]-e[k]<=high[k] for k in range(3))]
        return collisions(points,moving,candidates)
    for phase,point in [('source',source),('destination',destination)]:
        hits=check([point,point])
        yield {'phase':phase,'checks':checks,'blockers':hits}
        if hits:
            raise PathSearchError(phase,hits,checks)
    base=max(source[2],destination[2])+clearance
    heights=sorted({base,*[o.center[2]+o.half[2]+moving.half[2]+clearance
                         for o in obstacles if base<o.center[2]+o.half[2]+moving.half[2]+clearance<=base+max_extra_height]})
    departures=[source]
    for distance in offsets:
        if distance>0:
            for axis in (0,1):
                for sign in (-1,1):
                    p=list(source); p[axis]+=sign*distance
                    departures.append(tuple(p))
    reasons={'departure':set(),'descent':set(),'travel':set()}
    for height in heights:
        for depart in departures:
            points=[source,depart,depart,(*depart[:2],height),
                    (*destination[:2],height),destination]
            hits=check(points[:4])
            yield {'phase':'departure','checks':checks,'blockers':hits}
            if hits:
                reasons['departure'].update(hits)
                continue
            hits=check(points[-2:])
            yield {'phase':'descent','checks':checks,'blockers':hits}
            if hits:
                reasons['descent'].update(hits)
                continue
            hits=check(points)
            yield {'phase':'travel','checks':checks,'blockers':hits}
            if not hits:
                return points
            reasons['travel'].update(hits)
            # Generate doglegs only around actual blockers; validate against all.
            for obstacle in obstacles:
                if obstacle.name not in hits:
                    continue
                for axis in (0,1):
                    extent=sum(h*abs(a[axis]) for h,a in zip(obstacle.half,axes(obstacle)))
                    extent+=sum(h*abs(a[axis]) for h,a in zip(moving.half,axes(moving)))+clearance
                    for sign in (-1,1):
                        p,q=list(points[-3]),list(points[-2])
                        p[axis]=q[axis]=obstacle.center[axis]+sign*extent
                        candidate=[*points[:-2],tuple(p),tuple(q),*points[-2:]]
                        candidate_hits=check(candidate)
                        yield {'phase':'detour','checks':checks,'blockers':candidate_hits}
                        if not candidate_hits:
                            return candidate
    raise PathSearchError('no_candidate',set().union(*reasons.values()),checks)


def clear_transfer_path(*args,**kwargs):
    """Synchronous offline adapter; live runtime consumes the generator in slices."""
    steps=path_search_steps(*args,**kwargs)
    while True:
        try:
            next(steps)
        except StopIteration as result:
            return result.value


def pull_then_path_steps(source,destination,moving,obstacles,clearance,*,
                         allowed_prefix,pull_distances=(.35,.5,.7,1.),
                         offsets=(0.,.35,.7,1.),max_extra_height=2.,max_checks=512,
                         allowed_side_boxes=()):
    """User-authorized visual extraction from existing neighbouring-box overlap.

    Only the first horizontal segment may overlap initially intersecting or
    explicitly named side boxes. Endpoints and subsequent segments stay checked.
    """
    if not allowed_prefix or not pull_distances or any(not math.isfinite(d) or d<=0 for d in pull_distances):
        raise ValueError('Invalid authorized extraction configuration')
    initial=set(collisions([source,source],moving,obstacles))
    refused={name for name in initial if not name.startswith(allowed_prefix)}
    if refused:
        raise PathSearchError('source_not_authorized',refused)
    delta=tuple(destination[k]-source[k] for k in (0,1))
    axis=max((0,1),key=lambda k:abs(delta[k]))
    if abs(delta[axis])<1e-6:
        raise PathSearchError('no_cart_pull_direction')
    allowed=initial|{name for name in allowed_side_boxes if name.startswith(allowed_prefix)}
    remaining=[o for o in obstacles if o.name not in allowed]
    yield {'phase':'initial_overlap_authorized','blockers':tuple(sorted(initial))}
    blockers=set()
    for distance in pull_distances:
        point=list(source)
        point[axis]+=math.copysign(distance,delta[axis])
        point=tuple(point)
        hits=set(collisions([source,point],moving,remaining))
        hits.update(collisions([point,point],moving,obstacles))
        yield {'phase':'pull','distance':distance,'blockers':tuple(sorted(hits))}
        if hits:
            blockers.update(hits)
            continue
        # Start normal checked planning only after fully clearing the neighbours.
        tail=yield from path_search_steps(point,destination,moving,obstacles,clearance,
            offsets,max_extra_height,max_checks)
        points=[]
        for p in [source,*tail]:
            if not points or p!=points[-1]:
                points.append(p)
        return points
    raise PathSearchError('pull_blocked',blockers)


def iter_obstacle_proxies(stage,config,source_path,worker_position):
    from pxr import Usd,UsdGeom
    from scripts.warehouse_box_only_stack import bounds
    warehouse=stage.GetPrimAtPath(config.WAREHOUSE_PATH)
    if not warehouse:
        raise RuntimeError('Warehouse missing')
    # Warehouse box assemblies (not only the four selected targets).
    for prim in warehouse.GetChildren():
        root=str(prim.GetPath())
        if not prim.GetName().startswith('Box_') or source_path.startswith(root+'/'):
            continue
        if UsdGeom.Imageable(prim).ComputeVisibility()=='invisible':
            continue
        path=next((p for p in getattr(config,'OBSTACLE_BOX_PATHS',config.BOX_PATHS)
                   if p.startswith(root+'/')),root)
        try:
            yield from_stage(stage,path)
        except RuntimeError:
            r=bounds(stage,path)
            yield OrientedBox(path,tuple(r.GetMidpoint()),tuple(v/2 for v in r.GetSize()),0)
    # Individual visible cargo/cart meshes preserve space above the lids.
    cart=stage.GetPrimAtPath(config.CART_PATH)
    if not cart:
        raise RuntimeError('Cart missing')
    for prim in Usd.PrimRange(cart):
        if not prim.IsA(UsdGeom.Mesh) or UsdGeom.Imageable(prim).ComputeVisibility()=='invisible':
            continue
        r=bounds(stage,str(prim.GetPath()))
        half=tuple(max(float(v)/2,1e-5) for v in r.GetSize())
        yield OrientedBox(str(prim.GetPath()),tuple(r.GetMidpoint()),half,0)
    h=config.WORKER_BODY_HEIGHT_M
    yield OrientedBox('WorkerBody',(*worker_position[:2],worker_position[2]+h/2),
        (config.WORKER_BODY_RADIUS_M,config.WORKER_BODY_RADIUS_M,h/2),0)


def obstacle_proxies(*args):
    return list(iter_obstacle_proxies(*args))


def pull_policy(config,proxies,loaded_paths):
    """Visual neighbour extraction is independent of arm animation selection."""
    allow=getattr(config,'STACK_ALLOW_SIDE_BOX_OVERLAP',
                  not getattr(config,'STACK_GESTURES_ENABLED',True))
    loaded=set(loaded_paths)
    return dict(
        allowed_side_boxes=tuple(p.name for p in proxies
            if allow and p.name.startswith(config.WAREHOUSE_PATH+'/Box_') and p.name not in loaded),
        pull_distances=(config.STACK_VISUAL_PULL_DISTANCES_M if allow
                        else config.STACK_PULL_DISTANCES_M))


class StackGestureRuntime(FaceBoxRuntime):
    def __init__(self,*args,stage,config,**kwargs):
        self.stage,self.config=stage,config
        self.sequence=None
        self.box_index=0
        self.search=None
        self.planned_transfer=None
        self.parking_worker_pose=None
        self.roaming=None
        super().__init__(*args,**kwargs)

    def select_transfer(self):
        transfer=self.sequence.transfers[self.box_index]
        transfer.delay=self.config.ARM_RAISE_SECONDS if self.gesture is not None else 0.
        path=transfer.box_path
        self.planned_transfer=None
        self.transfer=transfer
        self.target=box_center(self.stage,path)
        if self.gesture is not None:
            self.gesture.follow_transfer(transfer,self.forward_yaw,self.config.STACK_TURN_RATE_DEG_S)
        print('[Worker Stack] BOX',self.box_index+1,'of',len(self.sequence.transfers),path)

    def plan_steps(self):
        """No Worker/box motion while collecting geometry and planning."""
        from dataclasses import asdict
        transfer=self.transfer
        position=self.sync._read_worker_pose()[0]
        proxies=[]
        for proxy in iter_obstacle_proxies(self.stage,self.config,transfer.box_path,position):
            proxies.append(proxy)
            yield {'phase':'geometry','count':len(proxies)}
        moving=from_stage(self.stage,transfer.box_path)
        source=box_center(self.stage,transfer.box_path)
        destination=transfer.destination
        self.search_report.update(source=source,destination=destination,
            worker_position=position,obstacles=[asdict(p) for p in proxies])
        if collisions([destination,destination],moving,proxies) and self.box_index==0:
            from scripts.warehouse_multi_box_inspection import collect_lid_meshes
            from scripts.warehouse_composite_support import lid_surfaces_from_mesh_report,placement_candidates
            from scripts.warehouse_box_only_stack import bounds,stack_centers
            c=self.config
            sizes=[tuple(bounds(self.stage,p).GetSize()) for p in c.BOX_PATHS]
            lids=lid_surfaces_from_mesh_report(collect_lid_meshes(self.stage,c.PALLET_PATH),verified_ids=c.COMPOSITE_VERIFIED_LID_PATHS)
            footprint=tuple(max(s[k] for s in sizes) for k in range(3))
            candidates=placement_candidates('alternate_stack',footprint,lids,[],
                max_gap=c.COMPOSITE_MAX_GAP_M,max_height_delta=c.COMPOSITE_MAX_HEIGHT_DELTA_M,
                min_coverage=c.COMPOSITE_MIN_COVERAGE,edge_margin=c.EDGE_MARGIN_M,
                placement_gap=c.PLACEMENT_GAP_M,max_top=1e6)
            for index,placement in enumerate(candidates):
                if index>=c.STACK_MAX_PLACEMENT_CANDIDATES:
                    break
                xy=tuple((placement.bounds.lower[k]+placement.bounds.upper[k])/2 for k in (0,1))
                centers=stack_centers(xy,placement.bounds.lower[2]-c.PLACEMENT_GAP_M,sizes,c.PLACEMENT_GAP_M)
                valid=True
                for path,center in zip(c.BOX_PATHS,centers):
                    if collisions([center,center],from_stage(self.stage,path),proxies):
                        valid=False
                        break
                yield {'phase':'placement','candidate':index,'accepted':valid}
                if valid:
                    for item,center in zip(self.sequence.transfers,centers):
                        item.destination=center
                    destination=transfer.destination
                    self.search_report['destination']=destination
                    print('[Worker Stack] PLACEMENT_CHANGED: collision-checked lid candidate',destination)
                    break
        if self.config.STACK_ALLOW_INITIAL_NEIGHBOUR_OVERLAP:
            self.search_report['initial_overlap_policy']='user-authorized first horizontal pull only'
            points=yield from pull_then_path_steps(source,destination,moving,proxies,
                self.config.LIFT_CLEARANCE_M,
                allowed_prefix=self.config.WAREHOUSE_PATH+'/Box_',
                **pull_policy(self.config,proxies,
                    (t.box_path for t in self.sequence.transfers[:self.box_index])),
                offsets=self.config.STACK_EXTRACTION_OFFSETS_M,
                max_extra_height=self.config.STACK_MAX_EXTRA_HEIGHT_M,
                max_checks=self.config.STACK_MAX_PATH_CHECKS)
        else:
            points=yield from path_search_steps(source,destination,moving,proxies,
                self.config.LIFT_CLEARANCE_M,self.config.STACK_EXTRACTION_OFFSETS_M,
                self.config.STACK_MAX_EXTRA_HEIGHT_M,self.config.STACK_MAX_PATH_CHECKS)
        def cached_path(actual_source,actual_destination,*args,**kwargs):
            if math.dist(actual_source,source)>1e-5 or math.dist(actual_destination,destination)>1e-5:
                raise RuntimeError('Box geometry changed after path planning; Stop and Run again')
            return points
        transfer.path_builder=cached_path
        self.planned_transfer=transfer
        self.search_report['path']=points
        self.search_report['status']='path_verified_proxy_only'
        print('[Worker Stack] PATH_OK:',transfer.box_path,'points=',len(points))

    def save_search_report(self):
        import json
        from pathlib import Path
        from datetime import datetime
        from uuid import uuid4
        from zoneinfo import ZoneInfo
        stamp=datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y%m%d_%H%M%S_%f')
        directory=Path(__file__).resolve().parent.parent/'artifacts'/'runs'/('stack_path_'+stamp+'_'+uuid4().hex[:6])
        directory.mkdir(parents=True,exist_ok=False)
        path=directory/'path_report.json'
        path.write_text(json.dumps(self.search_report,indent=2,allow_nan=False),encoding='utf-8')
        print('[Worker Stack] PATH_REPORT:',path)

    def advance_search(self):
        started=time.monotonic()
        try:
            if started-self.search_started>self.config.STACK_SEARCH_TIMEOUT_SECONDS:
                raise PathSearchError('time_budget')
            for _ in range(self.config.STACK_CHECKS_PER_FRAME):
                progress=next(self.search)
                self.search_report['last_progress']=progress
                phase=progress['phase']
                if phase=='initial_overlap_authorized':
                    print('[Worker Stack] INITIAL_OVERLAP_ALLOWED: pull only',progress['blockers'])
                elif phase=='pull' and not progress.get('blockers'):
                    print('[Worker Stack] PULL_CLEAR:',progress['distance'],'m toward Cart')
                counts=self.search_report['phase_counts']
                counts[phase]=counts.get(phase,0)+1
                blockers=self.search_report.setdefault('phase_blockers',{})
                if progress.get('blockers'):
                    blockers[phase]=sorted(set(blockers.get(phase,[]))|set(progress['blockers']))
                if time.monotonic()-started>=self.config.STACK_FRAME_BUDGET_SECONDS:
                    break
        except StopIteration:
            self.search=None
            self.state='arrival_pending'
            self.save_search_report()
        except Exception as error:
            self.search=None
            self.state='failed'
            self.search_report.update(status='failed',error=str(error))
            self.save_search_report()
            print('[Worker Stack] FAILED:',error,'; press Stop')

    def _on_update(self,event):
        import omni.usd
        if omni.usd.get_context().get_stage()!=self.stage:
            self.shutdown()
            return
        if not self.timeline.is_playing():
            return
        if getattr(self,'roaming',None) is not None:
            self.roaming.update(self.timeline.get_current_time())
            return
        if self.state=='planning':
            self.advance_search()
            return
        if self.state=='arrival_pending' and self.sequence is None:
            # Destination geometry must be read AFTER the cart reached its parking pose.
            pose=self.sync._read_worker_pose()
            cart=self.sync._read_cart_pose()
            if (math.dist(pose[0],self.worker_goal)>self.tolerance
                    or math.dist(cart[0][:2],self.cart_goal[:2])>self.tolerance):
                self.state='failed'
                print('[Worker Stack] FAILED: parking tolerance; press Stop')
                return
            self.sync.hold()
            self.parking_worker_pose=pose
            try:
                from scripts.warehouse_box_only_stack import prepare
                self.sequence=prepare(self.stage,self.config)
                self.select_transfer()
            except Exception as error:
                self.state='failed'
                print('[Worker Stack] FAILED:',error,'; press Stop')
                return
        if self.state=='arrival_pending' and self.planned_transfer is not self.transfer:
            self.search_report={'box':self.transfer.box_path,'status':'planning','phase_counts':{}}
            self.search_started=time.monotonic()
            self.search=self.plan_steps()
            self.state='planning'
            print('[Worker Stack] PLANNING: incremental geometry and path checks')
            return
        if self.gesture is None:
            try:
                if self.state=='arrival_pending':
                    self.transfer.start(self.timeline.get_current_time(),self.sync._read_worker_pose()[0])
                    self.state='facing'
                if self.state=='facing':
                    self.transfer.update(self.timeline.get_current_time())
            except Exception as error:
                self.state='failed'
                print('[Worker Stack] FAILED:',error,'; press Stop')
                return
        else:
            super()._on_update(event)
        if (self.state=='facing' and self.transfer.state=='loaded'
                and (self.gesture is None or self.gesture.done)):
            self.box_index+=1
            print('[Worker Stack] LOADED',self.box_index,'of',len(self.sequence.transfers))
            if self.box_index==len(self.sequence.transfers):
                from scripts import warehouse_roaming_config as roaming_config
                if roaming_config.ENABLED:
                    try:
                        from scripts.warehouse_loaded_cart_roaming import LoadedCartRoaming
                        from scripts.warehouse_roaming_actions import IsaacRoamingActions
                        self.roaming=LoadedCartRoaming(IsaacRoamingActions(self))
                        self.state='roaming'
                        self.roaming.start(self.timeline.get_current_time())
                    except Exception as error:
                        self.state='failed'
                        print('[Loaded Roaming] SETUP FAILED:',error,'; press Stop')
                    return

                from scripts.warehouse_worker_face_box import target_yaw

                position = self.sync._read_worker_pose()[0]
                cart_position = self.sync._read_cart_pose()[0]
                yaw = target_yaw(
                    position,
                    cart_position,
                    self.forward_yaw,
                    )

                if self.gesture is not None:
                    # 마지막 팔 내리기가 끝난 뒤 방향과 손 목표를 함께 갱신
                    self.gesture.yaw = yaw
                    self.gesture.update(
                        self.timeline.get_current_time()
                    )
                else:
                    import carb

                    angle = math.radians(yaw) / 2

                    self.sync._character.set_world_transform(
                        carb.Float3(*position),
                        carb.Float4(
                            0,
                            0,
                            math.sin(angle),
                            math.cos(angle),
                        ),
                    )
                self.state='waiting_arrival'  # Hold final arms-down pose; no repeated completion.
                print('[Worker Stack] COMPLETE: Cart parked, arms down; Stop restores boxes')
            else:
                try:
                    if self.gesture is not None:
                        self.gesture.reset()
                    self.select_transfer()
                    self.state='arrival_pending'  # Same parked position, face the next source.
                except Exception as error:
                    self.state='failed'
                    print('[Worker Stack] FAILED:',error,'; press Stop')

    def _on_timeline(self,event):
        if event.type==self._stop_type:
            if getattr(self,'search',None) is not None:
                self.search.close()
                self.search=None
            try:
                try:
                    self._close_roaming()
                finally:
                    if self.sequence is not None:
                        self.sequence.restore()
            finally:
                super()._on_timeline(event)
                self.sequence=None
                self.transfer=None
                self.box_index=0
                self.planned_transfer=None
                self.parking_worker_pose=None

    def _close_roaming(self):
        roaming=getattr(self,'roaming',None)
        if roaming is not None:
            try:
                roaming.close()
            finally:
                self.roaming=None

    def shutdown(self):
        if getattr(self,'search',None) is not None:
            self.search.close()
            self.search=None
        try:
            try:
                self._close_roaming()
            finally:
                if self.sequence is not None:
                    self.sequence.restore()
        finally:
            super().shutdown()
