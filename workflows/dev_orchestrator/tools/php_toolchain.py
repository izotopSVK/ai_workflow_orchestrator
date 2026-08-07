from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol

from workflows.dev_orchestrator.schemas import ToolResult
from workflows.observability.redaction import redact, redact_snippet


class PhpToolchain(Protocol):
    """Deterministic quality gates for PHP 8.4 + SOLID.

    These are the checks the LLM is NOT trusted to do by eye. Each returns a
    uniform :class:`ToolResult`; the verify node aggregates them.
    """

    def lint(self, workspace_path: str, paths: list[str]) -> ToolResult: ...

    def rector(self, workspace_path: str, paths: list[str], sets: list[str]) -> ToolResult: ...

    def phpstan(self, workspace_path: str, paths: list[str], level: str) -> ToolResult: ...

    def cs_fixer(self, workspace_path: str, paths: list[str]) -> ToolResult: ...

    def phpunit(self, workspace_path: str, paths: list[str] | None = None) -> ToolResult: ...


class SubprocessPhpToolchain:
    """Real toolchain that shells out to composer-installed binaries.

    Assumes the target repo has ``vendor/bin`` populated (symlinked into the
    worktree by the bootstrap step). Not exercised in the scaffold tests.
    """

    def __init__(self, *, php_bin: str = "php", vendor_bin: str = "vendor/bin"):
        self.php_bin = php_bin
        self.vendor_bin = vendor_bin

    def _run(self, tool: str, args: list[str], cwd: str) -> ToolResult:
        try:
            proc = subprocess.run(
                args, cwd=cwd, capture_output=True, text=True, timeout=600
            )
        except (subprocess.SubprocessError, OSError) as exc:  # pragma: no cover
            return ToolResult(tool=tool, ok=False, output=redact(str(exc)))
        # PHP tool output can echo repo config (DB creds, .env values) and paths;
        # redact + cap it before it enters the persisted verify_report.
        output = (proc.stdout or "") + (proc.stderr or "")
        return ToolResult(
            tool=tool, ok=proc.returncode == 0, output=redact_snippet(output, limit=8000)
        )

    def _bin(self, workspace_path: str, name: str) -> str:
        return str(Path(workspace_path) / self.vendor_bin / name)

    def lint(self, workspace_path: str, paths: list[str]) -> ToolResult:
        findings: list[str] = []
        for p in paths:
            res = self._run("php -l", [self.php_bin, "-l", p], workspace_path)
            if not res.ok:
                findings.append(res.output.strip())
        return ToolResult(tool="php -l", ok=not findings, findings=findings)

    def rector(self, workspace_path: str, paths: list[str], sets: list[str]) -> ToolResult:
        args = [self._bin(workspace_path, "rector"), "process", *paths]
        return self._run("rector", args, workspace_path)

    def phpstan(self, workspace_path: str, paths: list[str], level: str) -> ToolResult:
        args = [self._bin(workspace_path, "phpstan"), "analyse", "--level", level, *paths]
        return self._run("phpstan", args, workspace_path)

    def cs_fixer(self, workspace_path: str, paths: list[str]) -> ToolResult:
        args = [self._bin(workspace_path, "php-cs-fixer"), "fix", *paths]
        return self._run("php-cs-fixer", args, workspace_path)

    def phpunit(self, workspace_path: str, paths: list[str] | None = None) -> ToolResult:
        args = [self._bin(workspace_path, "phpunit"), *(paths or [])]
        return self._run("phpunit", args, workspace_path)


class FakePhpToolchain:
    """Scriptable toolchain for tests.

    Pass ``results`` to override outcomes per tool name. A callable per tool can
    return a different result on each successive call, which is how the tests
    simulate a failure that is fixed on retry.
    """

    def __init__(self, results: dict | None = None):
        self._results = results or {}
        self.calls: list[str] = []

    def _resolve(self, tool: str) -> ToolResult:
        self.calls.append(tool)
        spec = self._results.get(tool)
        if spec is None:
            return ToolResult(tool=tool, ok=True)
        if callable(spec):
            return spec(self.calls.count(tool))
        if isinstance(spec, ToolResult):
            return spec
        # spec is a list of results indexed by call count.
        idx = min(self.calls.count(tool) - 1, len(spec) - 1)
        return spec[idx]

    def lint(self, workspace_path: str, paths: list[str]) -> ToolResult:
        return self._resolve("php -l")

    def rector(self, workspace_path: str, paths: list[str], sets: list[str]) -> ToolResult:
        return self._resolve("rector")

    def phpstan(self, workspace_path: str, paths: list[str], level: str) -> ToolResult:
        return self._resolve("phpstan")

    def cs_fixer(self, workspace_path: str, paths: list[str]) -> ToolResult:
        return self._resolve("php-cs-fixer")

    def phpunit(self, workspace_path: str, paths: list[str] | None = None) -> ToolResult:
        return self._resolve("phpunit")
