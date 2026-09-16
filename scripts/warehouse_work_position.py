"""Read-only candidate selection; navigation AND handling must be valid."""
import math
from scripts.configure_warehouse_worker_behavior import validate_destination_path


def select_work_position(start,target,distances,angles,closest,query_path,clear_at,max_snap):
    dx,dy=start[0]-target[0],start[1]-target[1]
    length=math.hypot(dx,dy)
    if (not all(math.isfinite(v) for v in (*start,*target,*distances,*angles,max_snap))
            or length<1e-6 or max_snap<=0 or any(d<=0 for d in distances)):
        raise ValueError('Invalid work-position search')
    origin=closest(start)
    if origin is None or math.dist(origin,start)>max_snap:
        return None
    seen=set()
    for distance in distances:
        for degrees in angles:
            angle=math.radians(degrees)
            x=(dx*math.cos(angle)-dy*math.sin(angle))/length
            y=(dx*math.sin(angle)+dy*math.cos(angle))/length
            candidate=(start[0]+distance*x,start[1]+distance*y,start[2])
            goal=closest(candidate)
            if goal is None or not all(math.isfinite(v) for v in goal):
                continue
            goal=tuple(goal)
            if goal in seen or math.dist(goal,candidate)>max_snap or math.dist(goal,start)<.05:
                continue
            seen.add(goal)
            points=query_path(origin,goal)
            try:
                validate_destination_path(points,origin,goal)
            except RuntimeError:
                continue
            if clear_at(goal,points):
                return goal
    return None
