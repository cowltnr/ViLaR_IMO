"""Visual-only composite support from VERIFIED inscribed lid rectangles.

No USD edits, physics, automatic rotations, or movement of existing cargo.
Outer mesh AABBs are not verified support rectangles. All coordinates must use
one meter-scale orthonormal frame. Rectangles carry the full surface Z range.
"""

from dataclasses import dataclass
from collections import deque
from itertools import product
import math

from scripts.warehouse_cart_packing import Bounds
from scripts.warehouse_cart_packing import Slide

EPS = 1e-8


def can_slide_on_lids(moving, destination, surfaces, loaded, *, max_gap,
                     max_height_delta, min_coverage, edge_margin, placement_gap):
    """Conservative straight sweep for new cargo only; fixed lids never move.

    Rejects moving a stacked box or a box supporting another. A support gap
    anywhere in the enclosing sweep is rejected, even if endpoints fit.
    """
    surfaces, loaded = tuple(surfaces), tuple(loaded)
    fixed = {s.surface_id for s in surfaces if s.verified}
    if (not all(math.isfinite(v) and v >= 0 for v in (edge_margin, placement_gap))
            or moving not in loaded or moving.box_id in fixed
            or not moving.support_ids or not set(moving.support_ids) <= fixed
            or any(moving.box_id in p.support_ids for p in loaded)
            or any(abs(a-b) > EPS for a, b in zip(moving.bounds.size, destination.size))
            or abs(moving.bounds.lower[2]-destination.lower[2]) > EPS):
        return False
    sweep = Bounds(tuple(min(a,b) for a,b in zip(moving.bounds.lower, destination.lower)),
                   tuple(max(a,b) for a,b in zip(moving.bounds.upper, destination.upper)))
    if any(not any(sweep.upper[k]+placement_gap <= p.bounds.lower[k]+EPS
                   or p.bounds.upper[k]+placement_gap <= sweep.lower[k]+EPS
                   for k in range(3)) for p in loaded if p.box_id != moving.box_id):
        return False
    support = evaluate_support(tuple(v-edge_margin for v in sweep.lower[:2]),
        tuple(v+edge_margin for v in sweep.upper[:2]), surfaces,
        max_gap=max_gap, max_height_delta=max_height_delta, min_coverage=min_coverage)
    return (support.accepted and
            abs(sweep.lower[2]-support.top_z-placement_gap) <= max_height_delta+EPS)


MAX_LID_THICKNESS_M = .05


def _transform_point(matrix, point):
    """Apply a USD row-vector Matrix4d serialized as four rows."""
    return tuple(sum(float(point[k]) * float(matrix[k][j]) for k in range(3))
                 + float(matrix[3][j]) for j in range(3))


def lid_surfaces_from_mesh_report(report, *, verified_ids=()):
    """Convert inspector records to conservative lid candidates.

    Geometry alone cannot prove that a mesh is a load-bearing lid, therefore
    `verified` remains false unless an explicit upstream record or allow-list
    says so. Complex lid topology is accepted when its world-space thickness is
    small; the resulting rectangle is still only a visual support heuristic.
    """
    result = []
    for item in report:
        points = item.get('points_local')
        counts = item.get('face_vertex_counts')
        indices = item.get('face_vertex_indices')
        matrix = item.get('world_matrix')
        visible = item.get('visibility', 'inherited')
        valid = (points and counts and indices and matrix and not item.get('hole_indices')
                 and visible != 'invisible'
                 and sum(counts) == len(indices))
        world = []
        if valid:
            try:
                world = [_transform_point(matrix, p) for p in points]
                valid = all(all(math.isfinite(v) for v in p) for p in world)
            except (TypeError, IndexError, ValueError):
                valid = False
        horizontal = (valid and
                      max(p[2] for p in world) - min(p[2] for p in world)
                      <= MAX_LID_THICKNESS_M)
        if horizontal:
            lower = (min(p[0] for p in world), min(p[1] for p in world))
            upper = (max(p[0] for p in world), max(p[1] for p in world))
            verified = bool(item.get('support_verified')) or item.get('path', '') in set(verified_ids)
            result.append(LidSurface(item.get('path', ''), lower, upper,
                                     min(p[2] for p in world), max(p[2] for p in world),
                                     verified=verified))
        elif item.get('path'):
            result.append(LidSurface(item['path'], (0, 0), (1, 1), 0, 0, verified=False))
    return tuple(result)


