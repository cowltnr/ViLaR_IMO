> Last updated: 2026-09-03 18:42 KST

# ViLaR IMO GitHub Repository Maintenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GitHub 전용 clone의 구조와 README를 정리하고, 이식 가능한 Warehouse runtime 경로와 원본 로컬 무변경 GitHub 작업 지침을 제공한다.

**Architecture:** 모든 변경은 `/tmp`의 `ViLaR_IMO` clone에만 적용한다. 경로 계산은 Isaac Sim에 의존하지 않는 작은 모듈로 분리하고 기존 runtime script가 이를 소비하며, 문서·asset 정리는 실행 가능한 기본 파일을 보존하는 범위에서 수행한다.

**Tech Stack:** Python 3.10, `unittest`, ROS2 Humble, Isaac Sim 4.5.0, Git, Markdown

**Spec:** `docs/superpowers/specs/2026-09-03-github-repository-maintenance-design.md`

## Global Constraints

- GitHub 관련 작업은 시작 전에 사용자 승인을 받고, 원격 write 직전에 별도 최종 승인을 다시 받는다.
- 원본 `/home/cowltnr/PycharmProjects/SDV_Robocar`와 `/home/cowltnr/LimoIsaacSIM/USD/cart_simulation_env`는 read-only다.
- 구현과 commit은 `/tmp` GitHub clone에서만 수행하며 실제 push는 이 계획의 실행 범위에 포함하지 않는다.
- weekly-report 파일, 제3자 Isaac Sim 설치본, cache, `__pycache__`, 개인 IDE 상태는 업로드하지 않는다.
- 기존 ROS2 topic, HTTP endpoint, JSON schema, controller, Worker 왕복, NavMesh와 Cart sync 동작을 변경하지 않는다.
- force push, history rewrite, Git LFS migration과 라이선스 선택을 수행하지 않는다.

---

### Task 1: Portable Warehouse Runtime Paths

**Files:**
- Create: `scripts/warehouse_runtime_paths.py`
- Create: `tests/unit/test_warehouse_runtime_paths.py`
- Modify: `scripts/setup_warehouse_runtime.py:16-25`
- Modify: `scripts/configure_warehouse_worker_behavior.py:9-15`

**Interfaces:**
- Produces: `WarehouseRuntimePaths(stage: Path, command_file: Path)`
- Produces: `resolve_warehouse_runtime_paths(environment: Mapping[str, str] | None = None, repository_root: Path | None = None) -> WarehouseRuntimePaths`
- Consumes environment variables: `VILAR_WAREHOUSE_STAGE`, `VILAR_WORKER_COMMAND_FILE`

- [ ] **Step 1: Write the failing path-resolution tests**

```python
import unittest
from pathlib import Path

from scripts.warehouse_runtime_paths import resolve_warehouse_runtime_paths


class WarehouseRuntimePathsTest(unittest.TestCase):
    def test_repository_assets_are_the_defaults(self):
        root = Path("/tmp/vilar-clone")
        paths = resolve_warehouse_runtime_paths({}, root)
        self.assertEqual(
            paths.stage,
            root / "assets/isaac_sim/cart_simulation_env/warehouse_cart_worker.usd",
        )
        self.assertEqual(
            paths.command_file,
            root / "assets/isaac_sim/cart_simulation_env/worker_commands.txt",
        )

    def test_environment_overrides_both_paths(self):
        paths = resolve_warehouse_runtime_paths(
            {
                "VILAR_WAREHOUSE_STAGE": "/opt/scenes/warehouse.usd",
                "VILAR_WORKER_COMMAND_FILE": "/opt/scenes/commands.txt",
            },
            Path("/tmp/vilar-clone"),
        )
        self.assertEqual(paths.stage, Path("/opt/scenes/warehouse.usd"))
        self.assertEqual(paths.command_file, Path("/opt/scenes/commands.txt"))

    def test_relative_environment_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "absolute"):
            resolve_warehouse_runtime_paths(
                {"VILAR_WAREHOUSE_STAGE": "relative/warehouse.usd"},
                Path("/tmp/vilar-clone"),
            )
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m unittest tests.unit.test_warehouse_runtime_paths -v`

Expected: import failure because `scripts.warehouse_runtime_paths` does not exist.

- [ ] **Step 3: Implement the pure resolver**

