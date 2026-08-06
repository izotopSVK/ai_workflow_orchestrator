from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DevOrchestratorConfig:
    """Static configuration for a dev-orchestrator run.

    ``target_repo_path`` points at the legacy Yii 1.1 checkout the orchestrator
    develops against. It is left unset in the scaffold and supplied later.
    """

    # Where the legacy Yii 1.1 app lives (a git repo). Set per deployment.
    target_repo_path: str | None = None

    # Ref every task worktree branches from (e.g. "origin/main").
    base_ref: str = "HEAD"

    # Prefix for per-task branches; the short workflow id is appended.
    branch_prefix: str = "task/"

    # Files copied into each worktree (mutable, per-task local config).
    # Globs are relative to the target repo root.
    copy_globs: list[str] = field(
        default_factory=lambda: [
            "config/main-local.php",
            "config/console-local.php",
            ".env",
        ]
    )

    # dest -> source symlinks created inside each worktree (heavy/shared dirs).
    # Keys are worktree-relative; values are absolute or target-repo-relative.
    symlink_map: dict[str, str] = field(
        default_factory=lambda: {
            "vendor": "vendor",
            "runtime": "runtime",
            "assets": "assets",
            "uploads": "uploads",
        }
    )

    # Rector rule sets applied during the migrate/implement step.
    rector_sets: list[str] = field(
        default_factory=lambda: ["PHP_84", "CODE_QUALITY", "DEAD_CODE"]
    )

    # PHPStan analysis level (0-9, or "max").
    phpstan_level: str = "5"

    # Reflexion loop bound: how many implement→verify cycles before giving up.
    max_iterations: int = 4

    # Whether a human must approve before finalize.
    require_human_review: bool = True

    # How many lessons/episodes to pull from memory into planning.
    retrieval_k: int = 5
