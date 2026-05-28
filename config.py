from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://grants_user:grants_pass@localhost:5432/grants_db"
    DB_SCHEMA: str = "grants_svc"
    DEBUG: bool = False


settings = Settings()
