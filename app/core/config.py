from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "Dishwasher Workflow System"
    API_V1_STR: str = "/api/v1"

    # Database
    SQLALCHEMY_DATABASE_URL: str = "sqlite:///./sql_app.db"
    POSTGRES_SERVER: str = ""
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    @property
    def DATABASE_URL(self) -> str:
        if self.POSTGRES_SERVER:
            return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"
        return self.SQLALCHEMY_DATABASE_URL

    # Uploads
    UPLOAD_DIR: str = "uploads"

    # Security
    SECRET_KEY: str = "super-secret-key-change-it-in-prod"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8 # 8 days

    class Config:
        case_sensitive = True

settings = Settings()
