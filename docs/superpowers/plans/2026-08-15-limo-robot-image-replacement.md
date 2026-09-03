> Last updated: 2026-08-15 21:16 KST

# LIMO Robot Image Replacement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the robot artwork in both architecture PNGs with the supplied LIMO reference and align all current-behavior labels with production code.

**Architecture:** Keep the existing diagrams intact and use localized raster edits for the actuation cards and any verified correction labels. Current behavior is shown as solid/current; future-only behavior remains dotted green and explicitly marked `Target`.

**Tech Stack:** PNG raster editing, image generation/editing, static Python source inspection, shell verification

## Global Constraints

- Do not start ROS2, Flask, Ollama, Isaac Sim, or robot processes.
- Do not publish any ROS2 topic.
- Preserve all unrelated repository files and generated experiment artifacts.
- Use checked-in production code as the source of truth.

---

### Task 1: Audit diagram claims

**Files:**
- Inspect: `ictc_test/robot_motion_control_current.png`
- Inspect: `ictc_test/robot_motion_control_future.png`
- Inspect: `imo_server_lidar.py`, `edge_control.py`, `edge_threads/*.py`, `waypoint_tools/*.py`, `vlm_server.py`, `k8s_server.py`, `intent_server.py`

- [x] Compare all current ROS2 topics, HTTP endpoints, process/thread boundaries, publishers, and subscribers against source.
- [x] Record only source-supported corrections; keep proposed target capabilities explicitly distinct.

### Task 2: Edit both PNGs

**Files:**
- Modify: `ictc_test/robot_motion_control_current.png`
- Modify: `ictc_test/robot_motion_control_future.png`

- [x] Replace only the robot artwork with the isolated RobotLAB LIMO reference while preserving `Ego Vehicle`.
- [x] Apply the audited process/topic corrections without changing the established palette and rounded-box style.
- [x] Inspect both images at original resolution and correct any text or connector damage.

### Task 3: Explain and verify

**Files:**
- Create: `ictc_test/robot_motion_control_architecture_explanation.txt`

- [x] Describe each final PNG in plain Korean, including verified current behavior, known caveats, and proposed target behavior.
- [x] Verify PNG format/dimensions and run `bash scripts/check.sh` plus `bash scripts/test_offline.sh`.
- [x] Review `git diff`/status and report only intended changes and remaining limitations.