@dataclass(frozen=True)
class LidSurface:
    surface_id: str
    lower: tuple
    upper: tuple
    z_min: float
    z_max: float
    verified: bool = False

    def __post_init__(self):
        object.__setattr__(self, 'lower', tuple(self.lower))
        object.__setattr__(self, 'upper', tuple(self.upper))
        if (not self.surface_id or len(self.lower) != 2 or len(self.upper) != 2
                or not all(math.isfinite(v) for v in (*self.lower, *self.upper, self.z_min, self.z_max))
                or any(a >= b for a, b in zip(self.lower, self.upper))
                or self.z_min > self.z_max or type(self.verified) is not bool):
            raise ValueError('Invalid lid surface or verification flag')


@dataclass(frozen=True)
class SupportResult:
    accepted: bool
    coverage: float
    max_gap: float | None
    support_ids: tuple
    top_z: float | None
    reason: str


@dataclass(frozen=True)
class CargoPlacement:
    box_id: str
    bounds: Bounds
    support_ids: tuple


@dataclass(frozen=True)
class CompositePlan:
    placement: CargoPlacement
    slides: tuple
    relocated: tuple


def plan_with_slides(box_id, size, surfaces, loaded, *, max_relocations=2,
                     max_states=256, **policy):
    """Bounded search; None means no candidate found, not proof of impossibility."""
    surfaces, loaded = tuple(surfaces), tuple(loaded)
    if (type(max_relocations) is not int or max_relocations < 0
            or type(max_states) is not int or max_states < 1):
        raise ValueError('Invalid relocation search limits')
    queue = deque([(loaded, ())])
    visited = {loaded}
    slide_policy = {k:v for k,v in policy.items() if k != 'max_top'}
    while queue:
        current, slides = queue.popleft()
        direct = plan_on_lids(box_id, size, surfaces, current, **policy)
        if direct is not None:
            return CompositePlan(direct, slides, current)
        if len(slides) >= max_relocations:
            continue
        for index, moving in enumerate(current):
            axes = []
            for k in (0, 1):
                values = {v for s in surfaces if s.verified for v in (
                    s.lower[k]+policy['edge_margin'],
                    s.upper[k]-policy['edge_margin']-moving.bounds.size[k])}
                values.add(moving.bounds.lower[k])
                axes.append(sorted(values))
            for x,y in product(*axes):
                lower = (x,y,moving.bounds.lower[2])
                end = Bounds(lower, tuple(lower[k]+moving.bounds.size[k] for k in range(3)))
                if not can_slide_on_lids(moving,end,surfaces,current,**slide_policy):
                    continue
                support = evaluate_support(end.lower[:2],end.upper[:2],surfaces,
                    **{k:policy[k] for k in ('max_gap','max_height_delta','min_coverage')})
                shifted = CargoPlacement(moving.box_id,end,support.support_ids)
                candidate = (*current[:index],shifted,*current[index+1:])
                if candidate in visited:
                    continue
                if len(visited) >= max_states:
                    return None
                visited.add(candidate)
                queue.append((candidate,(*slides,Slide(moving.box_id,moving.bounds,end))))
    return None


