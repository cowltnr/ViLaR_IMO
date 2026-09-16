"""Configuration and rigid-offset calculation for the shelf approach experiment."""

import math

CART_GOAL_WORLD = (-7.4385, 19.7861, 0.0)
WAIT_SECONDS = 10.0
MAX_SNAP_M = 0.15
MAX_WORKER_CART_DISTANCE_M = 2.5
FACE_BOX_ENABLED = True
BOX_TARGET_PATH = "/World/Environment/Warehouse/Box_26000/SM_CardBoxC_01"
TURN_DURATION_SECONDS = 3.0
# Current character pushing arrangement suggests local -Y is its forward axis.
WORKER_FORWARD_YAW_DEG = -90.0
ARRIVAL_TOLERANCE_M = 0.25
BOX_TRANSFER_ENABLED = True
UPPER_PALLET_PATH = "/World/DynamicActors/CartAssembly/o3dyn_pallet_upper"
PALLET_TARGET_PATH = "/World/DynamicActors/CartAssembly/o3dyn_pallet_lower"
RACK_TARGET_PATH = "/World/Environment/Warehouse/SM_RackShelf_4475/SM_RackShelf_01"
BOX_TRANSFER_DELAY_SECONDS = 1.0
BOX_TRANSFER_DURATION_SECONDS = 8.0
BOX_PALLET_EDGE_MARGIN_M = 0.02
BOX_PLACEMENT_GAP_M = 0.01
BOX_PULL_MARGIN_M = 0.10
BOX_LIFT_CLEARANCE_M = 0.03
BOX_LIMIT_TO_ARM_REACH = True
BOX_MAX_PULL_M = 3.0
# Experimental approach-only mode: leave the box on the shelf until arm IK is ready.
WORKER_APPROACH_ENABLED = False
WORKER_FORWARD_AFTER_TURN = True
WORKER_FORWARD_STEP_M = .05
WORKER_APPROACH_DISTANCES_M = (0.55, 0.65)
WORKER_APPROACH_ANGLES_DEG = (0, -15, 15, -30, 30)
WORKER_APPROACH_MAX_DISTANCE_M = 0.75
WORKER_APPROACH_TIMEOUT_SECONDS = 60.0
# Visual-only reach. Disable to reproduce the verified face/box-transfer baseline.
WORKER_REACH_ENABLED = True
WORKER_REACH_SECONDS = 2.0
WORKER_REACH_LOWER_SECONDS = 2.0
WORKER_REACH_DISTANCE_M = 0.40
WORKER_REACH_MODE = "box_synced"  # "timed" preserves the previous gesture baseline.
WORKER_BOX_TURN_RATE_DEG_S = 45.0
WORKER_HAND_HEIGHT_FEEDBACK = True
WORKER_HAND_HEIGHT_MAX_CORRECTION_M = .10
WORKER_HAND_HEIGHT_RESPONSE_SECONDS = .30


def worker_goal_for_cart(worker_position, cart_position, cart_goal):
    """Keep the initial heading at arrival; all positions are in World meters."""
    if any(len(p) != 3 or not all(math.isfinite(v) for v in p)
           for p in (worker_position, cart_position, cart_goal)):
        raise ValueError("Positions must contain three finite values")
    return tuple(cart_goal[i] - (cart_position[i] - worker_position[i]) for i in range(3))
