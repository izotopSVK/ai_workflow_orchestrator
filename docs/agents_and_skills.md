# AGENTS.md, instructions & skills support

The dev orchestrator honors the common cross-tool conventions that a target repo
uses to steer agents. When a run starts, the `load_context` node reads them from
the worktree and injects them into **every** agent's system prompt for the rest
of the run.

## Instructions (AGENTS.md standard & friends)

`RepoInstructionsProvider` discovers and merges, in priority order:

| Source | Convention |
|--------|------------|
| `AGENTS.md` | the cross-tool AGENTS.md standard |
| `CLAUDE.md` | Claude Code |
| `.github/copilot-instructions.md` | GitHub Copilot |
| `.cursorrules`, `.cursor/rules/*.mdc` | Cursor |
| `.windsurfrules` | Windsurf |

Each block is merged with a provenance header (`## From AGENTS.md (…)`).
Nested `AGENTS.md` (nearest-to-edited-file wins, per the standard) is picked up
via `load_for_paths(root, target_files)`.

## Skills

`DirectorySkillLibrary` loads skill packages from standard locations in the repo:

- `.claude/skills/`
- `.agents/skills/`
- `skills/`

Each skill is a markdown file (`<name>.md` or `<skill>/SKILL.md`) with optional
YAML frontmatter:

```markdown
---
name: Yii Migration
description: How to migrate a Yii 1.1 model to PHP 8.4
---
1. Run Rector with the PHP_84 set.
2. Add #[AllowDynamicProperties] or declare properties.
3. Re-run PHPStan at the configured level.
```

Skills relevant to the goal are **selected** (keyword match against
name+description, same as lesson retrieval, top `retrieval_k`) and their bodies
injected into the agents — so the model gets the right procedure without loading
the whole catalog into context.

## How it flows

```
bootstrap → load_context → retrieve → analyze → plan → implement → verify → …
              │
              ├─ RepoInstructionsProvider.load(worktree)      → instructions
              └─ DirectorySkillLibrary.select(worktree, goal) → selected skills
                        │
                        └─ state["agent_instructions"] = instructions + skill bodies
```

Every agent role (`analyze`, `plan`, `implement`, `review_solid`, `reflect`)
takes a `system_extra` argument; the nodes pass `state["agent_instructions"]`, and
`GitHubCopilotLLM` appends it to the base system prompt under a
`# Project instructions & skills` heading. The loaded instructions and selected
skills are also stored in state, so they are checkpointed and visible for audit.

## Configuration / DI

`DevOrchestratorDeps.instructions` and `.skills` are optional Protocols
(`InstructionsProvider`, `SkillLibrary`). `build_real_deps` wires
`RepoInstructionsProvider` + `DirectorySkillLibrary`; when unset (e.g. the fake
deps used in tests) the node falls back to `NoInstructionsProvider` /
`EmptySkillLibrary`, so nothing breaks. Swap in your own implementation (e.g. a
remote skills registry) without touching the graph.

## Scope

Instructions/skills are a dev-orchestrator feature because they describe *a
target repo*. The MVP workflow graph is a generic planner with no target repo, so
it does not load them. Tested in `tests/test_agents_instructions.py` (9 tests).