def evaluate_support(lower, upper, surfaces, *, max_gap, max_height_delta, min_coverage):
    """Exact rectangle union coverage plus conservative unsupported-span test.

    Lower occluded lids cannot fill a hole at the chosen top elevation. Small
    seams are permitted only when a horizontal OR vertical unsupported span is
    bounded at every uncovered cell. Four corners must touch actual support.
    This is a geometric visual heuristic, not load-bearing certification.
    """
    lower, upper, surfaces = tuple(lower), tuple(upper), tuple(surfaces)
    if (len(lower) != 2 or len(upper) != 2
            or not all(math.isfinite(v) for v in (*lower, *upper, max_gap, max_height_delta, min_coverage))
            or any(a >= b for a, b in zip(lower, upper))
            or min(max_gap, max_height_delta) < 0 or not 0 < min_coverage <= 1):
        raise ValueError('Invalid footprint or composite support policy')
    if len({s.surface_id for s in surfaces}) != len(surfaces):
        raise ValueError('Surface IDs must be unique')
    touching = [s for s in surfaces if s.verified and all(
        min(upper[k], s.upper[k]) - max(lower[k], s.lower[k]) > EPS for k in (0, 1))]
    if not touching:
        return SupportResult(False, 0, None, (), None, 'no_verified_support')
    top = max(s.z_max for s in touching)
    # A mesh can contain a thin rim/side wall.  Height compatibility is based
    # on each candidate's upper support elevation, not its lowest mesh point.
    active = [s for s in touching if top - s.z_max <= max_height_delta + EPS]
    xs = sorted({lower[0], upper[0], *(max(lower[0], min(upper[0], x))
                                     for s in active for x in (s.lower[0], s.upper[0]))})
    ys = sorted({lower[1], upper[1], *(max(lower[1], min(upper[1], y))
                                     for s in active for y in (s.lower[1], s.upper[1]))})
    def supported(x, y):
        return any(s.lower[0] - EPS <= x <= s.upper[0] + EPS
                   and s.lower[1] - EPS <= y <= s.upper[1] + EPS for s in active)
    grid = [[supported((xs[i] + xs[i+1])/2, (ys[j] + ys[j+1])/2)
             for j in range(len(ys)-1)] for i in range(len(xs)-1)]
    area, largest_gap = 0.0, 0.0
    for i, j in product(range(len(xs)-1), range(len(ys)-1)):
        if grid[i][j]:
            area += (xs[i+1] - xs[i]) * (ys[j+1] - ys[j])
            continue
        a = b = i
        c = d = j
        while a > 0 and not grid[a-1][j]:
            a -= 1
        while b+1 < len(grid) and not grid[b+1][j]:
            b += 1
        while c > 0 and not grid[i][c-1]:
            c -= 1
        while d+1 < len(grid[i]) and not grid[i][d+1]:
            d += 1
        largest_gap = max(largest_gap, min(xs[b+1] - xs[a], ys[d+1] - ys[c]))
    coverage = min(1.0, area / ((upper[0] - lower[0]) * (upper[1] - lower[1])))
    corners = all(supported(x, y) for x, y in product(*zip(lower, upper)))
    accepted = corners and coverage + EPS >= min_coverage and largest_gap <= max_gap + EPS
    reason = 'supported' if accepted else 'insufficient_or_uneven_support'
    return SupportResult(accepted, coverage, largest_gap, tuple(sorted(s.surface_id for s in active)), top, reason)


def placement_candidates(box_id, size, surfaces, loaded, *, max_gap, max_height_delta,
                 min_coverage, edge_margin, placement_gap, max_top):
    """First deterministic, nonoverlapping base-layer placement; None if none.

    Fixed surfaces are never returned as moveable cargo. This first-stage
    planner does not yet stack new boxes on new boxes or plan their slides.
    """
    surfaces, loaded, size = tuple(surfaces), tuple(loaded), tuple(size)
    if (not box_id or any(p.box_id == box_id for p in loaded) or len(size) != 3
            or not all(math.isfinite(v) and v > 0 for v in size)
            or not all(math.isfinite(v) for v in (edge_margin, placement_gap, max_top))
            or min(edge_margin, placement_gap) < 0):
        raise ValueError('Invalid cargo placement input')
    verified = [s for s in surfaces if s.verified]
    if not verified:
        return None
    # Previously placed boxes become explicit, axis-aligned support surfaces.
    # They remain occupied geometry, so the overlap check below still requires
    # a placement gap in Z and prevents horizontal interpenetration.
    loaded_supports = tuple(
        LidSurface(p.box_id, (p.bounds.lower[0], p.bounds.lower[1]),
                   (p.bounds.upper[0], p.bounds.upper[1]),
                   p.bounds.upper[2], p.bounds.upper[2], verified=True)
        for p in loaded)
    support_surfaces = tuple(verified) + loaded_supports
    axes = []
    for k in (0, 1):
        values = {v for s in support_surfaces for v in (s.lower[k] + edge_margin,
                                               s.upper[k] - edge_margin - size[k])}
        values.update(v for p in loaded for v in (p.bounds.upper[k] + placement_gap,
                                                  p.bounds.lower[k] - placement_gap - size[k]))
        axes.append(sorted(values))
    candidates = [(x, y, edge_margin)
                  for x, y in product(*axes)]
    # A box stacked on a previously placed box may use that box's exact
    # footprint. Requiring the outer support margin again would make an equal-
    # size visual stack impossible, so the occupied box itself is the support
    # boundary and the mandatory placement gap is enforced in Z below.
    candidates.extend((p.bounds.lower[0], p.bounds.lower[1], 0.0)
                      for p in loaded)
    for x, y, margin in candidates:
        lower = (x - margin, y - margin)
        upper = (x + size[0] + margin, y + size[1] + margin)
        support = evaluate_support(lower, upper, support_surfaces, max_gap=max_gap,
            max_height_delta=max_height_delta, min_coverage=min_coverage)
        if not support.accepted:
            continue
        actual = evaluate_support((x, y), (x + size[0], y + size[1]), support_surfaces,
            max_gap=max_gap, max_height_delta=max_height_delta, min_coverage=min_coverage)
        if (not actual.accepted
                or abs(support.top_z - actual.top_z) > max_height_delta + EPS):
            continue
        z = actual.top_z + placement_gap
        bounds = Bounds((x, y, z), (x + size[0], y + size[1], z + size[2]))
        if bounds.upper[2] > max_top + EPS:
            continue
        if any(not any(bounds.upper[k] + placement_gap <= p.bounds.lower[k] + EPS
                       or p.bounds.upper[k] + placement_gap <= bounds.lower[k] + EPS
                       for k in range(3)) for p in loaded):
            continue
        yield CargoPlacement(box_id, bounds, actual.support_ids)
    return None


