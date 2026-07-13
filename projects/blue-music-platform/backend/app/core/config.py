import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env", override=False)


class Settings:
    PROJECT_NAME = "蓝乐 AI 音乐创作平台"
    PROJECT_DESCRIPTION = "AI 音乐榜单采集、风格分析、作词与 Suno 创作工作台"
    SERVICE_NAME = "blue-music-platform"
    VERSION = "0.1.0"
    API_V1_PREFIX = "/api/v1"

    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://blue_music:blue_music_pass@localhost:5432/blue_music_db",
    )
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key_change_in_production")
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120")
    )

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_FORMAT = os.getenv(
        "LOG_FORMAT", "json" if ENVIRONMENT == "production" else "text"
    ).lower()
    LOG_TO_FILE = os.getenv(
        "LOG_TO_FILE", "false" if ENVIRONMENT == "production" else "true"
    ).lower() in {"1", "true", "yes", "on"}
    LOG_DIR = os.getenv("LOG_DIR")
    LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "30"))

    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]


settings = Settings()
