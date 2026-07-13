from pydantic import BaseModel, Field, SecretStr


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: SecretStr = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