def plan_on_lids(box_id, size, surfaces, loaded, **policy):
    """Baseline greedy placement, preserved for comparison."""
    return next(placement_candidates(box_id,size,surfaces,loaded,**policy),None)


@dataclass(frozen=True)
class FullLoadPlan:
    placements: tuple
    complete: bool
    examined: int
    reason: str


def plan_full_load(boxes, surfaces, *, max_center_height, clearance,
                   max_states=256, worker_position=None, stack_second_on_first=False, **policy):
    """Bounded fixed-order lookahead, maximizing the feasible prefix.

    No source reordering, support relocation, automatic rotation or relaxed
    height limits. Failure is only failure within this candidate search.
    """
    boxes, surfaces = tuple(boxes), tuple(surfaces)
    if (type(max_states) is not int or max_states < 1
            or not math.isfinite(max_center_height)
            or not math.isfinite(clearance) or clearance < 0
            or len({b[0] for b in boxes}) != len(boxes)):
        raise ValueError('Invalid full-load search inputs')
    best, examined = (), 0
    direction=None
    if worker_position is not None:
        verified=[s for s in surfaces if s.verified]
        if not verified:
            return FullLoadPlan((),False,0,'no_verified_support')
        center=tuple((min(s.lower[k] for s in verified)+max(s.upper[k] for s in verified))/2
                     for k in (0,1))
        length=math.dist(center,worker_position[:2])
        if not math.isfinite(length) or length<1e-6:
            raise ValueError('Worker position cannot define pallet front/back')
        direction=tuple((worker_position[k]-center[k])/length for k in (0,1))
    def visit(loaded):
        nonlocal best, examined
        if len(loaded) > len(best):
            best = loaded
        if len(loaded) == len(boxes):
            return True
        box_id,size = boxes[len(loaded)]
        for p in placement_candidates(box_id,size,surfaces,loaded,
                max_top=max_center_height+size[2]/2-clearance,**policy):
            if stack_second_on_first and len(loaded)==1:
                base=loaded[0].bounds
                if (abs(p.bounds.lower[2]-base.upper[2]-policy.get('placement_gap',0))>1e-5
                        or any(p.bounds.lower[k]<base.lower[k]-1e-6 or
                               p.bounds.upper[k]>base.upper[k]+1e-6 for k in (0,1))):
                    continue
            if direction is not None:
                projection=sum(((p.bounds.lower[k]+p.bounds.upper[k])/2-center[k])*direction[k]
                               for k in (0,1))
                if (len(loaded)<2 and projection>=0) or (len(loaded)>=2 and projection<=0):
                    continue
            if examined >= max_states:
                return False
            examined += 1
            if visit((*loaded,p)):
                return True
        return False
    complete = visit(())
    return FullLoadPlan(best,complete,examined,'complete' if complete else
                       'search_limit' if examined >= max_states else 'no_full_candidate')
