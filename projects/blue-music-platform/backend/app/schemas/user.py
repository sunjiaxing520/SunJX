from pydantic import BaseModel, Field, SecretStr, field_validator

from app.models import AgentType, UserRole


USERNAME_PATTERN = r"^[A-Za-z0-9._-]+$"


class CreateUserRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=USERNAME_PATTERN,
    )
    password: SecretStr = Field(min_length=8, max_length=128)
    music_quota_remaining: int = Field(default=0, ge=0, le=100_000)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, username: str) -> str:
        return username.lower()


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserPasswordResetRequest(BaseModel):
    password: SecretStr = Field(min_length=8, max_length=128)


class AgentPermissionsUpdate(BaseModel):
    agents: set[AgentType] = Field(default_factory=set)


class UserMusicQuotaUpdate(BaseModel):
    remaining_tasks: int = Field(ge=0, le=100_000)


class UserWatermarkUpdate(BaseModel):
    watermark_text: str | None = Field(default=None, max_length=50)

    @field_validator("watermark_text")
    @classmethod
    def clean_watermark_text(cls, watermark_text: str | None) -> str | None:
        if watermark_text is None:
            return None
        cleaned = " ".join(watermark_text.split())
        return cleaned or None


class MusicTaskQuotaResponse(BaseModel):
    is_unlimited: bool
    remaining_tasks: int | None
    used_tasks: int


class UserResponse(BaseModel):
    id: int
    username: str
    watermark_text: str
    role: UserRole
    is_active: bool
    agent_permissions: list[AgentType]
    music_quota: MusicTaskQuotaResponse
