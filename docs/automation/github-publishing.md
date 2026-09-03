> Last updated: 2026-09-03 18:56 KST

# GitHub Publishing and Maintenance

## Non-negotiable rules

- Treat the original local source repositories as `read-only`. Do not write,
  commit, clean, reset, move, or delete files there for a GitHub task.
- Perform every GitHub maintenance task in a newly created temporary clone under
  `/tmp`; never reuse a prior task's clone.
- Obtain explicit user approval for every GitHub task and again before any
  remote write. Approval for one task does not carry over to another task.
- Do not start Isaac Sim, ROS2, robot services, or publish any ROS2 topic while
  preparing repository changes.

## Approval gate 1: before any GitHub work

Before cloning, fetching, inspecting a remote, opening a pull request, or
changing a temporary clone, explain the task scope, intended repository, and
whether it can write to a remote. Obtain fresh explicit **GitHub 작업 시작 승인**
from the user. Record the source repository path and its initial branch, HEAD
SHA, `git status --short`, and `git remote -v` output without modifying it.

## Temporary clone workflow

After approval gate 1, create one new clone under `/tmp` for this task. Make
all inspection, edits, tests, staging, and commits only in that clone. Keep the
original local source `read-only`, and do not use source-local writes as a
shortcut for preparing the upload. Set the intended branch in the temporary
clone and record its starting SHA before editing.

## File inclusion and exclusion rules

Include only source, tests, lightweight project assets, and documentation that
are necessary for the approved task. Exclude generated caches, `__pycache__`,
personal IDE state, third-party runtime installations, credentials, local logs,
datasets, models, rosbag files, and experiment artifacts unless the user has
explicitly approved them. Do not upload `weekly-report` files or their generated
outputs. Inspect `git status --short`, `git diff --check`, `git diff --cached`,
and `git ls-files` before committing so accidental files are not staged.

## README synchronization

When the approved change alters repository layout, setup, runtime assets,
interfaces, or user-facing operation, update `README` in the same temporary
clone. Ensure README paths and commands describe only tracked, portable files;
do not expose original local source paths, machine-specific locations, or
secrets. If no README change is needed, record why after comparing it with the
final staged diff.

## Verification before commit

Review the staged diff file by file and confirm it contains only approved
changes. Run the focused tests for the affected area and the project-required
checks; record each exact command and result. Run `git diff --check`, verify
Markdown metadata where applicable, and compare the temporary clone HEAD SHA
with the recorded starting SHA so the commit history and new commit SHA are
unambiguous. Do not commit when a required check fails or a changed file is
outside the approved scope.

## Approval gate 2: immediately before remote write

After local verification and before `git push`, creating or updating a pull
request, or any other remote write, show the branch, final commit SHA, staged or
committed diff summary, test results, and remote target. Obtain a separate
explicit **push 직전 최종 승인**. Do not treat approval gate 1 as authorization to
push.

## Remote verification

Only after approval gate 2, push the approved commit to the approved remote and
branch. Verify the remote branch points to the expected final SHA using a
read-only remote query, and record the remote URL, branch, and SHA. Do not force
push, rewrite history, alter protected-branch settings, or change remote URLs
without separate explicit user approval.

## Original local source verification

After the temporary-clone work, compare the original local source's current
HEAD SHA, `git status --short`, and `git remote -v` with the values recorded at
approval gate 1. Report any difference immediately and do not claim the source
was preserved until the comparison is complete. The original local source must
remain unchanged by the GitHub task.

## Prohibited operations

- No GitHub work without fresh approval gate 1.
- No `git push`, pull-request update, tag publication, release publication, or
  other remote write without approval gate 2.
- No writes, commits, branch changes, or cleanup operations in the original
  local source repository.
- No force push, history rewrite, destructive reset, Git LFS migration, or
  credential upload without explicit, task-specific approval.
- No upload of `weekly-report` files, generated reports, caches, private IDE
  settings, local logs, datasets, models, rosbag files, or secrets.
