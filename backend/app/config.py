"""Application configuration — reads from environment variables."""

import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # LLM Configuration
    gemini_api_key: str = ""
    openai_api_key: str = ""
    
    # Server Configuration
    frontend_url: str = "*"
    port: int = 8000
    
    # Data Configuration
    n_records: int = 30000
    random_seed: int = 42
    
    # Model Configuration
    n_estimators: int = 100
    max_depth: int = 12
    
    # App metadata
    app_name: str = "FinSight AI"
    app_version: str = "1.0.0"
    
    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
