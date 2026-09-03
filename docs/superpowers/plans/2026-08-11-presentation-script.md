> Last updated: 2026-09-03 19:08 KST

# SLAM·I2ICF Presentation Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a UTF-8 Korean speaking script for the verified eight-slide, ten-minute SLAM and I2ICF presentation.

**Architecture:** Mirror the slide order exactly and assign a speaking-time budget to every slide. Each section contains spoken prose and a transition line while preserving the presentation's verified/proposed distinction and safety constraints.

**Tech Stack:** Plain UTF-8 text, shell text verification, existing PowerPoint text and presenter notes.

## Global Constraints

- Keep the total nominal duration at ten minutes.
- Allocate about five minutes to SLAM and five minutes to I2ICF.
- Preserve commonly used English robotics terms shown in the slides.
- State that SLAM supplies Map and Pose while Planner generates Paths.
- Keep I2ICF intent interpretation and policy control out of scope.
- State that invalid or unavailable VLM output keeps the robot stopped.
- Do not run ROS2, Isaac Sim, Flask, Ollama, or a physical robot.

---

### Task 1: Write and verify the presentation script

**Files:**
- Create: `SDV_Robocar_SLAM_I2ICF_발표대본.txt` — GitHub 현재 tree에서는 사용자 요청으로 제거됨

**Interfaces:**
- Consumes: `SDV_Robocar_SLAM_I2ICF_연구방향_8장_최종.pptx` slide order and presenter notes
- Produces: an eight-section UTF-8 speaking script with time budgets and transitions

- [x] Write eight numbered sections in exact slide order.
- [x] Add nominal per-slide and cumulative time markers totaling ten minutes.
- [x] Include spoken transitions between the SLAM and I2ICF halves.
- [x] Verify all eight slide headings and required technical/safety statements are present.
- [x] Confirm the file is UTF-8 text and review it for placeholders or unsupported claims.
