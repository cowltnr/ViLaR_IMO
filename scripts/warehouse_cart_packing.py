"""Conservative axis-aligned packing in the verified pallet's local frame.

Pure geometry only: a layout is NOT a validated Worker/box transport path.
Bounds preserve box orientation using enclosing AABBs; no automatic rotations.
An enclosing AABB is NOT a support polygon. Only explicitly verified, filled,
axis-aligned tops may be marked stackable; the default refuses stacking on them.
"""

from dataclasses import dataclass
from collections import deque
from itertools import product
import math

EPS = 1e-8


@dataclass(frozen=True)
class Bounds:
    lower: tuple
    upper: tuple

    def __post_init__(self):
        for name in ('lower', 'upper'):
            values = tuple(getattr(self, name))
            if len(values) != 3 or not all(math.isfinite(v) for v in values):
                raise ValueError('Bounds require three finite coordinates')
            object.__setattr__(self, name, values)
        if any(a >= b for a, b in zip(self.lower, self.upper)):
            raise ValueError('Bounds must have positive volume')

    @property
    def size(self):
        return tuple(b - a for a, b in zip(self.lower, self.upper))


@dataclass(frozen=True)
class Placement:
    box_id: str
    bounds: Bounds
    support_id: str
    stackable: bool = False

    def __post_init__(self):
        if type(self.stackable) is not bool:
            raise ValueError('stackable requires an explicit bool after support verification')


@dataclass(frozen=True)
class Slide:
    box_id: str
    start: Bounds
    end: Bounds


@dataclass(frozen=True)
class LoadPlan:
    placement: Placement
    slides: tuple
    placements: tuple


def _inside_xy(box, support, margin):
    return all(box.lower[k] >= support.lower[k] + margin - EPS
               and box.upper[k] <= support.upper[k] - margin + EPS for k in (0, 1))


def _separated(a, b, gap):
    return any(a.upper[k] + gap <= b.lower[k] + EPS
               or b.upper[k] + gap <= a.lower[k] + EPS for k in range(3))


def _validate(surface, loaded, margin, gap, max_top):
    if (not all(math.isfinite(v) for v in (margin, gap, max_top))
            or min(margin, gap) < 0 or max_top <= surface.upper[2]):
        raise ValueError('Invalid packing clearance or height limit')
    by_id = {p.box_id: p for p in loaded}
    if len(by_id) != len(loaded) or any(not p.box_id or p.box_id == 'pallet' for p in loaded):
        raise ValueError('Box IDs must be unique, nonempty and not pallet')
    for i, box in enumerate(loaded):
        if box.support_id == 'pallet':
            support = surface
        elif (box.support_id in by_id and box.support_id != box.box_id
              and by_id[box.support_id].stackable):
            support = by_id[box.support_id].bounds
        else:
            raise ValueError('Missing or cyclic support')
        if (not _inside_xy(box.bounds, surface, margin)
                or not _inside_xy(box.bounds, support, 0)
                or abs(box.bounds.lower[2] - support.upper[2] - gap) > EPS
                or box.bounds.upper[2] > max_top + EPS):
            raise ValueError('Unsupported, outside or overheight initial box')
        if any(not _separated(box.bounds, other.bounds, gap) for other in loaded[:i]):
            raise ValueError('Initial boxes overlap or violate gap')


def _candidates(size, support, obstacles, margin, gap):
    axes = []
    for k in (0, 1):
        low, high = support.lower[k] + margin, support.upper[k] - margin - size[k]
        if high < low - EPS:
            return
        values = {low, high}
        for box in obstacles:
            values.update((box.bounds.upper[k] + gap, box.bounds.lower[k] - gap - size[k]))
        axes.append(sorted(v for v in values if low - EPS <= v <= high + EPS))
    for x, y in product(*axes):
        lower = (x, y, support.upper[2] + gap)
        yield Bounds(lower, tuple(lower[k] + size[k] for k in range(3)))


