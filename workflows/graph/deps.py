from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from workflows.llm.factory import WorkflowLLM


@dataclass
class WorkflowDeps:
    """Runtime dependencies injected into graph nodes via closures."""

    llm: WorkflowLLM
    session_factory: Callable[[], Session]
