"""Continuous SAT for translating upright rectangular boxes (visual proxy)."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class OrientedBox:
    name: str
    center: tuple
    half: tuple
    yaw: float

    def __post_init__(self):
        if (len(self.center)!=3 or len(self.half)!=3
                or not all(math.isfinite(v) for v in (*self.center,*self.half,self.yaw))
                or min(self.half)<=0):
            raise ValueError('Invalid oriented box')


def axes(box):
    c,s = math.cos(box.yaw),math.sin(box.yaw)
    return ((c,s,0),(-s,c,0),(0,0,1))


def dot(a,b):
    return sum(x*y for x,y in zip(a,b))


def collisions(points, moving, obstacles):
    """Exact continuous SAT for fixed-yaw upright box proxies; contact allowed."""
    hits=[]
    for other in obstacles:
        for start,end in zip(points,points[1:]):
            enter,leave=0.,1.
            for axis in (*axes(moving),*axes(other)[:2]):
                radius=sum(h*abs(dot(a,axis)) for h,a in zip(moving.half,axes(moving)))
                radius+=sum(h*abs(dot(a,axis)) for h,a in zip(other.half,axes(other)))
                radius-=1e-6
                origin=dot(tuple(start[k]-other.center[k] for k in range(3)),axis)
                velocity=dot(tuple(end[k]-start[k] for k in range(3)),axis)
                if abs(velocity)<1e-12:
                    if abs(origin)>=radius:
                        enter,leave=1.,0.
                        break
                else:
                    lo,hi=sorted(((-radius-origin)/velocity,(radius-origin)/velocity))
                    enter,leave=max(enter,lo),min(leave,hi)
            if enter<leave:
                hits.append(other.name)
                break
    return tuple(hits)


def from_stage(stage,path):
    from pxr import Usd,UsdGeom,Gf
    prim=stage.GetPrimAtPath(path)
    cache=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render','proxy'])
    bounds=cache.ComputeUntransformedBound(prim).ComputeAlignedRange()
    matrix=UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    scale=tuple(math.sqrt(sum(float(matrix[i][j])**2 for j in range(3))) for i in range(3))
    if bounds.IsEmpty() or min(scale)<=0:
        raise RuntimeError('Invalid box geometry: '+path)
    rows=tuple(tuple(float(matrix[i][j])/scale[i] for j in range(3)) for i in range(3))
    if (abs(rows[0][2])>1e-5 or abs(rows[1][2])>1e-5 or abs(rows[2][2]-1)>1e-5
            or abs(dot(rows[0],rows[1]))>1e-5):
        raise RuntimeError('Box is not upright orthogonal: '+path)
    center=tuple(matrix.Transform(Gf.Vec3d(*bounds.GetMidpoint())))
    return OrientedBox(path,center,tuple(bounds.GetSize()[k]*scale[k]/2 for k in range(3)),
                       math.atan2(rows[0][1],rows[0][0]))


def route_around(points,moving,obstacles,margin):
    """Try short horizontal doglegs; preserve lift/extraction and final descent."""
    if not collisions(points,moving,obstacles):
        return points
    if len(points)<6:
        return None
    a,b=points[-3],points[-2]
    candidates=[]
    for obstacle in obstacles:
        for k in (0,1):
            extent=sum(h*abs(axis[k]) for h,axis in zip(obstacle.half,axes(obstacle)))
            extent+=sum(h*abs(axis[k]) for h,axis in zip(moving.half,axes(moving)))+margin
            for sign in (-1,1):
                coord=obstacle.center[k]+sign*extent
                p,q=list(a),list(b)
                p[k]=q[k]=coord
                candidate=[*points[:-2],tuple(p),tuple(q),*points[-2:]]
                if not collisions(candidate,moving,obstacles):
                    candidates.append(candidate)
    return min(candidates,key=lambda ps:sum(math.dist(a,b) for a,b in zip(ps,ps[1:])),default=None)
