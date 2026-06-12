from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    service: str
    environment: str


class DatabaseHealthResponse(BaseModel):
    status: str
    database: str
    detail: str
