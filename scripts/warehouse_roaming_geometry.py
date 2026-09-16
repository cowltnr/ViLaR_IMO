"""Pure planar sampling for conservative, static NavMesh footprint checks."""
import math
from scripts.warehouse_worker_cart_pose_sync import compose_pose

def yaw_degrees(pose):
    return math.degrees(2*math.atan2(pose[1][2],pose[1][3]))


def pose_at(position,yaw):
    a=math.radians(yaw)/2
    return tuple(position),(0.,0.,math.sin(a),math.cos(a))


def footprint_grid(low,high,step):
    if (not math.isfinite(step) or step<=0 or len(low)!=2 or len(high)!=2
            or not all(math.isfinite(v) for v in (*low,*high))
            or any(high[k]<low[k] for k in (0,1))):
        raise ValueError('Invalid footprint grid')
    counts=[max(1,math.ceil((high[k]-low[k])/step)) for k in (0,1)]
    if (counts[0]+1)*(counts[1]+1)>1000:
        raise ValueError('Unexpected loaded Cart footprint size')
    return tuple((low[0]+(high[0]-low[0])*i/counts[0],
                  low[1]+(high[1]-low[1])*j/counts[1],0.)
                 for i in range(counts[0]+1) for j in range(counts[1]+1))


def footprint_world(pose,points):
    return tuple(compose_pose(pose,(p,(0,0,0,1)))[0] for p in points)


def route_poses(points,start_yaw,forward_yaw,step,turn_step):
    if not points or min(step,turn_step)<=0 or not all(math.isfinite(v)
            for v in (start_yaw,forward_yaw,step,turn_step,*[x for p in points for x in p])):
        raise ValueError('Invalid sampled route')
    yaw=start_yaw
    yield pose_at(points[0],yaw)
    for start,end in zip(points,points[1:]):
        distance=math.dist(start,end)
        if distance<1e-6:
            continue
        desired=math.degrees(math.atan2(end[1]-start[1],end[0]-start[0]))-forward_yaw
        error=(desired-yaw+180)%360-180
        n=max(1,math.ceil(abs(error)/turn_step))
        for i in range(1,n+1):
            yield pose_at(start,yaw+error*i/n)
        yaw+=error
        n=max(1,math.ceil(distance/step))
        for i in range(1,n+1):
            yield pose_at(tuple(start[k]+(end[k]-start[k])*i/n for k in range(3)),yaw)
