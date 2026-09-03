> Last updated: 2026-08-15 21:16 KST

# SLAM and I2ICF Research Direction Presentation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. This task is executed inline because the requested deliverable must be saved in the current workspace and multi-agent delegation is disabled.

**Goal:** Create a Korean 10-minute, eight-slide PowerPoint presentation explaining the project's SLAM-based real-time path generation direction and its I2ICF-based heterogeneous-mobile-object expansion.

**Architecture:** Generate a 16:9 presentation with native LibreOffice Impress shapes and text so the result remains editable. The first half covers the verified current baseline, SLAM/costmap/planner responsibilities, and automatic replanning. The second half uses I2ICF only as a multi-Mobile-Object information-sharing perspective, covering capability-aware obstacle/path/environment sharing and a staged experiment roadmap; intent translation and policy control are out of scope.

**Tech Stack:** LibreOffice Impress 7.3, Python UNO bridge, PowerPoint `.pptx` and legacy `.ppt` exports, PDF rendering for verification.

## Global Constraints

- Use Korean for prose and preserve original English spelling for code, paths, ROS2 topics, APIs, class names, and function names.
- Keep commonly used robotics terms in English where they improve readability, including Route, Planner, Costmap, Baseline, Candidate, Interface, Schema, and Metrics.
- Describe current implementation separately from proposed research.
- Do not claim that SLAM directly generates paths; SLAM supplies map and pose, while planners generate paths.
- Preserve the current static-route baseline as a comparison method.
- Keep VLM selection behind deterministic collision and kinematic validation.
- Invalid or unavailable VLM output keeps the robot stopped.
- The I2ICF section must not present intent translation or policy control as project scope; it focuses only on using multiple heterogeneous vehicles and robots to share observations.
- Do not run ROS2, Isaac Sim, Flask, Ollama, or a physical robot.

---

### Task 1: Build the editable presentation

**Files:**
- Create: `scripts/generate_slam_i2icf_presentation.py`
- Create: `SDV_Robocar_SLAM_I2ICF_연구방향_8장_최종.pptx`
- Create: `SDV_Robocar_SLAM_I2ICF_연구방향_8장_최종.ppt`

**Interfaces:**
- Consumes: verified project descriptions from `README.md`, `ARCHITECTURE.md`, `docs/safety/robot-safety.md`, and `docs/experiments/protocol.md`
- Produces: editable 16:9 presentation files with identical slide content

- [x] Create eight slides: title, agenda, current limitation, SLAM path-generation architecture, automatic detour example, I2ICF architecture, heterogeneous experiment design, and roadmap/decisions.
- [x] Place the agenda after the title and divide it into a five-minute SLAM part and a five-minute I2ICF part.
- [x] Replace selected Korean translations with commonly used English technical terms without turning the prose into English.
- [x] Include presenter notes as concise bottom-line takeaways on each content slide.
- [x] Export both `.pptx` and legacy `.ppt` formats.

### Task 2: Verify presentation structure and rendering

**Files:**
- Verify: `SDV_Robocar_SLAM_I2ICF_연구방향_8장_최종.pptx`
- Verify: `SDV_Robocar_SLAM_I2ICF_연구방향_8장_최종.ppt`

**Interfaces:**
- Consumes: the two presentation files from Task 1
- Produces: verification evidence from LibreOffice PDF conversion and slide text extraction

- [x] Reopen both files with LibreOffice in headless mode and convert them to PDF.
- [x] Confirm the PDF page count equals eight for both formats.
- [x] Render PDF pages to PNG contact sheets and inspect for clipping, overlap, or unreadable text.
- [x] Extract slide text and confirm that the agenda, SLAM, Planner, VLM safety, I2ICF, heterogeneous vehicles, Metrics, and staged validation are all present.
