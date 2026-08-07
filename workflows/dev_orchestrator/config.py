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

    # External MCP servers whose tools the agents may use. Maps server name ->
    # langchain-mcp-adapters connection config, e.g.
    # {"git": {"command": "uvx", "args": ["mcp-server-git"], "transport": "stdio"}}.
    # Empty (default) means no MCP client. See docs/mcp.md.
    mcp_servers: dict[str, dict] = field(default_factory=dict)

    # --- Enterprise LLM: GitHub Copilot (SSO-compatible) ----------------
    # All orchestration LLM calls route through Copilot's OpenAI-compatible API.
    llm_provider: str = "github_copilot"
    # Default agent model. Variants: chatgpt-5.6-sol / -terra / -luna.
    copilot_model: str = "chatgpt-5.6-terra"
    copilot_base_url: str = "https://api.githubcopilot.com"
    copilot_editor_version: str = "vscode/1.95.0"
    copilot_integration_id: str = "vscode-chat"
    # OAuth app client id used for the SSO device flow. Override with the
    # enterprise's own OAuth app for tighter org control. The OAuth token itself
    # is read from GH_COPILOT_OAUTH_TOKEN (or acquired via device flow).
    copilot_oauth_client_id: str = "Iv1.b507a08c87ecfe98"

    # --- Context compression / cache (Headroom + RTK) -------------------
    # "none" (default) or "headroom". Compresses tool output / RAG / history
    # before it reaches Copilot to cut tokens. See docs/headroom_integration.md.
    compressor: str = "none"
    # If set, Copilot calls go through this Headroom proxy URL (zero-code mode:
    # compression + CacheAligner happen in the proxy). Overrides copilot_base_url.
    headroom_proxy_url: str | None = None
    # LLM response cache to dedupe identical Copilot calls: "none" | "memory" | "sqlite".
    llm_cache: str = "none"

    # Per-agent model overrides. Each orchestrator agent (analyze, plan,
    # implement, review_solid, reflect) can run on its own Copilot model; any
    # role not listed here falls back to ``copilot_model``. E.g.
    # {"implement": "chatgpt-5.6-sol", "review_solid": "chatgpt-5.6-luna"}.
    agent_models: dict[str, str] = field(default_factory=dict)


def parse_agent_models(raw: str | None) -> dict[str, str]:
    """Parse ``"implement=chatgpt-5.6-sol,reflect=chatgpt-5.6-luna"`` into a dict.

    Convenience for reading per-agent models from a single env var
    (``COPILOT_AGENT_MODELS``). Blank/None yields an empty mapping.
    """
    if not raw:
        return {}
    models: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        role, _, model = pair.partition("=")
        role, model = role.strip(), model.strip()
        if role and model:
            models[role] = model
    return models
