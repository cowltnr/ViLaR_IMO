"""Validated Worker-only approach after the Cart has been parked."""

import math

from scripts.configure_warehouse_worker_behavior import validate_destination_path


def approach_candidates(start, target, distances, angles):
    dx, dy = start[0] - target[0], start[1] - target[1]
    length = math.hypot(dx, dy)
    if length < 1e-6 or not all(math.isfinite(v) for v in (*start, *target, *distances, *angles)):
        raise ValueError("Invalid approach geometry")
    dx, dy = dx / length, dy / length
    result = []
    for distance in distances:
        if distance <= 0:
            raise ValueError("Approach distances must be positive")
        for angle in angles:
            a = math.radians(angle)
            result.append((target[0] + distance * (dx * math.cos(a) - dy * math.sin(a)),
                           target[1] + distance * (dx * math.sin(a) + dy * math.cos(a)), start[2]))
    return result


def select_approach(start, target, candidates, closest, query_path, max_snap, max_distance):
    snapped_start = closest(start)
    if snapped_start is None or math.dist(start, snapped_start) > max_snap:
        raise RuntimeError("Worker is outside NavMesh approach start tolerance")
    for candidate in candidates:
        goal = closest(candidate)
        if goal is None or not all(math.isfinite(v) for v in goal):
            continue
        if math.dist(candidate, goal) > max_snap or math.dist(goal[:2], target[:2]) > max_distance:
            continue
        points = query_path(snapped_start, goal)
        try:
            validate_destination_path(points, snapped_start, goal)
        except RuntimeError:
            continue
        return tuple(goal), len(points)
    raise RuntimeError("No close, connected Worker approach point on existing NavMesh. "
                       "Cart remains parked; do not reduce Bake radius without review.")


class WorkerApproach:
    def __init__(self, distances, angles, max_snap, max_distance, timeout,
                 after_turn=False, forward_step=.05):
        self.distances, self.angles = distances, angles
        self.max_snap, self.max_distance, self.timeout = max_snap, max_distance, timeout
        self.character = None
        self.command = None
        self.after_turn, self.forward_step = after_turn, forward_step

    def begin(self, start, target, now):
        import carb
        import omni.anim.navigation.core as nav
        from omni.anim.people.scripts.utils import Utils
        mesh = nav.acquire_interface().get_navmesh()
        if mesh is None:
            raise RuntimeError("NavMesh unavailable for Worker approach")

        def closest(p):
            point = mesh.query_closest_point(carb.Float3(*p))
            return tuple(float(point[i]) for i in range(3)) if point is not None else None

        def path(a, b):
            route = mesh.query_shortest_path(start_pos=carb.Float3(*a), end_pos=carb.Float3(*b))
            return [tuple(float(p[i]) for i in range(3)) for p in route.get_points()] if route is not None else []

        if self.after_turn:
            self.goal, count = select_forward_approach(start, target, closest, path,
                                                       self.max_snap, self.forward_step, min(self.distances))
            if math.dist(start, self.goal) < self.forward_step:
                print('[Worker Approach] NO_ADVANCE: keep current position on existing NavMesh.')
                return False
        else:
            self.goal, count = select_approach(start, target,
                approach_candidates(start, target, self.distances, self.angles), closest, path,
                self.max_snap, self.max_distance)
        self.character = Utils.fetch_target_character_instance_by_name('Worker_01')
        if self.character is None:
            raise RuntimeError("Worker People behavior instance unavailable")
        self.command = 'Worker_01 GoTo %.5f %.5f %.5f _' % self.goal
        # Append only after Cart hold and successful path validation. Do not prequeue on Play.
        self.character.inject_command([self.command, 'Worker_01 Idle 10'], executeImmediately=False)
        self.started = now
        print(f'[Worker Approach] QUEUED: goal={self.goal}, path_points={count}; after existing Idle')
        return True

    def cancel(self):
        if self.character is None or self.command is None:
            return
        tokens = self.command.split()[1:]
        current = self.character.current_command
        if current is not None and list(current.command) == tokens:
            self.character.end_current_command(set_status=True)
        # Remove only this injected GoTo; preserve other commands and their IDs.
        self.character.commands[:] = [pair for pair in self.character.commands if list(pair[1]) != tokens]
        self.character = None
        self.command = None

    def reset(self):
        # Called only on Stop, after the People runtime is being torn down.
        self.character = None
        self.command = None


def select_forward_approach(start, target, closest, query_path, max_snap, step, stand_off):
    """Farthest reachable sample along a forward corridor; no off-mesh teleport."""
    if (not all(math.isfinite(v) for v in (*start, *target, max_snap, step, stand_off))
            or min(max_snap, step, stand_off) <= 0):
        raise ValueError('Invalid forward approach settings')
    snapped = closest(start)
    if snapped is None or not all(math.isfinite(v) for v in snapped) or math.dist(start, snapped) > max_snap:
        raise RuntimeError('Worker outside NavMesh approach start tolerance')
    distance = math.dist(start[:2], target[:2])
    if distance <= stand_off + step:
        return tuple(start), 0
    advance = distance - stand_off
    if advance / step > 1000:
        raise RuntimeError('Forward approach search too large; inspect target')
    direction = tuple((target[i] - start[i]) / distance for i in (0,1))

    def coordinates(p):
        dx, dy = p[0] - start[0], p[1] - start[1]
        return dx*direction[0] + dy*direction[1], abs(dx*direction[1] - dy*direction[0])

    goals = set()
    for index in range(math.ceil(advance / step), 0, -1):
        travel = min(advance, index * step)
        candidate = (start[0] + travel*direction[0], start[1] + travel*direction[1], start[2])
        goal = closest(candidate)
        if goal is None or not all(math.isfinite(v) for v in goal) or math.dist(candidate, goal) > max_snap:
            continue
        progress, lateral = coordinates(goal)
        if (progress < step or progress > advance or lateral > max_snap
                or abs(goal[2] - start[2]) > max_snap):
            continue
        goals.add(tuple(goal))
    for goal in sorted(goals, key=lambda p: math.dist(p[:2], target[:2])):
        points = query_path(snapped, goal)
        try:
            validate_destination_path(points, snapped, goal)
        except RuntimeError:
            continue
        previous = -max_snap
        valid = True
        for point in points:
            if not all(math.isfinite(v) for v in point):
                valid = False
                break
            progress, lateral = coordinates(point)
            if (lateral > max_snap or progress < previous - .02 or progress > advance
                    or abs(point[2] - start[2]) > max_snap):
                valid = False
                break
            previous = progress
        if valid:
            return goal, len(points)
    return tuple(start), 0
