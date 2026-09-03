> Last updated: 2026-08-15 21:16 KST

# Overview Palette and LIMO Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align both robot-control architecture PNGs with the visual language of `overview.png`, remove unnecessary borders, and replace every robot illustration with the specified RobotLAB LIMO image.

**Architecture:** Rebuild the diagrams as deterministic raster graphics so topic spelling, arrow endpoints, and layout remain exact. Use a background-isolated LIMO source as a composited bitmap and verify all current-behavior labels against production Python code.

**Tech Stack:** Python/Pillow raster composition, ImageMagick inspection, repository shell checks

## Global Constraints

- Do not start or publish to ROS2, Isaac Sim, Ollama, Flask, or a real robot.
- Preserve exact ROS2 topic and HTTP endpoint spelling.
- Clearly distinguish current code behavior from future/proposed architecture.
- Modify only the requested PNGs, their explanation, and lightweight design/plan records.

---

### Task 1: Rebuild the current implementation diagram

**Files:**
- Modify: `ictc_test/robot_motion_control_current.png`

**Interfaces:**
- Consumes: production topic names and process boundaries
- Produces: one 1672×941 PNG describing verified current control flow

- [x] Sample the palette and geometry from `ictc_test/overview.png`.
- [x] Render only the key sensor, decision, VLM, controller, safety, command, and feedback paths.
- [x] Remove the saturated outer frame and composite the exact LIMO cutout.
- [x] Inspect the rendered PNG at full resolution for clipped text and ambiguous arrows.

### Task 2: Rebuild the target architecture diagram

**Files:**
- Modify: `ictc_test/robot_motion_control_future.png`

**Interfaces:**
- Consumes: the verified current baseline and explicitly proposed target components
- Produces: one 1672×941 PNG with visually distinct current and proposed sections

- [x] Reuse the same palette, typography, arrow labels, and border weight as Task 1.
- [x] Remove decorative lane frames while keeping current and proposed regions unmistakable.
- [x] Preserve the single-publisher target, safety supervisor, fallback stop, and state feedback.
- [x] Composite the exact LIMO cutout and inspect the rendered PNG at full resolution.

### Task 3: Synchronize explanation and verify artifacts

**Files:**
- Modify: `ictc_test/robot_motion_control_architecture_explanation.txt`

**Interfaces:**
- Consumes: final PNG content
- Produces: a concise explanation aligned with the final images and production code

- [x] Update the explanation for the simplified layout, palette, border removal, and LIMO source.
- [x] Verify image dimensions, topic strings, arrow connectivity, and sampled colors.
- [x] Run `bash scripts/check.sh` and `bash scripts/test_offline.sh`.
- [x] Review `git diff` and `git status` to confirm only scoped files changed.
