> Last updated: 2026-08-15 21:16 KST

# Robot Motion Control Diagram Corrections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct both robot motion-control PNGs so their current interfaces, limitations, and current-versus-target classifications agree with production code.

**Architecture:** Perform one reference-guided edit for each existing PNG while preserving its layout and pastel visual language. The current diagram receives a compact ROS2 sensor-process to HTTP-gateway boundary; the target diagram uses a single gateway abstraction and literal solid-current/dotted-target classification.

**Tech Stack:** Built-in `image_gen`, local `view_image`, PNG metadata inspection, repository source inspection

## Global Constraints

- Replace only `ictc_test/robot_motion_control_current.png` and `ictc_test/robot_motion_control_future.png`, as explicitly approved.
- Preserve `ictc_test/overview.png` and `ictc_test/IETF125.png`.
- Preserve the 1672×941 landscape layout, rounded geometry, and pastel palette where practical.
- Preserve exact spelling of ROS2 topics, HTTP endpoints, TF frames, and message types.
- Do not start or publish to ROS2, Isaac Sim, Flask, Ollama, or any robot process.
- Do not represent operational policy as code-enforced behavior.

---

### Task 1: Correct the current-state diagram

**Files:**
- Modify: `ictc_test/robot_motion_control_current.png`
- Reference: `ictc_test/overview.png`
- Reference: `ictc_test/IETF125.png`

**Interfaces:**
- Consumes: verified interfaces in `imo_server_lidar.py`, `edge_threads/infer_thread.py`, `waypoint_tools/intent_decision.py`, `waypoint_tools/point_follower.py`, and `waypoint_tools/pure_pursuit_follower.py`
- Produces: a current-state PNG that distinguishes active control paths, partial file state, operational constraints, ROS2 topics, HTTP endpoints, and the compact sensor process boundary

- [x] **Step 1: Load the edit target at original resolution**

  Inspect `ictc_test/robot_motion_control_current.png` before invoking image generation.

- [x] **Step 2: Apply one reference-guided correction**

  Require `ROS2 Sensor Process → Queue / Shared State → Flask HTTP Sensor Gateway`, separate inactive Intent YAML, remove normal `Continue`, separate VLM selection from edge stop handling, and qualify controller exclusion plus both implementation caveats.

- [x] **Step 3: Save the accepted correction**

  Copy the selected built-in output over `ictc_test/robot_motion_control_current.png` without modifying either reference image.

- [x] **Step 4: Validate current-state content**

  Inspect the final image at original resolution and verify the exact topics, HTTP endpoints, TF lookup, caveats, arrow directions, and process abstraction.

### Task 2: Correct the target-state diagram

**Files:**
- Modify: `ictc_test/robot_motion_control_future.png`
- Reference: `ictc_test/robot_motion_control_current.png`
- Reference: `ictc_test/overview.png`

**Interfaces:**
- Consumes: corrected current-state terminology and the approved current-versus-target classification
- Produces: a target-state PNG with a solid current sensor gateway, current VLM and predefined route capabilities, and dotted target planning/safety/arbitration components

- [x] **Step 1: Load the edit target at original resolution**

  Inspect `ictc_test/robot_motion_control_future.png` before invoking image generation.

- [x] **Step 2: Apply one reference-guided correction**

  Replace the left process detail with solid `ROS2-to-HTTP Sensor Gateway`; show current `IntentDecisionNode`, `Predefined Route Matching`, `VLM Route Selection`, and `Threshold Stop Checks`; mark the true global planner, deterministic supervisor, and remaining future modules as dotted `Target`.

- [x] **Step 3: Save the accepted correction**

  Copy the selected built-in output over `ictc_test/robot_motion_control_future.png` without modifying the current image or references.

- [x] **Step 4: Validate target-state content**

  Inspect the final image at original resolution and verify literal legend usage, no direct VLM-to-actuation path, current direct follower publication versus target command arbitration, and all fault-to-safe-stop paths.

### Task 3: Verify both corrected assets

**Files:**
- Review: `ictc_test/robot_motion_control_current.png`
- Review: `ictc_test/robot_motion_control_future.png`

**Interfaces:**
- Consumes: both corrected PNGs
- Produces: file-format evidence, source-alignment review, and a handoff listing any residual text-rendering limitation

- [x] **Step 1: Verify PNG metadata**

  Run `file` and `identify` for both images. Expected: two readable, non-empty landscape PNGs.

- [x] **Step 2: Run the repository static/offline check**

  Run `bash scripts/check.sh`. Expected: exit code 0 without starting live robot or simulator processes.

- [x] **Step 3: Review the final change scope**

  Run `git status --short` and confirm no unrelated file was modified by this correction pass.
