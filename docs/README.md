# Documentation

Full documentation for the AI Workflow Orchestrator. New here? Start with the top
of the list and work down.

## Getting started

1. **[Installation & first setup](installation.md)** — prerequisites, environment,
   database, Copilot auth, verify.
2. **[Usage](usage.md)** — run the MVP API and the dev orchestrator, with examples.
3. **[Configuration](configuration.md)** — every env var and config field.

## Understanding it

- **[Architecture](architecture.md)** — both graphs, dependency injection, and
  the project layout.
- **[Dev orchestrator](dev_orchestrator.md)** — the self-learning Yii 1.1 → PHP 8.4
  pipeline in depth (nodes, state, Reflexion loop, memory).

## Features & integrations

- **[Auth & security](auth_and_security.md)** — Copilot SSO auth, secret handling.
- **[Logging security](logging_security.md)** — secret/PII redaction, threat model.
- **[AGENTS.md & skills](agents_and_skills.md)** — repo instructions and skills.
- **[Headroom + RTK](headroom_integration.md)** — context compression & prompt cache.

## At a glance

| Topic | Doc |
|-------|-----|
| Install / setup | [installation.md](installation.md) |
| Run it | [usage.md](usage.md) |
| All settings | [configuration.md](configuration.md) |
| How it works | [architecture.md](architecture.md) |
| Enterprise LLM & SSO | [auth_and_security.md](auth_and_security.md) |
| Token/PII safety | [logging_security.md](logging_security.md) |
| AGENTS.md / skills | [agents_and_skills.md](agents_and_skills.md) |
| Token compression | [headroom_integration.md](headroom_integration.md) |
