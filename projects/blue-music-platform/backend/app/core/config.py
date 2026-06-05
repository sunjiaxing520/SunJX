import os


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

    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]


settings = Settings()
