from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.ranking import TaskStatusValue


WorkflowStepValue = Literal["collection", "analysis", "lyrics"]
STEP_ORDER: tuple[WorkflowStepValue, ...] = (
    "collection",
    "analysis",
    "lyrics",
)


class WorkflowCollectionConfig(BaseModel):
    source_mode: Literal["live", "sample"] = "live"
    limit: int = Field(default=100, ge=1, le=500)


class WorkflowAnalysisConfig(BaseModel):
    window_days: int = Field(default=7, ge=1, le=30)


class WorkflowLyricsConfig(BaseModel):
    direction_index: int = Field(default=0, ge=0, le=9)
    title_hint: str | None = Field(default=None, max_length=200)
    theme: str | None = Field(default=None, max_length=500)
    language: str = Field(default="中文", min_length=1, max_length=30)
    requirements: str | None = Field(default=None, max_length=2000)


class WorkflowConfiguration(BaseModel):
    collection: WorkflowCollectionConfig = Field(
        default_factory=WorkflowCollectionConfig
    )
    analysis: WorkflowAnalysisConfig = Field(default_factory=WorkflowAnalysisConfig)
    lyrics: WorkflowLyricsConfig = Field(default_factory=WorkflowLyricsConfig)


class WorkflowTemplateWrite(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    steps: list[WorkflowStepValue] = Field(min_length=1, max_length=3)
    configuration: WorkflowConfiguration = Field(
        default_factory=WorkflowConfiguration
    )

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_steps(self):
        if len(set(self.steps)) != len(self.steps):
            raise ValueError("流程步骤不能重复")
        expected = [step for step in STEP_ORDER if step in self.steps]
        if self.steps != expected:
            raise ValueError("流程步骤必须按采集、分析、作词的依赖顺序排列")
        if "lyrics" in self.steps and "analysis" not in self.steps:
            raise ValueError("自动作词步骤必须接在内容分析步骤之后")
        return self


class WorkflowTemplateResponse(BaseModel):
    id: int
    name: str
    steps: list[WorkflowStepValue]
    configuration: WorkflowConfiguration
    created_by_id: int | None
    created_by_username: str | None
    created_at: datetime
    updated_at: datetime


class WorkflowRunStepResponse(BaseModel):
    id: int
    step_type: WorkflowStepValue
    position: int
    status: TaskStatusValue
    task_id: int | None
    output_id: int | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None


class WorkflowRunResponse(BaseModel):
    id: int
    template_id: int | None
    template_name: str
    configuration: WorkflowConfiguration
    status: TaskStatusValue
    current_step: WorkflowStepValue | None
    requested_by_id: int | None
    requested_by_username: str | None
    error_code: str | None
    error_message: str | None
    error_detail: dict[str, object] | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    steps: list[WorkflowRunStepResponse]


class WorkflowRunListResponse(BaseModel):
    items: list[WorkflowRunResponse]
    total: int
