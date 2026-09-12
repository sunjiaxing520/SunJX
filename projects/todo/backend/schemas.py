from typing import Literal
from datetime import date as Date
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Project(Strict):
    id: str = Field(min_length=1, max_length=36)
    name: str = Field(min_length=1, max_length=80)
    kind: Literal['general','postgrad','civil','upgrade','personal'] = 'general'
    color: Literal['blue','orange','green','purple','pink'] = 'blue'
    goal: str = Field(default='', max_length=3000)
    deadline: Date | None = None
    hours: float = Field(default=2, ge=0.25, le=16)
    details: str = Field(default='', max_length=5000)

class Subtask(Strict):
    id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=1, max_length=200)
    done: bool = False

class Task(Strict):
    id: str = Field(min_length=1, max_length=36)
    project_id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=1, max_length=200)
    task_type: Literal['normal','vocabulary'] = 'normal'
    date: Date | None = None
    time: str = Field(default='', pattern=r'^$|^([01]\d|2[0-3]):[0-5]\d$')
    minutes: int = Field(default=30, ge=0, le=960)
    actual_minutes: int = Field(default=0, ge=0, le=10080)
    priority: Literal['normal','high'] = 'normal'
    done: bool = False
    completed_at: str | None = Field(default=None, max_length=40)
    notes: str = Field(default='', max_length=5000)
    mastery: Literal['none','learned','review'] = 'none'
    locked: bool = False
    subtasks: list[Subtask] = Field(default_factory=list, max_length=50)
    @field_validator('title')
    @classmethod
    def title_not_blank(cls,v):
        if not v.strip(): raise ValueError('标题不能为空')
        return v.strip()

class State(Strict):
    projects: list[Project] = Field(max_length=100)
    tasks: list[Task] = Field(max_length=5000)
    @model_validator(mode='after')
    def validate_links(self):
        ids = [p.id for p in self.projects]
        tids = [t.id for t in self.tasks]
        if len(ids)!=len(set(ids)) or len(tids)!=len(set(tids)): raise ValueError('存在重复编号')
        if any(t.project_id not in ids for t in self.tasks): raise ValueError('任务所属计划不存在')
        if any(not p.name.strip() for p in self.projects): raise ValueError('计划名称不能为空')
        return self

class StateWrite(State):
    revision: int = Field(ge=0)

class Auth(Strict):
    username: str = Field(min_length=3,max_length=40,pattern=r'^[a-zA-Z0-9_@.\-]+$')
    password: str = Field(min_length=8,max_length=128)
    name: str = Field(default='',max_length=50)

class AIConfig(Strict):
    key: str | None = Field(default=None,max_length=512)
    model: str = Field(default='kimi-k2.6',min_length=1,max_length=100,pattern=r'^[a-zA-Z0-9._\-]+$')

class MemoConfig(Strict):
    key: str = Field(min_length=10,max_length=2048)

class MemoQuestion(Strict):
    message: str = Field(default='根据今天墨墨的真实学习进度，帮我分析完成情况，并给出下一步背词和复习建议。',min_length=1,max_length=3000)

class ChatInput(Strict):
    project_id: str = Field(min_length=1,max_length=36)
    message: str = Field(min_length=1,max_length=6000)
    today: Date
    request_id: str = Field(min_length=1,max_length=36)

class Change(Strict):
    op: Literal['add','update','delete']
    id: str | None = None
    fields: dict = Field(default_factory=dict)

class AIReply(Strict):
    message: str = Field(min_length=1,max_length=12000)
    changes: list[Change] = Field(default_factory=list,max_length=40)
