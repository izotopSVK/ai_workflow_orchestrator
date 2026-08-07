"""Load project instructions from the target repo (AGENTS.md standard & friends).

Supports the common cross-tool conventions an agent is expected to honor, read
from the worktree root in priority order and merged into one block that is
injected into every agent's system prompt:

* ``AGENTS.md``                        - the cross-tool AGENTS.md standard
* ``CLAUDE.md``                        - Claude Code
* ``.github/copilot-instructions.md``  - GitHub Copilot
* ``.cursorrules`` / ``.cursor/rules/*.mdc`` - Cursor
* ``.windsurfrules``                   - Windsurf

Nested ``AGENTS.md`` files (nearest-to-edited-file wins, per the standard) are
picked up via :meth:`RepoInstructionsProvider.load_for_paths`.
"""

from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Protocol

# (label, repo-relative path or glob), highest priority first.
STANDARD_INSTRUCTION_SOURCES: list[tuple[str, str]] = [
    ("AGENTS.md", "AGENTS.md"),
    ("CLAUDE.md", "CLAUDE.md"),
    ("copilot-instructions", ".github/copilot-instructions.md"),
    ("cursorrules", ".cursorrules"),
    ("cursor-rules", ".cursor/rules/*.mdc"),
    ("windsurfrules", ".windsurfrules"),
]


class InstructionsProvider(Protocol):
    def load(self, root: str) -> str: ...


class NoInstructionsProvider:
    """Loads nothing. Default when no target repo instructions are wanted."""

    def load(self, root: str) -> str:
        return ""


class RepoInstructionsProvider:
    """Reads and merges standard instruction files from a repo/worktree root."""

    def __init__(self, *, max_chars: int = 20000):
        self.max_chars = max_chars

    def _read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return ""

    def load(self, root: str) -> str:
        base = Path(root)
        blocks: list[str] = []
        for label, rel in STANDARD_INSTRUCTION_SOURCES:
            for match in sorted(glob.glob(str(base / rel))):
                content = self._read(Path(match))
                if content:
                    blocks.append(f"## From {label} ({os.path.relpath(match, base)})\n{content}")
        return self._cap("\n\n".join(blocks))

    def load_for_paths(self, root: str, paths: list[str]) -> str:
        """Root instructions plus the nearest nested AGENTS.md for each path."""
        base = Path(root)
        blocks = [self.load(root)] if self.load(root) else []
        seen: set[str] = set()
        for rel in paths:
            directory = (base / rel).parent
            while True:
                candidate = directory / "AGENTS.md"
                key = str(candidate)
                if candidate.is_file() and key not in seen and candidate != base / "AGENTS.md":
                    seen.add(key)
                    content = self._read(candidate)
                    if content:
                        blocks.append(
                            f"## From nested AGENTS.md ({os.path.relpath(candidate, base)})\n{content}"
                        )
                if directory == base or base not in directory.parents:
                    break
                directory = directory.parent
        return self._cap("\n\n".join(b for b in blocks if b))

    def _cap(self, text: str) -> str:
        if len(text) <= self.max_chars:
            return text
        return text[: self.max_chars] + "\n…[instructions truncated]"
