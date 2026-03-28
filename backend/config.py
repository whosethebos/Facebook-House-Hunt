# backend/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    fb_email: str = ""
    fb_password: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    database_url: str = "postgresql://localhost:5432/facebook_house_hunt"
    frontend_url: str = "http://localhost:3000"
    session_path: str = "session/fb_session.json"
    session_max_age_days: int = 7


settings = Settings()