```python
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class WarehouseRuntimePaths:
    stage: Path
    command_file: Path


def _absolute_path(value: str, label: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path")
    return path.resolve()


def resolve_warehouse_runtime_paths(
    environment: Mapping[str, str] | None = None,
    repository_root: Path | None = None,
) -> WarehouseRuntimePaths:
    values = os.environ if environment is None else environment
    root = (
        Path(__file__).resolve().parents[1]
        if repository_root is None
        else Path(repository_root).resolve()
    )
    asset_dir = root / "assets/isaac_sim/cart_simulation_env"
    stage_value = values.get("VILAR_WAREHOUSE_STAGE")
    command_value = values.get("VILAR_WORKER_COMMAND_FILE")
    return WarehouseRuntimePaths(
        stage=(
            _absolute_path(stage_value, "VILAR_WAREHOUSE_STAGE")
            if stage_value
            else asset_dir / "warehouse_cart_worker.usd"
        ),
        command_file=(
            _absolute_path(command_value, "VILAR_WORKER_COMMAND_FILE")
            if command_value
            else asset_dir / "worker_commands.txt"
        ),
    )
```

- [ ] **Step 4: Connect existing runtime scripts to the resolver**

In `scripts/setup_warehouse_runtime.py`:

```python
from scripts.warehouse_runtime_paths import resolve_warehouse_runtime_paths

_RUNTIME_PATHS = resolve_warehouse_runtime_paths()
EXPECTED_STAGE_PATH = _RUNTIME_PATHS.stage
COMMAND_FILE = _RUNTIME_PATHS.command_file
```

In `scripts/configure_warehouse_worker_behavior.py`:

```python
from scripts.warehouse_runtime_paths import resolve_warehouse_runtime_paths

DEFAULT_COMMAND_FILE = resolve_warehouse_runtime_paths().command_file
```

- [ ] **Step 5: Run focused and regression tests**

Run: `python3 -m unittest tests.unit.test_warehouse_runtime_paths tests.unit.test_setup_warehouse_runtime tests.unit.test_configure_warehouse_worker_behavior -v`

Expected: all tests pass; no Isaac Sim process starts.

- [ ] **Step 6: Commit Task 1**

```bash
git add scripts/warehouse_runtime_paths.py scripts/setup_warehouse_runtime.py scripts/configure_warehouse_worker_behavior.py tests/unit/test_warehouse_runtime_paths.py
git commit -m "refactor: make warehouse runtime paths portable"
```

---

### Task 2: Safe Repository File Organization

**Files:**
- Delete from GitHub clone: `.idea/`
- Delete from GitHub clone: `assets/isaac_sim/cart_simulation_env/.thumbs/`
- Move: `assets/isaac_sim/cart_simulation_env/warehouse_cart_worker.pre_behavior_20260903_1441.usd`
- Move: `assets/isaac_sim/cart_simulation_env/warehouse_cart_worker.pre_fix_20260902_1708.usd`
- Move: `assets/isaac_sim/cart_simulation_env/warehouse_cart_worker.pre_navigation_20260903_1317.usd`
- Create directory through moved files: `assets/isaac_sim/cart_simulation_env/backups/`
- Move: `docs/exec-plans/active/2026-09-03-warehouse-navmesh-automation.md`
- Modify: moved NavMesh plan
- Modify: `.gitignore`

**Interfaces:**
- Preserves runtime files beside each other: `warehouse_cart_worker.usd`, `warehouse_cart.usd`, `worker_commands.txt`
- Produces archive directory: `assets/isaac_sim/cart_simulation_env/backups/`

- [ ] **Step 1: Record exact pre-move files**

Run: `git ls-files .idea assets/isaac_sim/cart_simulation_env docs/exec-plans/active`

Expected: nine `.idea` files, two thumbnails, three backup USD files, three runtime files and one active NavMesh plan are listed.

- [ ] **Step 2: Remove generated project metadata in the temporary clone**

```bash
git rm -r .idea
git rm -r assets/isaac_sim/cart_simulation_env/.thumbs
```

- [ ] **Step 3: Archive backup USD files with history-preserving moves**

```bash
mkdir -p assets/isaac_sim/cart_simulation_env/backups
git mv assets/isaac_sim/cart_simulation_env/warehouse_cart_worker.pre_behavior_20260903_1441.usd assets/isaac_sim/cart_simulation_env/backups/
git mv assets/isaac_sim/cart_simulation_env/warehouse_cart_worker.pre_fix_20260902_1708.usd assets/isaac_sim/cart_simulation_env/backups/
git mv assets/isaac_sim/cart_simulation_env/warehouse_cart_worker.pre_navigation_20260903_1317.usd assets/isaac_sim/cart_simulation_env/backups/
```

