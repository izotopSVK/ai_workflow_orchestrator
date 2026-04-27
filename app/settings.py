from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    db_url: str = "postgresql+psycopg://workflow:workflow@localhost:5432/ai_workflows"
    checkpoint_db_url: str = "postgresql://workflow:workflow@localhost:5432/ai_workflows"

    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.6"

    artifact_dir: str = "./artifacts"


def get_settings() -> Settings:
    return Settings()
