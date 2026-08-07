from __future__ import annotations

import glob
import os
import shutil
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class Workspace:
    path: str
    branch: str
    base_ref: str
    copied: list[str] = field(default_factory=list)
    symlinks: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Workspace":
        return cls(
            path=data["path"],
            branch=data["branch"],
            base_ref=data.get("base_ref", "HEAD"),
            copied=list(data.get("copied", [])),
            symlinks=list(data.get("symlinks", [])),
        )


class WorkspaceManager(Protocol):
    """Provisions/tears down an isolated workspace for a single task.

    The concrete implementation uses ``git worktree`` so each task develops on
    its own branch in its own directory without touching the main checkout.
    """

    def create_worktree(self, *, base_ref: str, branch: str) -> Workspace: ...

    def copy_files(self, workspace: Workspace, globs: list[str]) -> list[str]: ...

    def link_files(self, workspace: Workspace, symlink_map: dict[str, str]) -> list[str]: ...

    def commit(self, workspace: Workspace, message: str) -> str: ...

    def remove_worktree(self, workspace: Workspace) -> None: ...


class GitWorktreeManager:
    """Real implementation backed by git + the filesystem.

    Generic over any git repo, so it is usable before a concrete Yii target is
    wired in — point ``repo_path`` at the legacy checkout.
    """

    def __init__(self, *, repo_path: str, worktrees_root: str | None = None):
        self.repo_path = Path(repo_path).resolve()
        self.worktrees_root = Path(
            worktrees_root or (self.repo_path.parent / ".dev-orchestrator-worktrees")
        ).resolve()

    def _git(self, *args: str, cwd: Path | None = None) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd or self.repo_path),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def create_worktree(self, *, base_ref: str, branch: str) -> Workspace:
        self.worktrees_root.mkdir(parents=True, exist_ok=True)
        dest = self.worktrees_root / branch.replace("/", "_")
        self._git("worktree", "add", "-b", branch, str(dest), base_ref)
        return Workspace(path=str(dest), branch=branch, base_ref=base_ref)

    def copy_files(self, workspace: Workspace, globs: list[str]) -> list[str]:
        copied: list[str] = []
        for pattern in globs:
            for src in glob.glob(str(self.repo_path / pattern)):
                rel = os.path.relpath(src, self.repo_path)
                dst = Path(workspace.path) / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied.append(rel)
        workspace.copied = copied
        return copied

    def link_files(self, workspace: Workspace, symlink_map: dict[str, str]) -> list[str]:
        links: list[str] = []
        for dest_rel, source in symlink_map.items():
            source_path = Path(source)
            if not source_path.is_absolute():
                source_path = self.repo_path / source
            if not source_path.exists():
                continue
            link_path = Path(workspace.path) / dest_rel
            if link_path.exists() or link_path.is_symlink():
                if link_path.is_dir() and not link_path.is_symlink():
                    shutil.rmtree(link_path)
                else:
                    link_path.unlink()
            link_path.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(source_path, link_path, target_is_directory=source_path.is_dir())
            links.append(dest_rel)
        workspace.symlinks = links
        return links

    def commit(self, workspace: Workspace, message: str) -> str:
        wt = Path(workspace.path)
        self._git("add", "-A", cwd=wt)
        self._git("commit", "-m", message, "--allow-empty", cwd=wt)
        return self._git("rev-parse", "HEAD", cwd=wt)

    def remove_worktree(self, workspace: Workspace) -> None:
        self._git("worktree", "remove", "--force", workspace.path)


class FakeWorkspaceManager:
    """Deterministic in-memory/tmp-dir workspace for tests.

    Creates real temp directories (so copy/symlink logic is exercised) but never
    shells out to git.
    """

    def __init__(self, *, root: str | None = None):
        import tempfile

        self.root = Path(root or tempfile.mkdtemp(prefix="fake-worktrees-"))
        self.commits: list[tuple[str, str]] = []
        self.removed: list[str] = []

    def create_worktree(self, *, base_ref: str, branch: str) -> Workspace:
        dest = self.root / f"{branch.replace('/', '_')}-{uuid.uuid4().hex[:6]}"
        dest.mkdir(parents=True, exist_ok=True)
        return Workspace(path=str(dest), branch=branch, base_ref=base_ref)

    def copy_files(self, workspace: Workspace, globs: list[str]) -> list[str]:
        # No source tree in the fake; just record intent deterministically.
        workspace.copied = list(globs)
        return workspace.copied

    def link_files(self, workspace: Workspace, symlink_map: dict[str, str]) -> list[str]:
        workspace.symlinks = list(symlink_map.keys())
        return workspace.symlinks

    def commit(self, workspace: Workspace, message: str) -> str:
        sha = uuid.uuid4().hex[:12]
        self.commits.append((workspace.branch, message))
        return sha

    def remove_worktree(self, workspace: Workspace) -> None:
        self.removed.append(workspace.path)
        if Path(workspace.path).exists():
            shutil.rmtree(workspace.path, ignore_errors=True)