def _direct(box_id, size, surface, loaded, margin, gap, max_top, stackable):
    supports = [('pallet', surface, margin)] + [
        (p.box_id, p.bounds, 0) for p in sorted(loaded, key=lambda p: (p.bounds.upper[2], p.box_id))
        if p.stackable]
    for support_id, support, inset in supports:
        for bounds in _candidates(size, support, loaded, inset, gap):
            if (bounds.upper[2] <= max_top + EPS and _inside_xy(bounds, surface, margin)
                    and all(_separated(bounds, other.bounds, gap) for other in loaded)):
                return Placement(box_id, bounds, support_id, stackable)
    return None


def can_slide(moving, destination, surface, loaded, *, margin, gap):
    """Conservative continuous sweep: never move a support or leave the pallet.

    The enclosing sweep may reject feasible diagonal paths; it cannot miss an
    AABB collision along the proposed straight translation.
    """
    loaded = tuple(loaded)
    if (not all(math.isfinite(v) and v >= 0 for v in (margin, gap))
            or moving not in loaded or moving.support_id != 'pallet'
            or any(p.support_id == moving.box_id for p in loaded)
            or any(abs(a - b) > EPS for a, b in zip(moving.bounds.size, destination.size))
            or abs(destination.lower[2] - moving.bounds.lower[2]) > EPS
            or abs(moving.bounds.lower[2] - surface.upper[2] - gap) > EPS
            or not _inside_xy(moving.bounds, surface, margin)
            or not _inside_xy(destination, surface, margin)):
        return False
    sweep = Bounds(tuple(min(a, b) for a, b in zip(moving.bounds.lower, destination.lower)),
                   tuple(max(a, b) for a, b in zip(moving.bounds.upper, destination.upper)))
    return all(_separated(sweep, p.bounds, gap) for p in loaded if p.box_id != moving.box_id)


def _state_key(placements):
    return tuple((p.box_id, p.support_id, p.stackable, *(round(v, 8) for v in (*p.bounds.lower, *p.bounds.upper)))
                 for p in placements)


def plan_load(box_id, size, surface, loaded, *, margin, gap, max_top,
              max_relocations=2, max_states=256, stackable=False):
    """Return a geometry plan or None; invalid inputs raise before any mutation."""
    loaded, size = tuple(loaded), tuple(size)
    if type(stackable) is not bool:
        raise ValueError('stackable requires an explicit bool after support verification')
    if len(size) != 3 or not all(math.isfinite(v) and v > 0 for v in size):
        raise ValueError('Box size must have three finite positive dimensions')
    _validate(surface, loaded, margin, gap, max_top)
    if not box_id or box_id == 'pallet' or any(p.box_id == box_id for p in loaded):
        raise ValueError('New box must have a unique ID')
    if (type(max_relocations) is not int or max_relocations < 0
            or type(max_states) is not int or max_states < 1):
        raise ValueError('Search limits must be nonnegative depth and positive state count')
    placement = _direct(box_id, size, surface, loaded, margin, gap, max_top, stackable)
    if placement is not None:
        return LoadPlan(placement, (), (*loaded, placement))
    queue = deque([(loaded, ())])
    visited = {_state_key(loaded)}
    while queue:
        current, slides = queue.popleft()
        if len(slides) >= max_relocations:
            continue
        for index, moving in enumerate(current):
            for end in _candidates(moving.bounds.size, surface, current, margin, gap):
                if not can_slide(moving, end, surface, current, margin=margin, gap=gap):
                    continue
                candidate = (*current[:index], Placement(moving.box_id, end, 'pallet', moving.stackable),
                             *current[index+1:])
                key = _state_key(candidate)
                if key in visited:
                    continue
                if len(visited) >= max_states:
                    return None  # Finite search exhausted, not proof of geometric impossibility.
                visited.add(key)
                moves = (*slides, Slide(moving.box_id, moving.bounds, end))
                placement = _direct(box_id, size, surface, candidate, margin, gap, max_top, stackable)
                if placement is not None:
                    return LoadPlan(placement, moves, (*candidate, placement))
                queue.append((candidate, moves))
    return None
