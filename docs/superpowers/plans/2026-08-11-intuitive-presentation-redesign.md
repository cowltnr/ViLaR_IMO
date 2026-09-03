> Last updated: 2026-08-15 21:16 KST

# Intuitive SLAM and I2ICF Presentation Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a seven-slide editable PowerPoint with three SLAM slides, one intuitive I2ICF slide, and one realistic one-week Next Step slide.

**Architecture:** Reuse the existing LibreOffice UNO presentation generator and retain the verified SLAM slides. Replace the abstract I2ICF architecture and experiment slides with one scenario flow, replace the long roadmap with a one-week implementation plan, and export under a new filename to preserve open or previous presentation files.

**Tech Stack:** Python UNO, LibreOffice Impress 7.3, PowerPoint `.pptx`, PDF and PNG rendering for verification.

## Global Constraints

- Keep exactly three SLAM content slides.
- Keep exactly one I2ICF content slide.
- Add exactly one Next Step slide with work feasible in one week.
- Keep I2ICF intent interpretation and policy control out of scope.
- Do not claim SLAM directly generates a Path.
- Do not run ROS2, Isaac Sim, Flask, Ollama, or a physical robot.
- Preserve previous presentation artifacts by using a new output filename.

---

### Task 1: Recompose and simplify the slide deck

**Files:**
- Modify: `scripts/generate_slam_i2icf_presentation.py`
- Create: `SDV_Robocar_SLAM_I2ICF_직관적_7장.pptx`

**Interfaces:**
- Consumes: existing slide builders and verified project constraints
- Produces: seven editable slides in title, agenda, three-SLAM, one-I2ICF, one-Next-Step order

- [x] Update the title timing and agenda for the new seven-slide flow.
- [x] Preserve the three SLAM content slides and their safety messages.
- [x] Replace the I2ICF content with a `발견 → 공유 → 각자 판단` scenario.
- [x] Add a Monday-to-Friday Next Step with explicit deliverables and exclusions.
- [x] Export only the requested `.pptx` under the new filename.

### Task 2: Verify the presentation

**Files:**
- Verify: `SDV_Robocar_SLAM_I2ICF_직관적_7장.pptx`

**Interfaces:**
- Consumes: generated PowerPoint
- Produces: page-count, text-presence, and visual-layout evidence

- [x] Reopen the PPTX with LibreOffice and convert it to PDF.
- [x] Confirm seven 16:9 pages.
- [x] Extract text and confirm three SLAM slides, one I2ICF slide, and the one-week scope.
- [x] Render all pages and inspect for clipping, overlap, and unreadable text.
