"""Separate multi-box experiment inputs; never imported by the single-box launcher."""

BOX_PATHS = (
    '/World/Environment/Warehouse/Box_26000/SM_CardBoxC_01',
    '/World/Environment/Warehouse/Box_26002/SM_CardBoxC_01',
    '/World/Environment/Warehouse/Box_26004/SM_CardBoxC_01',
    '/World/Environment/Warehouse/Box_26006/SM_CardBoxC_01',
)
PALLET_PATH = '/World/DynamicActors/CartAssembly/o3dyn_pallet_lower'
CART_PATH = '/World/DynamicActors/CartAssembly'
WORKER_PATH = '/World/Characters/Worker_01/DHGen/SkelRoot'
WAREHOUSE_PATH = '/World/Environment/Warehouse'
EDGE_MARGIN_M = .02
PLACEMENT_GAP_M = .01
LIFT_CLEARANCE_M = .03
MAX_RELOCATIONS = 2
MAX_SEARCH_STATES = 256
USE_FULL_LOAD_PLAN = True
WALK_WITH_BOX = True
BOX_ONLY_SECONDS = 3.0
STACK_FACE_SECONDS = 0.3
STACK_TURN_RATE_DEG_S = 90.0
STACK_EXTRACTION_OFFSETS_M = (0., .35, .7, 1.)
STACK_MAX_EXTRA_HEIGHT_M = 2.0
STACK_MAX_PATH_CHECKS = 512
STACK_MAX_PLACEMENT_CANDIDATES = 32
STACK_CHECKS_PER_FRAME = 16
STACK_FRAME_BUDGET_SECONDS = .006
STACK_SEARCH_TIMEOUT_SECONDS = 30.0
# User approved visual extraction despite existing lateral box overlap (2026-09-10).
STACK_ALLOW_INITIAL_NEIGHBOUR_OVERLAP = True
STACK_PULL_DISTANCES_M = (.35, .5, .7, 1.0)
STACK_SECOND_ON_FIRST = True
CARRY_HOLD_DISTANCE_M = .65
CARRY_HOLD_HEIGHT_M = 1.10
PICKUP_SECONDS = 2.0
PLACE_SECONDS = 2.0
DROP_WORK_DISTANCES_M = (.8, 1.0, 1.2, 1.4, 1.6)
DROP_WORK_ANGLES_DEG = (0, 180, 45, 135, -45, -135, 90, -90)
SOURCE_SEPARATION_M = .04
SOURCE_SEPARATION_ENABLED = False
WORKER_BODY_RADIUS_M = .30
WORKER_BODY_HEIGHT_M = 1.80
WORKER_RETREAT_STEP_M = .35
WORKER_MAX_RETREATS = 2
WORKER_REPOSITION_DISTANCES_M = (.35, .70)
WORKER_REPOSITION_ANGLES_DEG = (0, 45, -45, 90, -90)
# Read-only probe offsets; these are NOT authorized destinations or contact poses.
PROBE_DISTANCES_M = (.55, .75, 1.0)
PROBE_ANGLES_DEG = tuple(range(0, 360, 45))
MAX_NAVMESH_SNAP_M = .15
# Candidate visual-only composite support policy, not certified physical limits.
COMPOSITE_MAX_GAP_M = .01
COMPOSITE_MAX_HEIGHT_DELTA_M = .002
COMPOSITE_MIN_COVERAGE = .95
ARM_RAISE_SECONDS = 1.0
STACK_GESTURES_ENABLED = True  # Visual arm/heading follow; no physical hand contact.
STACK_BOX_PATHS = BOX_PATHS[:3]  # 26000 -> 26002 -> 26004; other launchers retain four.
STACK_ARM_RAISE_SECONDS = .3
STACK_ARM_LOWER_SECONDS = .3
STACK_HAND_HEIGHT_OFFSET_M = 0.3  # Use a point 30 cm above the center of the box as the hand target
STACK_ALLOW_SIDE_BOX_OVERLAP = True  # Horizontal extraction only, not loaded boxes.
STACK_VISUAL_PULL_DISTANCES_M = (.7, 1.)
ARM_LOWER_SECONDS = 1.0
TRANSFER_SECONDS = 8.0
SLIDE_SECONDS = 2.0
# User-confirmed physical supports, NOT USD parent-child relationships.
SOURCE_PALLET_PATH = '/World/Environment/Warehouse/SM_PaletteA_4582'
SOURCE_SUPPORT_PATHS = {
    BOX_PATHS[0]: '/World/Environment/Warehouse/Box_25976/SM_CardBoxB_01',
    BOX_PATHS[1]: '/World/Environment/Warehouse/Box_25978/SM_CardBoxB_01',
    BOX_PATHS[2]: '/World/Environment/Warehouse/Box_25980/SM_CardBoxB_01',
    BOX_PATHS[3]: '/World/Environment/Warehouse/Box_25982/SM_CardBoxB_01',
}
# User-approved fixed plastic cargo lids. This is a visual-scenario allow-list,
# not a physics/load-bearing certification and does not move these prims.
COMPOSITE_VERIFIED_LID_PATHS = tuple(
    f'{PALLET_PATH}/SM_BoxPlastic_EuroCasePolyethyleneLid_C2_{index:03d}'
    for index in range(9, 17)
)
