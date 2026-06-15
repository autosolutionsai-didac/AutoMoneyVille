"""Centralized helpers for Claudeville run and metadata storage."""

from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path
from typing import Any


class RunStorage:
    """Resolve and update simulation storage paths from the project root."""

    def __init__(self, project_root: str | Path | None = None):
        if project_root is None:
            project_root = Path(__file__).resolve().parents[2]
        self.project_root = Path(project_root)
        self.frontend_dir = self.project_root / "environment" / "frontend_server"
        self.storage_dir = self.frontend_dir / "storage"
        self.base_dir = self.storage_dir / "base"
        self.runs_dir = self.storage_dir / "runs"
        self.temp_dir = self.frontend_dir / "temp_storage"

    def run_dir(self, sim_code: str) -> Path:
        return self.runs_dir / sim_code

    def meta_path(self, sim_code: str) -> Path:
        return self.run_dir(sim_code) / "reverie" / "meta.json"

    def read_run_meta(self, sim_code: str) -> dict[str, Any]:
        return self._read_json(self.meta_path(sim_code))

    def write_run_meta(self, sim_code: str, meta: dict[str, Any]) -> None:
        self._write_json(self.meta_path(sim_code), meta)

    def resolve_fork_path(self, fork_code: str) -> Path:
        candidates = [fork_code]
        if fork_code.startswith("base_"):
            candidates.append(fork_code.removeprefix("base_"))

        for code in candidates:
            base_candidate = self.base_dir / code
            if base_candidate.exists():
                return base_candidate

        for code in candidates:
            run_candidate = self.runs_dir / code
            if run_candidate.exists():
                return run_candidate

        raise FileNotFoundError(f"Fork simulation '{fork_code}' was not found.")

    def canonical_fork_code(self, fork_code: str) -> str:
        return self.resolve_fork_path(fork_code).name

    def create_run_from_fork(self, fork_code: str, sim_code: str) -> Path:
        fork_path = self.resolve_fork_path(fork_code)
        canonical_fork = fork_path.name
        run_path = self.run_dir(sim_code)
        if not run_path.exists():
            run_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(fork_path, run_path)

        (run_path / "movement").mkdir(parents=True, exist_ok=True)
        meta = self._read_json(run_path / "reverie" / "meta.json")
        meta["fork_sim_code"] = canonical_fork
        self._write_json(run_path / "reverie" / "meta.json", meta)
        self.write_current_run_pointer(sim_code, int(meta.get("step", 0)))
        return run_path

    def write_current_run_pointer(self, sim_code: str, step: int) -> None:
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(self.temp_dir / "curr_sim_code.json", {"sim_code": sim_code})
        self._write_json(self.temp_dir / "curr_step.json", {"step": step})

    def read_current_run_pointer(self) -> dict[str, Any]:
        sim_code = self._read_json(self.temp_dir / "curr_sim_code.json")["sim_code"]
        step = int(self._read_json(self.temp_dir / "curr_step.json")["step"])
        return {"sim_code": sim_code, "step": step}

    def _read_json(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as infile:
            return json.load(infile)

    def _write_json(self, path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(
            f".{path.name}.{threading.get_ident()}.tmp"
        )
        try:
            with temp_path.open("w", encoding="utf-8") as outfile:
                json.dump(value, outfile, indent=2)
                outfile.write("\n")
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)
