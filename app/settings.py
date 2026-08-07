from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    db_url: str = "postgresql+psycopg://workflow:workflow@localhost:5432/ai_workflows"
    checkpoint_db_url: str = "postgresql://workflow:workflow@localhost:5432/ai_workflows"

    # Enterprise LLM: GitHub Copilot (SSO-compatible). The Copilot token is
    # derived from a GitHub OAuth token (GH_COPILOT_OAUTH_TOKEN or device flow).
    llm_provider: str = "github_copilot"
    copilot_model: str = "chatgpt-5.6-terra"
    copilot_base_url: str = "https://api.githubcopilot.com"

    # Context compression (Headroom) + response cache for the planner LLM.
    compressor: str = "none"  # none | headroom
    headroom_proxy_url: str | None = None  # proxy mode; overrides copilot_base_url
    llm_cache: str = "none"  # none | memory | sqlite

    artifact_dir: str = "./artifacts"


def get_settings() -> Settings:
    return Settings()
