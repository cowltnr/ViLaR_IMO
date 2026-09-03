> Last updated: 2026-08-15 21:16 KST

# LIMO Robot Image Replacement Design

## Goal

Replace only the robot illustration in the current and target ROS2 motion-control architecture PNGs with the user-supplied RobotLAB LIMO reference, while correcting any diagram statements that disagree with the checked-in production code.

## Approved approach

- Preserve the 1672×941 canvas, overview-inspired rounded boxes, pastel palette, ROS2 topic labels, arrows, and `Ego Vehicle` caption.
- Isolate the LIMO subject from the 4000×4000 reference and fit it inside each existing `Robot Actuation` card.
- Use localized raster editing rather than regenerating the complete diagrams, because text and connector fidelity are more important than stylistic reinterpretation.
- Treat production Python as the source of truth. Solid/current claims must match current code; dotted green elements in the target image remain explicitly proposed capabilities.

## Code-audit corrections

The static review must ensure the final images communicate these verified facts:

- `imo_server_lidar.py` runs the ROS2 subscriber node in a `multiprocessing.Process`; Flask remains in the main process, with `multiprocessing.Queue` and a `Manager` dictionary/lock for transfer.
- That subscriber consumes `/sim/camera/color/image_raw`, `/sim/scan`, and `/sim/odom`.
- `edge_control.py` launches five worker threads for capture, odometry polling, LiDAR polling, inference/decision, and log sending.
- Startup helper readers also subscribe to `/sim/camera/camera_info` and `/sim/scan` while resolving camera FOV and LiDAR length.
- The active controllers subscribe to `/selected_route`, `/selected_route_goal`, and `/navigation_stop`, use TF `odom → base_link`, and each can publish `/sim/cmd_vel`; only one controller may run.
- `intent_server.py` is a policy YAML receiver, not the ROS2 intent-decision node. Its `/received_policy.yaml` write path does not match the configured relative read path, and the associated distance-control call is inactive.
- Current caveats remain visible: intent-state writing is incomplete, VLM handling can duplicate `/selected_route`, and command arbitration is not implemented.

## Verification

- Visually inspect both output images at original resolution.
- Confirm dimensions and PNG format.
- Re-run repository static/offline checks without starting ROS2, Flask, Ollama, Isaac Sim, or robot processes.
- Update one plain-text explanation file so it describes the final PNGs and distinguishes verified, partial, and target behavior.
