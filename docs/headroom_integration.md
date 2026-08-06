# Headroom + RTK integration (context compression & cache)

Yes — the orchestrator can connect to
[Headroom](https://github.com/headroomlabs-ai/headroom) (and, through it,
[RTK](https://github.com/rtk-ai/rtk)) to cut the tokens sent to GitHub Copilot
and keep the provider's prompt cache aligned.

## What each tool does

- **Headroom** (`headroom-ai`, Rust core + Python/TS SDK) — a context-compression
  layer that shrinks tool outputs, RAG chunks, files and conversation history
  before they reach the LLM (60–95% on JSON, 15–20% for coding agents). It ships
  a library (`compress(messages, model=...)`), an HTTP proxy, an MCP server, and
  a **CacheAligner** that keeps volatile content from busting provider KV-cache
  prefixes.
- **RTK** ("Rust Token Killer", `rtk-ai/rtk`) — compresses shell/command output
  before an agent reads it. It is integrated into Headroom, so Headroom's
  content-aware routing covers our verbose PHP tool output too.

## Where it plugs into this orchestrator

The heavy context here is (1) `verify` output — PHPStan/PHPUnit/Rector logs that
feed the `reflect` and `implement` agents, and (2) retrieved RAG lessons in
`analyze`/`plan`/`implement` prompts. Both flow through the Copilot LLM, so
compressing the messages there is the highest-value hook.

## Two ways to connect

### 1. Proxy mode (zero code)

Run Headroom as a proxy in front of Copilot and point the orchestrator at it:

```bash
headroom proxy   # listens on e.g. http://localhost:8080, forwards to Copilot
```

```python
config = DevOrchestratorConfig(headroom_proxy_url="http://localhost:8080")
```

`headroom_proxy_url` overrides `copilot_base_url`, so every Copilot call is
compressed and cache-aligned in the proxy. No Python dependency needed.

### 2. SDK mode (in-process)

```bash
pip install -e ".[compression]"     # installs headroom-ai
```

```python
config = DevOrchestratorConfig(compressor="headroom")
```

The factory builds a `HeadroomCompressor` and injects it into the Copilot LLM;
`GitHubCopilotLLM.prepare_messages` compresses the `(system, human)` messages
before `invoke`. The adapter imports `headroom` lazily and **falls back to the
uncompressed input on any error** — compression can never break a run.

## Response cache (complementary)

Separate from Headroom's prompt-cache alignment, an exact-match response cache
dedupes identical Copilot calls (retries, repeated plans):

```python
config = DevOrchestratorConfig(llm_cache="memory")   # or "sqlite"
```

`sqlite` mode needs `pip install -e ".[cache]"` (langchain-community) and persists
across restarts.

## Design / SOLID

`workflows/llm/compression.py` defines a `ContextCompressor` Protocol with:

| Impl | Use |
|------|-----|
| `NoOpCompressor` | default; identity, no dependency |
| `HeadroomCompressor` | `headroom-ai` SDK adapter (lazy import, fail-open) |

All Headroom API coupling is isolated in `HeadroomCompressor._compress`, so if a
Headroom release changes the `compress(...)` signature, that one method is the
only thing to update. Written against the documented
`headroom.compress(messages, model=...)` entry point — verify against the
installed `headroom-ai` version before relying on SDK mode in production; proxy
mode has no such coupling.

## Status

Scaffolded and tested with a fake compressor (`tests/test_compression.py`, 9
tests): NoOp identity, Headroom fail-open when the SDK is absent, compressor
applied before invoke, proxy-mode base-url override, and cache toggling. The live
`headroom-ai`/`rtk` binaries are not exercised in CI.
