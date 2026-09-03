> Last updated: 2026-08-15 21:16 KST

# Robot Motion Control Architecture Images Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate two readable PNG diagrams that visualize the implemented and target robot motion-control architectures while matching `ictc_test/overview.png`.

**Architecture:** Use `overview.png` as the style/composition reference and `IETF125.png` as the control-command flow reference for two independent image-generation passes. Validate each pass visually and by file metadata, then place the accepted files under `ictc_test/` without changing runtime code or starting robot-related processes.

**Tech Stack:** Built-in `image_gen`, local `view_image`, PNG metadata inspection

## Global Constraints

- Preserve `ictc_test/overview.png`; do not overwrite it.
- Preserve `ictc_test/IETF125.png`; do not overwrite it.
- Save final files as `ictc_test/robot_motion_control_current.png` and `ictc_test/robot_motion_control_future.png`.
- Use a wide landscape composition near the reference's 1843:926 aspect ratio.
- Match `overview.png` arrow and box colors; any additional semantic colors must
  remain low-saturation pastels.
- Preserve exact spelling of ROS2 topics and code-facing labels.
- Show proposed features with dotted borders and `Target` tags.
- Do not start ROS2, Isaac Sim, Flask, Ollama, or robot processes.
- Do not publish any ROS2 topic or alter robot state.

---

### Task 1: Generate and validate the current-state architecture

**Files:**
- Reference: `ictc_test/overview.png`
- Reference: `ictc_test/IETF125.png`
- Create: `ictc_test/robot_motion_control_current.png`

**Interfaces:**
- Consumes: the approved design in `docs/superpowers/specs/2026-08-13-robot-motion-control-architecture-design.md`
- Produces: a PNG showing the code-grounded sensing, route/safety decision, selectable controller, actuation, and feedback paths

- [x] **Step 1: Generate one current-state candidate**

  Use the built-in image generation tool with `ictc_test/overview.png` and `ictc_test/IETF125.png` as reference images. Require exact `SUB`, `PUB`, and `TF` relationships for `/sim/camera/color/image_raw`, `/sim/scan`, `/sim/odom`, `/user_intent_goal`, `/selected_route`, `/selected_route_goal`, `/navigation_stop`, `/intent_feedback`, and `/sim/cmd_vel`.

- [x] **Step 2: Save the candidate non-destructively**

  Copy the generated candidate to `ictc_test/robot_motion_control_current.png`; never replace `ictc_test/overview.png`.

- [x] **Step 3: Inspect at original resolution**

  Check container hierarchy, arrow direction, clipping, controller exclusivity, safety priority, topic spelling, and the separated `Implementation Caveat` callout.

- [x] **Step 4: Correct only material defects**

  If the candidate has unreadable or incorrect critical labels, perform one targeted regeneration that preserves the accepted composition and fixes the named defects.

- [x] **Step 5: Verify the PNG**

  Run `file ictc_test/robot_motion_control_current.png` and `identify ictc_test/robot_motion_control_current.png`. Expected: a readable, non-empty landscape PNG.

### Task 2: Generate and validate the target-state architecture

**Files:**
- Reference: `ictc_test/overview.png`
- Reference: `ictc_test/IETF125.png`
- Create: `ictc_test/robot_motion_control_future.png`

**Interfaces:**
- Consumes: the approved design and the current-state visual language
- Produces: a PNG showing hierarchical planning, deterministic safety, controller management, command arbitration, health monitoring, safe fallback, and proposed multi-robot coordination

- [x] **Step 1: Generate one target-state candidate**

  Use the built-in image generation tool with both reference images. Require solid borders for current capabilities, dotted borders plus `Target` tags for proposed capabilities, and explicit current `SUB`, `PUB`, and `TF` badges without inventing proposed ROS2 topic names.

- [x] **Step 2: Save the candidate non-destructively**

  Copy the generated candidate to `ictc_test/robot_motion_control_future.png` without altering the reference or current-state image.

- [x] **Step 3: Inspect at original resolution**

  Check that `VLM Route Advisor` cannot bypass `Deterministic Safety Supervisor`, `Command Arbitration` is the only command output, and all fault paths lead to `Safe Stop`.

- [x] **Step 4: Correct only material defects**

  If the current/target distinction or critical labels are ambiguous, perform one targeted regeneration preserving accepted areas.

- [x] **Step 5: Verify the PNG**

  Run `file ictc_test/robot_motion_control_future.png` and `identify ictc_test/robot_motion_control_future.png`. Expected: a readable, non-empty landscape PNG.

### Task 3: Final cross-image review and handoff

**Files:**
- Review: `ictc_test/robot_motion_control_current.png`
- Review: `ictc_test/robot_motion_control_future.png`

**Interfaces:**
- Consumes: both validated image files
- Produces: a final comparison confirming consistent style and an explicit list of any remaining visual or factual limitations

- [x] **Step 1: Compare both images**

  Confirm consistent palette, rounded geometry, shadows, title hierarchy, major placement, and aspect ratio.

- [x] **Step 2: Review repository changes**

  Run `git status --short` and restrict the handoff to the two requested PNGs plus the approved design/plan records. Do not modify unrelated files.

- [x] **Step 3: Report paths and generation method**

  Provide clickable paths for both PNGs, state that the built-in image generator was used, summarize the final prompts, and disclose any text-rendering limitations.
