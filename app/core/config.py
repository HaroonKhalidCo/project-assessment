from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Project Evaluation"
    API_V1_STR: str = "/api/v1"
    GOOGLE_API_KEY: Optional[str] = None

class config:
    env_file = ".env"
    env_file_encoding = "utf-8"
    ignore_extra = True

settings = Settings()