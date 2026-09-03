> Last updated: 2026-08-15 21:16 KST

# Architecture Arrow Clarity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct ambiguous, disconnected, and directionally incorrect arrows in both ROS2 motion-control architecture PNGs.

**Architecture:** Apply localized raster edits using production-code-supported producer/consumer relationships. Preserve the current/target visual grammar and make route, stop, VLM, logging, controller-command, and feedback paths individually traceable.

**Tech Stack:** PNG raster editing, image generation/editing, static Python source inspection, shell verification

## Global Constraints

- Do not start ROS2, Flask, Ollama, Isaac Sim, or robot processes.
- Do not publish any ROS2 topic.
- Preserve the RobotLAB LIMO image, 1672×941 dimensions, and established palette.
- Use production code as the source of truth for all solid/current arrows.

---

### Task 1: Repair current architecture flow

**Files:**
- Modify: `ictc_test/robot_motion_control_current.png`

- [x] Replace the orphan VLM line with a direct bidirectional `Edge Safety Decision ↔ VLM Route Selection` connection.
- [x] Route sensor HTTP data to fusion, fusion output to edge safety, intent state to edge safety, and route/stop topics to the selected controller.
- [x] Merge route-select and emergency stop conditions into one explicit `/navigation_stop = "stop"` controller input while preserving their different thresholds and semantics.

### Task 2: Repair target architecture flow

**Files:**
- Modify: `ictc_test/robot_motion_control_future.png`

- [x] Correct all solid/current arrow directions and direct each endpoint to the responsible current component.
- [x] Connect every dotted target planning, safety, fallback, arbitration, coordination, and state-feedback component into a continuous labeled path.
- [x] Remove orphan segments and retain an unambiguous legend distinction between solid, dotted green, and dashed blue paths.

### Task 3: Explain and verify

**Files:**
- Modify: `ictc_test/robot_motion_control_architecture_explanation.txt`

- [x] Explain the clarified VLM request/result path and both `/navigation_stop` conditions.
- [x] Inspect both images at original resolution and confirm that every arrow has an identifiable source and destination.
- [x] Run `bash scripts/check.sh` and `bash scripts/test_offline.sh`, then report any remaining conceptual-only target assumptions.
