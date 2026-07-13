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


class UserResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    is_active: bool
    agent_permissions: list[AgentType]
