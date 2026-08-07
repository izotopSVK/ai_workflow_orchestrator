# Justfile — task runner for the AI Workflow Orchestrator.
# Install `just`: https://just.systems  (e.g. `brew install just`, `cargo install just`,
# `pipx install rust-just`). Then run `just` to list recipes.
#
# Recipes assume a POSIX shell and a local venv at .venv (Linux/macOS). The venv
# binaries are called directly, so you never need to `source .venv/bin/activate`.

venv := ".venv"
py := venv / "bin" / "python"
pip := venv / "bin" / "pip"

# Show available recipes (default when you run bare `just`).
default:
    @just --list

# One-shot first initialization: venv + deps + .env + database + migrations.
# After this, run `just login` (Copilot SSO) then `just run`.
init: venv env db-up migrate
    @echo ""
    @echo "✅ Initialization complete."
    @echo "   Next: 'just login'  (GitHub Copilot SSO — or set LLM_PROVIDER=fake in .env)"
    @echo "   Then: 'just run'    (start the API at http://localhost:8000)"

# Create the virtualenv and install the package with test dependencies.
venv:
    test -d {{ venv }} || python3 -m venv {{ venv }}
    {{ pip }} install -q -U pip
    {{ pip }} install -q -e ".[test]"

# Install optional extras too: Headroom compression + sqlite LLM cache.
install-extras:
    {{ pip }} install -q -e ".[test,compression,cache]"

# Create .env from the template if it doesn't exist yet.
env:
    test -f .env || cp .env.example .env

# Start PostgreSQL (Docker) and wait until it is healthy.
db-up:
    docker compose up -d
    @echo "Waiting for Postgres to become healthy..."
    @until docker compose exec -T postgres pg_isready -U workflow -d ai_workflows >/dev/null 2>&1; do sleep 1; done
    @echo "Postgres is ready."

# Stop the database container.
db-down:
    docker compose down

# Wipe the database volume and recreate an empty Postgres (DESTROYS all data).
# Use this to recover from a partially-applied migration.
db-reset:
    docker compose down -v
    @just db-up

# Apply database migrations.
migrate:
    {{ venv }}/bin/alembic upgrade head

# Authenticate GitHub Copilot via the SSO device flow and append the token to .env.
# Follow the printed URL + code (this is where org SAML SSO is enforced).
login:
    {{ py }} -c "from workflows.llm.copilot import GitHubCopilotTokenProvider as T; open('.env','a').write(f'\nGH_COPILOT_OAUTH_TOKEN={T().login_device_flow()}\n')"

# Run the API with auto-reload (http://localhost:8000).
run:
    {{ venv }}/bin/uvicorn app.main:app --reload

# Run the test suite (Fakes + SQLite; no Copilot/PHP/git/Postgres needed).
test:
    {{ venv }}/bin/pytest -q

# Full reset from scratch: wipe the venv/caches, then initialize again.
fresh: clean init

# Remove the venv, local caches and generated artifacts.
clean:
    rm -rf {{ venv }} .llm_cache.sqlite artifacts .pytest_cache
    -find . -type d -name __pycache__ -prune -exec rm -rf {} +
