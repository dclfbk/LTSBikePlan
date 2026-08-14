from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    repo_root: Path
    code_dir: Path
    data_dir: Path
    images_dir: Path

    @classmethod
    def from_project_layout(cls) -> "AppConfig":
        code_dir = Path(__file__).resolve().parents[1]
        repo_root = code_dir.parent
        data_dir = Path(os.environ.get("LTSBP_DATA_DIR", str(repo_root / "data")))
        images_dir = Path(os.environ.get("LTSBP_IMAGES_DIR", str(repo_root / "images")))
        return cls(
            repo_root=repo_root,
            code_dir=code_dir,
            data_dir=data_dir,
            images_dir=images_dir,
        )
