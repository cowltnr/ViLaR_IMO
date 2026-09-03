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
