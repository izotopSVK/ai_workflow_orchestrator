"""Self-learning dev orchestrator for modernizing legacy Yii 1.1 apps to PHP 8.4.

This sub-package is intentionally decoupled from the MVP workflow graph in
``workflows.graph``. It provides a separate LangGraph pipeline that:

1. bootstraps an isolated git worktree (copy configs + symlink heavy dirs),
2. retrieves lessons from long-term memory (self-learning / RAG),
3. analyzes + plans a change against a Yii 1.1 codebase,
4. implements a patch,
5. verifies it deterministically (php -l, Rector PHP84, PHPStan, PHPUnit, SOLID),
6. reflects on failures (Reflexion loop) and retries,
7. finalizes, distills lessons back into memory, and tears down the worktree.

Every side-effecting dependency (git, PHP toolchain, memory store, LLM) is a
Protocol with a deterministic Fake implementation, so the whole graph runs in
tests without git, PHP, Postgres or an LLM server.
"""