- [ ] **Step 4: Complete and move the NavMesh execution plan**

Update its KST timestamp, mark Apply/Bake live review complete, and record that the user verified Worker return, Cart/Pallet synchronization, obstacle non-penetration, NavMesh containment and Stop cleanup. Then run:

```bash
git mv docs/exec-plans/active/2026-09-03-warehouse-navmesh-automation.md docs/exec-plans/completed/2026-09-03-warehouse-navmesh-automation.md
```

- [ ] **Step 5: Extend ignore rules**

Add these literal rules to `.gitignore`:

```gitignore
.idea/
assets/isaac_sim/**/.thumbs/
```

- [ ] **Step 6: Verify the new tree**

Run: `test ! -e .idea && test ! -e assets/isaac_sim/cart_simulation_env/.thumbs && test -f assets/isaac_sim/cart_simulation_env/backups/warehouse_cart_worker.pre_fix_20260902_1708.usd && test -f docs/exec-plans/completed/2026-09-03-warehouse-navmesh-automation.md`

Expected: exit code 0.

- [ ] **Step 7: Commit Task 2**

```bash
git add .gitignore assets/isaac_sim/cart_simulation_env docs/exec-plans
git commit -m "chore: organize warehouse assets and project metadata"
```

---

### Task 3: GitHub Maintenance Instructions

**Files:**
- Create: `docs/automation/github-publishing.md`
- Modify: `docs/automation/index.md`
- Modify: `docs/index.md`
- Modify: `tests/unit/test_harness_contract.py`

**Interfaces:**
- Produces the human/agent procedure for approval gates, temporary clones, exclusion checks, README synchronization, verification and push.
- Adds `automation/github-publishing.md` to the documentation map.

- [ ] **Step 1: Write a failing documentation contract test**

Add to `HarnessContractTest`:

```python
def test_github_publishing_requires_approval_and_preserves_local_source(self):
    guide_path = ROOT / "docs/automation/github-publishing.md"
    self.assertTrue(guide_path.is_file())
    guide = guide_path.read_text(encoding="utf-8")
    for text in [
        "GitHub 작업 시작 승인",
        "push 직전 최종 승인",
        "/tmp",
        "read-only",
        "weekly-report",
        "README",
    ]:
        self.assertIn(text, guide)
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python3 -m unittest tests.unit.test_harness_contract.HarnessContractTest.test_github_publishing_requires_approval_and_preserves_local_source -v`

Expected: FAIL because `docs/automation/github-publishing.md` does not exist.

- [ ] **Step 3: Write the maintenance guide**

Create `docs/automation/github-publishing.md` with these exact sections:

```markdown
# GitHub Publishing and Maintenance

## Non-negotiable rules
## Approval gate 1: before any GitHub work
## Temporary clone workflow
## File inclusion and exclusion rules
## README synchronization
## Verification before commit
## Approval gate 2: immediately before remote write
## Remote verification
## Original local source verification
## Prohibited operations
```

The guide must require a fresh approval per GitHub task, a second approval before remote write, a new `/tmp` clone per task, no source-local writes, weekly-report exclusion, staged diff review, tests, SHA comparison and original status/remote comparison.

- [ ] **Step 4: Link the guide from both documentation indexes**

Add `github-publishing.md` to `docs/automation/index.md` and add a direct link under the automation entry in `docs/index.md`. Update both KST timestamps.

- [ ] **Step 5: Run the focused contract test**

Run: `python3 -m unittest tests.unit.test_harness_contract -v`

Expected: all harness tests pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add docs/automation/github-publishing.md docs/automation/index.md docs/index.md tests/unit/test_harness_contract.py
git commit -m "docs: define approval-gated GitHub maintenance"
```

---

### Task 4: ViLaR IMO README and Historical Document Accuracy

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-08-11-presentation-script.md`
- Modify: `docs/superpowers/specs/2026-08-11-presentation-script-design.md`

**Interfaces:**
- README links to current code, Warehouse assets, experiment context and GitHub maintenance guide.
- Historical presentation documents no longer imply that the deleted root script is a current repository artifact.

- [ ] **Step 1: Create a README verification checklist before editing**

Verify these paths with `test -e`: `scripts/setup_warehouse_runtime.py`, `assets/isaac_sim/cart_simulation_env/warehouse_cart_worker.usd`, `docs/experiments/warehouse-cart-worker-context.md`, `docs/research-direction.md`, and `docs/automation/github-publishing.md`.

