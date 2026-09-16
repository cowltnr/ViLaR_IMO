"""Random connected NavMesh goals.

This module only queries navigation data.
It does not move Worker/Cart, start Play, bake, or save USD.
"""

import math
import random

from scripts import warehouse_roaming_config as config
from scripts.configure_warehouse_worker_behavior import (
    validate_destination_path,
)


def as_point(value):
    if value is None:
        return None

    point = tuple(float(value[i]) for i in range(3))

    if not all(math.isfinite(v) for v in point):
        return None

    return point


class RoamingGoalPicker:
    def __init__(self, seed=config.RANDOM_SEED):
        self.random = random.Random(seed)

    def candidate_steps(self, start):
        """Check one candidate per iteration.

        Yields:
            A result dictionary for each candidate.

        Stop iterating after accepted=True.
        If all candidates are rejected, retry later while stopped.
        """
        import carb
        import omni.anim.navigation.core as nav

        start = as_point(start)
        if start is None:
            raise RuntimeError("Invalid Worker start position")

        mesh = nav.acquire_interface().get_navmesh()
        if mesh is None:
            raise RuntimeError("Existing NavMesh is required")

        snapped_start = as_point(
            mesh.query_closest_point(carb.Float3(*start))
        )

        if (
            snapped_start is None
            or math.dist(start, snapped_start)
            > config.MAX_NAVMESH_SNAP_M
        ):
            raise RuntimeError("Worker start is outside NavMesh tolerance")

        for attempt in range(1, config.MAX_GOAL_ATTEMPTS + 1):
            angle = self.random.uniform(0.0, 2.0 * math.pi)
            distance = self.random.uniform(
                config.MIN_GOAL_DISTANCE_M,
                config.MAX_GOAL_DISTANCE_M,
            )

            candidate = (
                start[0] + distance * math.cos(angle),
                start[1] + distance * math.sin(angle),
                start[2],
            )

            if not (
                config.WAREHOUSE_X_RANGE[0]
                <= candidate[0]
                <= config.WAREHOUSE_X_RANGE[1]
                and config.WAREHOUSE_Y_RANGE[0]
                <= candidate[1]
                <= config.WAREHOUSE_Y_RANGE[1]
            ):
                yield {
                    "accepted": False,
                    "attempt": attempt,
                    "reason": "outside_warehouse_bounds",
                }
                continue

            goal = as_point(
                mesh.query_closest_point(carb.Float3(*candidate))
            )

            if (
                goal is None
                or math.dist(candidate, goal)
                > config.MAX_NAVMESH_SNAP_M
            ):
                yield {
                    "accepted": False,
                    "attempt": attempt,
                    "reason": "candidate_outside_navmesh",
                }
                continue

            horizontal_distance = math.dist(start[:2], goal[:2])

            if not (
                config.MIN_GOAL_DISTANCE_M
                <= horizontal_distance
                <= config.MAX_GOAL_DISTANCE_M
            ):
                yield {
                    "accepted": False,
                    "attempt": attempt,
                    "reason": "goal_distance_out_of_range",
                }
                continue

            route = mesh.query_shortest_path(
                start_pos=carb.Float3(*snapped_start),
                end_pos=carb.Float3(*goal),
            )

            points = (
                [as_point(point) for point in route.get_points()]
                if route is not None
                else []
            )

            if any(point is None for point in points):
                yield {
                    "accepted": False,
                    "attempt": attempt,
                    "reason": "invalid_path_points",
                }
                continue

            try:
                validate_destination_path(
                    points,
                    snapped_start,
                    goal,
                )
            except RuntimeError:
                yield {
                    "accepted": False,
                    "attempt": attempt,
                    "reason": "missing_or_disconnected_path",
                }
                continue

            yield {
                "accepted": True,
                "attempt": attempt,
                "goal": goal,
                "points": points,
            }
            return
