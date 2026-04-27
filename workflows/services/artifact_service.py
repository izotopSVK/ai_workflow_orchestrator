from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class ArtifactService:
    """Local-disk JSON artifact store. Out-of-state storage for large payloads."""

    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or os.getenv("ARTIFACT_DIR", "./artifacts"))
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def put_json(self, *, workflow_id: str, name: str, data: dict[str, Any]) -> str:
        wf_dir = self.base_dir / workflow_id
        wf_dir.mkdir(parents=True, exist_ok=True)
        path = wf_dir / f"{name}.json"
        path.write_text(json.dumps(data, indent=2, default=str))
        return path.resolve().as_uri()

    def get_json(self, uri: str) -> dict[str, Any]:
        path = Path(uri.removeprefix("file://"))
        return json.loads(path.read_text())