- [ ] **Step 2: Rewrite README for the current repository**

Use a Korean-first README with preserved English identifiers and these sections:

```markdown
# ViLaR IMO
## 연구 목표
## 현재 구현 범위
## 전체 구조
## Repository 구조
## Warehouse Worker–Cart 시나리오
## 빠른 시작
## 환경변수
## 안전 원칙
## 검증된 상태
## 알려진 제한
## 문서 안내
```

State explicitly that predefined waypoint/VLM route selection is the current baseline, SLAM candidate generation and multi-vehicle sharing are research directions, the Warehouse Worker–Cart scenario is live-verified, and USD files may retain Isaac Sim asset or behavior-script dependencies.

Under `Repository 구조`, include a concise table that explains the role and
normal use of every tracked top-level directory and these major root files:
`README.md`, `ARCHITECTURE.md`, `AGENTS.md`, `World.usd`, `edge_control.py`,
`imo_server_lidar.py`, `vlm_server.py`, `k8s_server.py`, `intent_server.py`,
`imo_control.py`, and `received_policy.yaml`. Group files only when their role
and usage are genuinely the same; do not list a path without a description.

- [ ] **Step 3: Correct deleted presentation-script references**

In both historical documents, retain the original filename as historical context but append the literal status: `GitHub 현재 tree에서는 사용자 요청으로 제거됨`. Update each Markdown timestamp.

- [ ] **Step 4: Verify README paths and stale claims**

Run:

```bash
rg -n 'ViLaR IMO|Warehouse Worker–Cart|Repository 구조|역할|VILAR_WAREHOUSE_STAGE|VILAR_WORKER_COMMAND_FILE|알려진 제한' README.md
rg -n 'GitHub 현재 tree에서는 사용자 요청으로 제거됨' docs/superpowers/plans/2026-08-11-presentation-script.md docs/superpowers/specs/2026-08-11-presentation-script-design.md
```

Expected: every required heading, environment variable and historical status is present.

- [ ] **Step 5: Commit Task 4**

```bash
git add README.md docs/superpowers/plans/2026-08-11-presentation-script.md docs/superpowers/specs/2026-08-11-presentation-script-design.md
git commit -m "docs: align README with ViLaR IMO research"
```

---

### Task 5: Final Offline and Publication Readiness Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-09-03-github-repository-maintenance.md`

**Interfaces:**
- Produces a reviewed local commit series ready for a separately approved `ViLaR_IMO/main` push.

- [ ] **Step 1: Run standard checks**

Run: `bash scripts/check.sh`

Expected: exit code 0 and all discovered tests pass.

Run: `bash scripts/test_offline.sh`

Expected: exit code 0 and all discovered tests pass.

- [ ] **Step 2: Verify excluded and oversized files**

Run:

```bash
git ls-files | rg -i '(^|/)(Weekly-Report|WEEKLY_REPORT_AUTOMATION|weekly-report-cron|generate_weekly_report|run_weekly_report|weekly_report_schema|test_generate_weekly_report|test_weekly_report_wrapper|\.idea/|\.thumbs/)' || true
find . -path './.git' -prune -o -type f -size +100M -print
```

Expected: both commands print no tracked matches or oversized files.

- [ ] **Step 3: Scan for credentials and review remaining absolute paths**

Run a secret-pattern scan excluding binary assets and confirm hits are vocabulary rather than credentials. Run `rg -n '/home/cowltnr' scripts README.md` and require no output; historical experiment documents may retain recorded local paths.

- [ ] **Step 4: Review the complete local-only commit range**

Run: `git log --oneline origin/main..HEAD`

Run: `git diff --stat origin/main..HEAD`

Run: `git diff --check origin/main..HEAD`

Expected: only approved repository maintenance changes and no whitespace errors.

- [ ] **Step 5: Mark this plan complete locally**

Update every checkbox, record test counts and remaining license/LFS/USD dependency limitations, update the KST timestamp, then commit:

```bash
git add docs/superpowers/plans/2026-09-03-github-repository-maintenance.md
git commit -m "docs: complete GitHub repository maintenance plan"
```

- [ ] **Step 6: Stop for final user approval**

Present the commit list, changed/deleted/moved files, test results, remaining limitations, target `cowltnr/ViLaR_IMO main`, and confirmation that the original local source was not modified. Do not run `git push` until the user explicitly approves that exact remote write.
