# Installation & first setup

## Prerequisites

- **Python 3.11+**
- **Docker** (for the PostgreSQL used by the MVP API; not needed for `pytest`)
- A **GitHub Copilot** subscription (enterprise/org, SSO-authorized) — only for
  live LLM runs. Tests and offline development use Fakes and need no Copilot.
- For live dev-orchestrator runs against a real Yii app: **PHP 8.4**, **Composer**,
  and the target repo's `vendor/bin` tools (Rector, PHPStan, PHP-CS-Fixer,
  PHPUnit). Not required for the scaffold or tests.

## 1. Clone and enter the repo

```bash
git clone https://github.com/izotopSVK/ai_workflow_orchestrator.git
cd ai_workflow_orchestrator
```

## 2. Python environment

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[test]"
```

Optional extras:

```bash
pip install -e ".[compression]"  # Headroom SDK (context compression)
pip install -e ".[cache]"        # langchain-community (sqlite LLM cache)
```

## 3. Environment variables

```bash
cp .env.example .env
```

Key variables (full list in [configuration.md](configuration.md)):

| Var | Default | Purpose |
|-----|---------|---------|
| `DB_URL` | `postgresql+psycopg://workflow:workflow@localhost:5432/ai_workflows` | app tables |
| `CHECKPOINT_DB_URL` | same DB (libpq URL) | LangGraph checkpoints |
| `LLM_PROVIDER` | `github_copilot` | `github_copilot` or `fake` |
| `COPILOT_MODEL` | `chatgpt-5.6-terra` | default model (`-sol`/`-terra`/`-luna`) |
| `GH_COPILOT_OAUTH_TOKEN` | _(unset)_ | SSO-authorized OAuth token |

> Tip: set `LLM_PROVIDER=fake` to run the API end-to-end with no Copilot account.

## 4. Database (MVP API only)

```bash
docker compose up -d          # starts PostgreSQL 16
alembic upgrade head          # creates the schema
```

## 5. Authenticate Copilot (SSO)

The Copilot token is derived from a GitHub OAuth token via the SSO device flow.
Run it once and store the token in `.env` **without echoing it to your shell
history**:

```bash
python -c "from workflows.llm.copilot import GitHubCopilotTokenProvider as T; \
open('.env','a').write(f'\nGH_COPILOT_OAUTH_TOKEN={T().login_device_flow()}\n')"
```

Follow the printed URL + code to authorize (this is where org SAML SSO is
enforced). See [auth_and_security.md](auth_and_security.md) for details and the
enterprise OAuth-app override.

## 6. Verify

```bash
pytest -q          # 60 tests; no Copilot/PHP/git/Postgres required
```

You're ready — continue to [usage.md](usage.md).
