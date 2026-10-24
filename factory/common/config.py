"""Load config.yaml, the single home for every threshold the agents apply."""

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Read the YAML config. Missing keys raise KeyError where they are used."""
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with config_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{config_path} must contain a YAML mapping")
    return data
